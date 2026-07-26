"""
foreground_fix.py — replicate the input-unstick that Ctrl+Alt+Del performs,
surgically.

The SteamVR "laser can't click the desktop" bug is a Windows foreground-focus
problem. Ctrl+Alt+Del fixes it because the secure-desktop round trip forces
Windows to re-resolve the foreground window and drop stuck keys/buttons.
"""

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ---- SendInput plumbing ----------------------------------------------------
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_KEYUP = 0x0002
ULONG_PTR = wintypes.WPARAM

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]

class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]

def _send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    return user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

def _key_up(vk):
    i = INPUT(type=INPUT_KEYBOARD)
    i.u.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)
    return i

def _key_down(vk):
    i = INPUT(type=INPUT_KEYBOARD)
    i.u.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=0)
    return i

def _mouse(flags):
    i = INPUT(type=INPUT_MOUSE)
    i.u.mi = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=0)
    return i

def _is_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)

# ---- step 1+2: release ONLY what is actually stuck -------------------------
_MODIFIERS = {  # vk: name
    0xA0: "LShift", 0xA1: "RShift", 0xA2: "LCtrl", 0xA3: "RCtrl",
    0xA4: "LAlt", 0xA5: "RAlt", 0x5B: "LWin", 0x5C: "RWin",
}
_MOUSE_BUTTONS = {  # vk: (name, up-flag)
    0x01: ("LButton", 0x0004), 0x02: ("RButton", 0x0010), 0x04: ("MButton", 0x0040),
}

def release_stuck(check_mouse=True):
    """Release stuck modifiers/buttons. Returns list of names released."""
    released = []
    for vk, name in _MODIFIERS.items():
        if _is_down(vk):
            _send(_key_up(vk))
            released.append(name)
    if check_mouse:
        for vk, (name, upflag) in _MOUSE_BUTTONS.items():
            if _is_down(vk):
                _send(_mouse(upflag))
                released.append(name)
    return released

# ---- step 3: re-assert foreground without synthetic input ------------------
def _find_main_window(pid):
    if not pid:
        return 0
    found = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if (wpid.value == pid and user32.IsWindowVisible(hwnd)
                and user32.GetWindow(hwnd, 4) == 0  # GW_OWNER: unowned only
                and user32.GetWindowTextLengthW(hwnd) > 0):
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found[0] if found else 0

WM_CANCELMODE = 0x001F

def _cancel_menu_mode(*hwnds):
    """Cancel menu/capture mode without keystrokes (PostMessage: hang-safe)."""
    for h in hwnds:
        if h:
            user32.PostMessageW(h, WM_CANCELMODE, 0, 0)

def reassert_foreground(target_pid=None):
    """Force the scene app's window to real foreground. Returns (hwnd, ok)."""
    SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001
    user32.SystemParametersInfoW(SPI_SETFOREGROUNDLOCKTIMEOUT, 0, None, 0)
    user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY

    old_fg = user32.GetForegroundWindow()
    target = _find_main_window(target_pid) or old_fg
    if not target:
        return 0, False
    if target == old_fg:
        # already foreground — nudging it again is still useful: it forces the
        # window manager to re-evaluate the activation state
        user32.BringWindowToTop(target)
        user32.SetForegroundWindow(target)
        return target, True

    our_tid = kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(old_fg, None) if old_fg else 0
    tgt_tid = user32.GetWindowThreadProcessId(target, None)

    attached_fg = fg_tid and user32.AttachThreadInput(our_tid, fg_tid, True)
    attached_tgt = tgt_tid and user32.AttachThreadInput(our_tid, tgt_tid, True)
    try:
        user32.BringWindowToTop(target)
        user32.SetForegroundWindow(target)
        user32.ShowWindow(target, 5)  # SW_SHOW
    finally:
        if attached_fg:
            user32.AttachThreadInput(our_tid, fg_tid, False)
        if attached_tgt:
            user32.AttachThreadInput(our_tid, tgt_tid, False)

    ok = user32.GetForegroundWindow() == target
    if not ok:
        # last resort: Alt tap unlocks SetForegroundWindow for us, then we
        # immediately cancel the menu mode it may have started
        _send(_key_down(0xA4))          # LAlt down
        user32.SetForegroundWindow(target)
        _send(_key_up(0xA4))            # LAlt up
        _cancel_menu_mode(old_fg, target, user32.GetForegroundWindow())
        ok = user32.GetForegroundWindow() == target
    return target, ok

def run_fix(target_pid=None):
    """Full unstick. Returns dict for logging/UI."""
    released = release_stuck()
    hwnd, ok = reassert_foreground(target_pid)
    return {"released": released, "hwnd": hwnd, "foreground_ok": ok}

if __name__ == "__main__":
    import sys
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(run_fix(pid))
