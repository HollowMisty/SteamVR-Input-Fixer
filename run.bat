@echo off
rem Dev launcher — runs the overlay from source without installing
start "" "%LocalAppData%\Programs\Python\Python314\pythonw.exe" "%~dp0fixinput.py" --overlay
