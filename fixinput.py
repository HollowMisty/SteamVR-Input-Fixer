"""
fixinput.py — Fix Input: one-button SteamVR dashboard overlay that unsticks
the "laser can't click the desktop / game stops taking input" bug.

Distribution is via the NSIS installer (see installer.nsi / build_installer.bat),
which owns Start Menu / Apps & Features integration. This exe handles the
overlay and the SteamVR side:

  FixInput.exe --overlay      run the dashboard overlay (SteamVR auto-launch
                              target; also re-registers itself, so launching
                              it once while SteamVR is up always heals the
                              registration)
  FixInput.exe --register     silent: write .vrmanifest next to the exe,
                              register + enable auto-launch (used by installer)
  FixInput.exe --unregister   silent: remove from SteamVR (used by uninstaller)
  FixInput.exe                register, launch overlay, confirm with a dialog

Works identically from source:  python fixinput.py [--overlay|...]
"""

import ctypes
import json
import os
import subprocess
import sys
import time

import glfw
import openvr
from OpenGL import GL

import foreground_fix

# app key is stable on purpose — renames must not orphan the SteamVR
# registration or its auto-launch setting
APP_KEY = "hollowmist.vrforegroundfix"
APP_NAME = "SteamVR Input Fixer"
VERSION = "1.0.0"

# panel geometry — must match gen_assets.py
PANEL_W, PANEL_H = 800.0, 500.0
# central button rect (vertically centered, so a mouse-Y flip maps it onto
# itself and the hit test works on either origin convention)
BTN_L, BTN_T, BTN_R, BTN_B = 200.0, 170.0, 600.0, 330.0
# texture region re-uploaded on state change: button + the subtitle band
UPD_RECT = (200, 170, 600, 410)
# hysteresis: the pointer must leave a slightly larger rect to drop hover,
# so edge jitter can't rapid-toggle states
HOVER_PAD = 14.0

FROZEN = getattr(sys, "frozen", False)
# bundled read-only assets (PyInstaller unpack dir when frozen)
BUNDLE_DIR = getattr(sys, "_MEIPASS",
                     os.path.dirname(os.path.abspath(__file__)))
# the app's own directory: manifest, log and icon copy live here
APP_DIR = os.path.dirname(os.path.abspath(
    sys.executable if FROZEN else __file__))
MANIFEST = os.path.join(APP_DIR, "fixinput.vrmanifest")


def asset(name):
    return os.path.join(BUNDLE_DIR, name)


def log(msg):
    line = f"[fix-input] {time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    try:  # windowed builds have no console — the file is the only visible log
        with open(os.path.join(APP_DIR, "fixinput.log"), "a",
                  encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def message_box(text, title=APP_NAME):
    ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)  # MB_ICONINFO


# --------------------------------------------------------------------------
# SteamVR registration
# --------------------------------------------------------------------------
def _launch_spec():
    """(binary_path, arguments) SteamVR should use to start the overlay."""
    if FROZEN:
        return sys.executable, "--overlay"
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    binary = pyw if os.path.exists(pyw) else sys.executable
    return binary, f'"{os.path.abspath(__file__)}" --overlay'


def write_manifest():
    import shutil
    icon_dst = os.path.join(APP_DIR, "icon.png")
    if not os.path.exists(icon_dst):
        shutil.copy2(asset("icon.png"), icon_dst)
    binary, args = _launch_spec()
    data = {
        "source": "builtin",
        "applications": [{
            "app_key": APP_KEY,
            "launch_type": "binary",
            "binary_path_windows": binary,
            "arguments": args,
            "is_dashboard_overlay": True,
            "image_path": icon_dst,
            "strings": {"en_us": {
                "name": APP_NAME,
                "description": "One-tap foreground/input reset for the "
                               "SteamVR laser-can't-click bug.",
            }},
        }],
    }
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def register(auto_launch=True):
    """Needs the SteamVR runtime reachable; raises if it isn't."""
    write_manifest()
    openvr.init(openvr.VRApplication_Utility)
    try:
        apps = openvr.IVRApplications()
        apps.addApplicationManifest(MANIFEST, False)
        apps.setApplicationAutoLaunch(APP_KEY, auto_launch)
    finally:
        openvr.shutdown()


