# SteamVR Input Fixer

One-button SteamVR dashboard overlay that fixes the "laser can't click the
desktop / game stops taking input" bug, the one normally cured by opening the
Ctrl+Alt+Del screen and cancelling.

Ctrl+Alt+Del works because the secure-desktop round trip forces Windows to
re-resolve the foreground window and drop stuck modifier keys / mouse buttons.
This overlay reproduces those effects directly with Win32 calls
([foreground_fix.py](foreground_fix.py)), triggered by a button you can reach
without taking the headset off.

## Install

Run **`SteamVRInputFixerSetup.exe`**, a normal wizard installer (NSIS).
It installs to `%LOCALAPPDATA%\Programs\SteamVRInputFixer`, registers with
SteamVR (auto-launch, same mechanism fpsVR / Standable use), and adds a Start
Menu entry plus an Apps & Features uninstall entry. No admin rights, no
Python needed.

If SteamVR wasn't running during install, launch it once from the Start Menu
while SteamVR is up; the overlay re-registers itself on every start.

Uninstall from Windows Settings > Apps. That also removes the SteamVR
registration.

## Use

Open the SteamVR dashboard, pick the **SteamVR Input Fixer** tab, and tap
**FIX INPUT**. The fix:

1. releases stuck modifier keys / mouse buttons, but **only ones actually
   held down** (checked via `GetAsyncKeyState`), so nothing fires on a
   healthy system,
2. forces the running VR game's window (asked from SteamVR, so it works for
   any game) back to the real foreground via `AttachThreadInput`, with no
   synthetic keystrokes.

The button flashes a green **DONE** as confirmation.

## Building

```
pip install openvr pillow pyinstaller PyOpenGL glfw
build_installer.bat
```

NSIS is picked up from electron-builder's cache (or a system install).
`build.bat` alone builds just the exe. Dev mode without installing:
`python fixinput.py` (register + run) / `python fixinput.py --unregister`.

## Files

- `fixinput.py`: the app; overlay (`--overlay`) and SteamVR registration
  (`--register` / `--unregister`)
- `foreground_fix.py`: the unstick logic; also runnable standalone:
  `python foreground_fix.py [pid]`
- `installer.nsi`: NSIS script for the wizard installer
- `gen_assets.py`: regenerates the panel textures and icon
- `build.bat` / `build_installer.bat`: build the exe / the installer
- `run.bat`: dev launch of the overlay from source

## Limitation

If the window that stole focus is **elevated** (running as administrator), an
unprivileged process can't take focus back from it; that variant needs the
real Ctrl+Alt+Del. SteamVR should prevent interaction with elevated windows, however 
if you somehow manage to, you will need to perform the regular Ctrl+Alt+Del fix.

## License

[MIT](LICENSE): free to use, modify, and redistribute; just keep the
copyright notice (credit: HollowMisty / Discord `hollow_misty`).
