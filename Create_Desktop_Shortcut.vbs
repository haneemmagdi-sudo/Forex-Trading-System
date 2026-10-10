Set oWS = WScript.CreateObject("WScript.Shell")
Dim DesktopPath
DesktopPath = oWS.SpecialFolders("Desktop")

' ─── Get Script Directory ────────────────────────────────────────────────
Dim ScriptDir
ScriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' ─── Create Single Desktop Shortcut ─────────────────────────────────────
Dim sLinkFile
sLinkFile = DesktopPath & "\Run_Quantum_Trading.lnk"

Dim oLink
Set oLink = oWS.CreateShortcut(sLinkFile)

' Point directly to the batch file (shows a window with status)
oLink.TargetPath       = ScriptDir & "\Run_Quantum_Trading.bat"
oLink.WorkingDirectory = ScriptDir
oLink.Description      = "Quantum AI Forex Trading System - Full Launch (Backend + Frontend + MT5)"
oLink.WindowStyle      = 1

' Use a nice chart/trading icon from system32
oLink.IconLocation = "%SystemRoot%\System32\shell32.dll, 171"

oLink.Save

MsgBox "تم إنشاء أيقونة التشغيل على سطح المكتب!" & vbCrLf & vbCrLf & _
       "انقر نقراً مزدوجاً على:" & vbCrLf & _
       "Run_Quantum_Trading" & vbCrLf & vbCrLf & _
       "سيشغل النظام تلقائياً:" & vbCrLf & _
       "  - سيرفر الباكيند (port 8000)" & vbCrLf & _
       "  - سيرفر الفرونتيند (port 5173)" & vbCrLf & _
       "  - MetaTrader 5" & vbCrLf & _
       "  - يفتح المتصفح على http://localhost:5173", _
       vbInformation, "Quantum Forex - Setup Complete"