def unregister():
    openvr.init(openvr.VRApplication_Utility)
    try:
        apps = openvr.IVRApplications()
        try:
            apps.setApplicationAutoLaunch(APP_KEY, False)
        except Exception:
            pass
        apps.removeApplicationManifest(MANIFEST)
    finally:
        openvr.shutdown()


# --------------------------------------------------------------------------
# overlay
# --------------------------------------------------------------------------
def in_button(x, y, pad=0.0):
    return (BTN_L - pad) <= x <= (BTN_R + pad) and \
           (BTN_T - pad) <= y <= (BTN_B + pad)


def run_overlay():
    # hidden GL context: the overlay texture lives on the GPU permanently and
    # state changes patch it in place — no texture re-creation, no flicker
    if not glfw.init():
        raise RuntimeError("GLFW init failed")
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    gl_window = glfw.create_window(64, 64, "inputfixer-gl", None, None)
    if not gl_window:
        glfw.terminate()
        raise RuntimeError("GLFW window creation failed")
    glfw.make_context_current(gl_window)

    openvr.init(openvr.VRApplication_Overlay)
    overlay = openvr.IVROverlay()
    apps = openvr.IVRApplications()

    # heal registration on every start: running the app once while SteamVR is
    # up is always enough to (re)establish auto-launch
    try:
        write_manifest()
        apps.addApplicationManifest(MANIFEST, False)
        apps.setApplicationAutoLaunch(APP_KEY, True)
    except Exception as e:
        log(f"startup registration skipped: {e!r}")

    main_handle, thumb_handle = overlay.createDashboardOverlay(APP_KEY, APP_NAME)
    overlay.setOverlayWidthInMeters(main_handle, 1.375)
    overlay.setOverlayInputMethod(main_handle, openvr.VROverlayInputMethod_Mouse)

    scale = openvr.HmdVector2_t()
    scale.v[0], scale.v[1] = PANEL_W, PANEL_H
    overlay.setOverlayMouseScale(main_handle, scale)

    overlay.setOverlayFromFile(thumb_handle, asset("icon.png"))

    # one persistent GPU texture: full panel uploaded once, then state changes
    # rewrite only the button band via glTexSubImage2D (pixel data is stored
    # bottom-up per GL convention; gen_assets pre-flips it)
    tex_w, tex_h = int(PANEL_W), int(PANEL_H)
    with open(asset("panel_base.rgba"), "rb") as f:
        base_pixels = f.read()
    patches = {}
    for name in ("idle", "hover", "done"):
        with open(asset(f"btn_{name}.rgba"), "rb") as f:
            patches[name] = f.read()

    tex_id = int(GL.glGenTextures(1))
    GL.glBindTexture(GL.GL_TEXTURE_2D, tex_id)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
    GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
    GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, tex_w, tex_h, 0,
                    GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, base_pixels)
    GL.glFlush()

    vr_texture = openvr.Texture_t()
    vr_texture.handle = tex_id
    vr_texture.eType = openvr.TextureType_OpenGL
    vr_texture.eColorSpace = openvr.ColorSpace_Auto
    overlay.setOverlayTexture(main_handle, vr_texture)

    upd_l, upd_t, upd_r, upd_b = UPD_RECT
    upd_w, upd_h = upd_r - upd_l, upd_b - upd_t
    upd_gl_y = tex_h - upd_b  # region origin in bottom-up texture coords

    def apply_state(name):
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex_id)
        GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, upd_l, upd_gl_y, upd_w, upd_h,
                           GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, patches[name])
        GL.glFlush()
        overlay.setOverlayTexture(main_handle, vr_texture)

    log("overlay ready — open the SteamVR dashboard and tap the button")

    state = "idle"  # idle | hover | done

    def set_state(new):
        nonlocal state
        if new != state:
            state = new
            apply_state(new)

    last_fire = 0.0
    revert_at = None
    event = openvr.VREvent_t()
    running = True
    while running:
        while True:
            # pyopenvr returns (bool, event) — the tuple itself is always
            # truthy, so the result flag MUST be unpacked and tested
            got_event, event = overlay.pollNextOverlayEvent(main_handle, event)
            if not got_event:
                break
            et = event.eventType
            if et == openvr.VREvent_MouseMove:
                if state != "done":
                    m = event.data.mouse
                    if state == "hover":
                        if not in_button(m.x, m.y, HOVER_PAD):
                            set_state("idle")
                    elif in_button(m.x, m.y):
                        set_state("hover")
            elif et == openvr.VREvent_FocusLeave:
                if state != "done":
                    set_state("idle")
            elif et == openvr.VREvent_MouseButtonUp:
                x, y = event.data.mouse.x, event.data.mouse.y
                log(f"tap at ({x:.0f}, {y:.0f})")
                if not in_button(x, y):
                    continue
                now = time.monotonic()
                if now - last_fire < 1.2:
                    continue
                last_fire = now
                try:
                    pid = apps.getCurrentSceneProcessId()
                except Exception:
                    pid = None
                result = foreground_fix.run_fix(pid or None)
                log(f"fix fired (scene pid={pid}) -> {result}")
                set_state("done")
                revert_at = time.monotonic() + 1.2
            elif et == openvr.VREvent_Quit:
                log("SteamVR quitting")
                running = False
                break

        if revert_at is not None and time.monotonic() >= revert_at:
            revert_at = None
            set_state("idle")  # next MouseMove re-asserts hover if applicable
        glfw.poll_events()
        time.sleep(0.02)

    openvr.shutdown()
    glfw.terminate()


