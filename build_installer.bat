@echo off
rem Build dist\FixInputSetup.exe — full wizard installer.
rem Uses the NSIS copy electron-builder caches; falls back to a system NSIS.
cd /d "%~dp0"
call "%~dp0build.bat" || exit /b 1

set MAKENSIS=%LOCALAPPDATA%\electron-builder\Cache\nsis\nsis-3.0.4.1\Bin\makensis.exe
if not exist "%MAKENSIS%" set MAKENSIS=%LOCALAPPDATA%\electron-builder\Cache\nsis\nsis-3.0.4.1\makensis.exe
if not exist "%MAKENSIS%" set MAKENSIS=makensis

"%MAKENSIS%" "%~dp0installer.nsi" || exit /b 1
echo.
echo Built: %~dp0dist\SteamVRInputFixerSetup.exe
