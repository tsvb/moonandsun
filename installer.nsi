; NSIS installer script for Moon and Sun Natal Chart
; Build with: makensis installer.nsi

!include "MUI2.nsh"

Name "Moon and Sun Natal Chart"
OutFile "moonandsun_setup.exe"
InstallDir "$PROGRAMFILES\MoonAndSun"
RequestExecutionLevel admin

Page directory
Page instfiles

Section "Install"
    SetOutPath "$INSTDIR"
    File /r "dist\natal_chart\*.*"
    CreateShortcut "$DESKTOP\Moon and Sun.lnk" "$INSTDIR\natal_chart.exe"
    CreateDirectory "$SMPROGRAMS\Moon and Sun"
    CreateShortcut "$SMPROGRAMS\Moon and Sun\Moon and Sun.lnk" "$INSTDIR\natal_chart.exe"
SectionEnd
