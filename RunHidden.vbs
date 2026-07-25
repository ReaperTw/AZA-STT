Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' 1. 取得目前資料夾路徑
CurrentDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' 2. 組合出 Start.bat 的「完整路徑」
BatPath = FSO.BuildPath(CurrentDir, "Start.bat")

' 3. 組合執行指令
CommandArg = "cmd.exe /c """ & BatPath & """"

' 4. 執行 (0 表示隱藏視窗，False 表示不等待執行結束)
WshShell.Run CommandArg, 0, False