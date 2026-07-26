; installer.nsi — full wizard installer for SteamVR Input Fixer
; Compile with the NSIS that electron-builder caches (see build_installer.bat)

!include "MUI2.nsh"
!include "LogicLib.nsh"

!define APPNAME "SteamVR Input Fixer"
!define EXENAME "SteamVRInputFixer.exe"
!define VERSION "1.0.0"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\SteamVRInputFixer"

Name "${APPNAME}"
OutFile "dist\SteamVRInputFixerSetup.exe"
Unicode True
InstallDir "$LOCALAPPDATA\Programs\SteamVRInputFixer"
RequestExecutionLevel user
SetCompressor /SOLID lzma

VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "${APPNAME}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "CompanyName" "hollow_misty"
VIAddVersionKey "FileDescription" "${APPNAME} Setup"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" ""

!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXENAME}"
!define MUI_FINISHPAGE_RUN_PARAMETERS "--overlay"
!define MUI_FINISHPAGE_RUN_TEXT "Launch now (requires SteamVR)"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  ; stop a running overlay so the exe can be replaced (upgrade path)
  nsExec::Exec 'taskkill /F /IM ${EXENAME}'
  File "dist\${EXENAME}"
  ; register with SteamVR (writes .vrmanifest, enables auto-launch);
  ; harmless if SteamVR is off — the overlay re-registers itself on launch
  nsExec::Exec '"$INSTDIR\${EXENAME}" --register'
  CreateShortcut "$SMPROGRAMS\${APPNAME}.lnk" "$INSTDIR\${EXENAME}"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "hollow_misty"
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${EXENAME}"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  ; remove from SteamVR first (needs the exe still present), then stop it
  nsExec::Exec '"$INSTDIR\${EXENAME}" --unregister'
  nsExec::Exec 'taskkill /F /IM ${EXENAME}'
  Delete "$INSTDIR\${EXENAME}"
  Delete "$INSTDIR\fixinput.vrmanifest"
  Delete "$INSTDIR\icon.png"
  Delete "$INSTDIR\fixinput.log"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\${APPNAME}.lnk"
  DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd
