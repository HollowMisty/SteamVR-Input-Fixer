@echo off
rem Build the self-contained FixInput.exe into dist\
cd /d "%~dp0"
python gen_assets.py || exit /b 1
python -m PyInstaller --noconfirm --onefile --noconsole --name SteamVRInputFixer ^
  --icon icon.ico --collect-all openvr --collect-all glfw ^
  --add-data "panel_base.rgba;." --add-data "btn_idle.rgba;." --add-data "btn_hover.rgba;." --add-data "btn_done.rgba;." --add-data "icon.png;." ^
  fixinput.py
echo.
echo Built: %~dp0dist\SteamVRInputFixer.exe
