@echo off
where pythonw >nul 2>nul && (start "" pythonw "%~dp0xtra_gui.py" & exit /b)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (start "" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" "%~dp0xtra_gui.py" & exit /b)
where py >nul 2>nul && (start "" pyw -3 "%~dp0xtra_gui.py" & exit /b)
echo Python non trovato nel PATH. Avvio con python...
python "%~dp0xtra_gui.py"
pause