# --------------------------------------------------------------------------
def main(argv):
    if "--selftest" in argv:
        # build verification: prove the bundle unpacks and imports cleanly
        out = argv[argv.index("--selftest") + 1]
        with open(out, "w", encoding="utf-8") as f:
            base_ok = (os.path.exists(asset("panel_base.rgba")) and
                       os.path.getsize(asset("panel_base.rgba"))
                       == int(PANEL_W) * int(PANEL_H) * 4)
            patch_expect = (UPD_RECT[2] - UPD_RECT[0]) * (UPD_RECT[3] - UPD_RECT[1]) * 4
            patch_ok = [os.path.exists(asset(f"btn_{n}.rgba")) and
                        os.path.getsize(asset(f"btn_{n}.rgba")) == patch_expect
                        for n in ("idle", "hover", "done")]
            f.write(f"SELFTEST_OK frozen={FROZEN} gl={bool(glfw.init())} "
                    f"icon={os.path.exists(asset('icon.png'))} "
                    f"base_ok={base_ok} patch_ok={patch_ok}\n")
        return
    if "--register" in argv:
        try:
            register()
            log("registered with SteamVR")
        except Exception as e:
            log(f"register failed (SteamVR off?): {e!r} — the overlay "
                "re-registers itself on next launch with SteamVR running")
    elif "--unregister" in argv:
        try:
            unregister()
            log("unregistered from SteamVR")
        except Exception as e:
            log(f"unregister failed (SteamVR off?): {e!r}")
    elif "--overlay" in argv:
        try:
            run_overlay()
        except openvr.error_code.InitError_Init_HmdNotFound:
            log("no HMD / SteamVR not running")
            sys.exit(1)
        except Exception as e:
            log(f"overlay error: {e!r}")
            sys.exit(1)
    else:
        # direct double-click: register and start, then confirm
        try:
            register()
            binary, _ = _launch_spec()
            cmd = [binary, "--overlay"] if FROZEN else \
                [binary, os.path.abspath(__file__), "--overlay"]
            subprocess.Popen(cmd, creationflags=0x08000008,  # NO_WINDOW|DETACHED
                             close_fds=True)
            message_box("Fix Input is registered and running.\n\nIt will "
                        "start automatically with SteamVR — look for the "
                        "panel in your dashboard.")
        except Exception as e:
            log(f"register failed: {e!r}")
            message_box("SteamVR isn't running, so Fix Input couldn't "
                        "register yet.\n\nStart SteamVR and run Fix Input "
                        "once more.")


if __name__ == "__main__":
    main(sys.argv[1:])
