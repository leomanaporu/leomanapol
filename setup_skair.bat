@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ---------------------------------------------------------------------------
:: Skair One-Click Installer    
:: Copies Skair files to Program Files, installs Node deps, creates a
:: scheduled task and shortcuts, then runs the consent handler.
:: ---------------------------------------------------------------------------

:: ---- Check for administrative rights ----------------------------------------
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================
echo   Skair Installer
echo ============================================
echo.

:: ---- Display installer logo (if logo.png exists) ----------------------------
if exist "%~dp0logo.png" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $img = [System.Drawing.Image]::FromFile('%~dp0logo.png'); $form = New-Object Windows.Forms.Form; $form.Text = 'Skair Installer'; $form.StartPosition = 'CenterScreen'; $form.Size = New-Object Drawing.Size(400,400); $pic = New-Object Windows.Forms.PictureBox; $pic.Image = $img; $pic.SizeMode = 'Zoom'; $pic.Dock = 'Fill'; $form.Controls.Add($pic); $timer = New-Object Windows.Forms.Timer; $timer.Interval = 3000; $timer.Add_Tick({ $form.Close() }); $timer.Start(); $form.ShowDialog()"
)

:: ---- Run prerequisite installer ---------------------------------------------
call "%~dp0install_prereqs.bat"
if %errorlevel% neq 0 (
    echo.
    echo Prerequisite check failed. Aborting installation.
    goto :End
)

:: ---- Define source and destination folders -----------------------------------
set "SRC_DIR=%~dp0"
set "DEST_DIR=%ProgramFiles%\Skair"

echo.
echo Source:      %SRC_DIR%
echo Destination: %DEST_DIR%
echo.

:: ---- Create destination folder if it does not exist --------------------------
if not exist "%DEST_DIR%" (
    mkdir "%DEST_DIR%"
    if !errorlevel! neq 0 (
        echo Failed to create "%DEST_DIR%". Aborting.
        goto :End
    )
)

:: ---- Prepare exclude list ---------------------------------------------------
:: Exclude: this installer, the prereqs script, .venv dir, worker_log, .vscode
:: NOTE: xcopy /EXCLUDE does NOT accept quotes around the filename.
::       We use the 8.3 short path to handle spaces in TEMP if any.
set "EXCLUDE_FILE=%TEMP%\skair_exclude.txt"
(
    echo %~nx0
    echo install_prereqs.bat
    echo install_skair.ps1
    echo .venv\
    echo .vscode\
    echo worker_log.txt
    echo index.html.bak
) > "%EXCLUDE_FILE%"

:: Get the 8.3 short path (safe for xcopy /EXCLUDE which can't handle quotes)
for %%F in ("%EXCLUDE_FILE%") do set "EXCL_SHORT=%%~sF"

:: Verify the exclude file was created
if not exist "%EXCLUDE_FILE%" (
    echo WARNING: Could not create exclude file. Copying all files.
    xcopy "%SRC_DIR%*" "%DEST_DIR%\" /E /H /C /I /Y >nul
) else (
    xcopy "%SRC_DIR%*" "%DEST_DIR%\" /E /H /C /I /Y /EXCLUDE:%EXCL_SHORT% >nul
)

:: ---- Verify that critical files were copied ---------------------------------
set "COPY_OK=1"
if not exist "%DEST_DIR%\consent_handler.py" (
    echo WARNING: consent_handler.py missing after copy.
    copy "%SRC_DIR%consent_handler.py" "%DEST_DIR%\" >nul 2>&1
    if not exist "%DEST_DIR%\consent_handler.py" (
        echo ERROR: consent_handler.py could not be copied.
        set "COPY_OK=0"
    )
)
if not exist "%DEST_DIR%\silent_worker.py" (
    echo WARNING: silent_worker.py missing after copy.
    copy "%SRC_DIR%silent_worker.py" "%DEST_DIR%\" >nul 2>&1
)
if not exist "%DEST_DIR%\server.js" (
    echo WARNING: server.js missing after copy.
    copy "%SRC_DIR%server.js" "%DEST_DIR%\" >nul 2>&1
)
if not exist "%DEST_DIR%\admin.html" (
    echo WARNING: admin.html missing after copy.
    copy "%SRC_DIR%admin.html" "%DEST_DIR%\" >nul 2>&1
)

echo.
echo Files copied to %DEST_DIR%:
dir /B "%DEST_DIR%"
echo.

:: ---- Install Node.js dependencies if package.json exists --------------------
if exist "%DEST_DIR%\package.json" (
    echo Installing Node.js packages...
    pushd "%DEST_DIR%"
    where npm >nul 2>&1
    if !errorlevel! equ 0 (
        npm install
    ) else (
        if exist "C:\Program Files\nodejs\npm.cmd" (
            "C:\Program Files\nodejs\npm.cmd" install
        ) else (
            echo WARNING: npm not found. Skipping dependency installation.
            echo          server.js will fail to start until you run: npm install
        )
    )
    popd
) else (
    echo No package.json found - skipping npm install.
)

:: ---- Register scheduled task ------------------------------------------------
echo.
echo Creating scheduled task SkairConsentHandler...
schtasks /Create /TN "SkairConsentHandler" /TR "python \"%DEST_DIR%\consent_handler.py\" --reset" /RL HIGHEST /SC ONLOGON /F >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Failed to create scheduled task. You may need to create it manually.
) else (
    echo Scheduled task created successfully.
)

:: ---- Create shortcuts -------------------------------------------------------
set "SHORTCUT_NAME=Skair Admin"

echo Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $p = [Environment]::GetFolderPath('Desktop') + '\%SHORTCUT_NAME%.lnk'; $s = $ws.CreateShortcut($p); $s.TargetPath = 'C:\Windows\System32\cmd.exe'; $s.Arguments = '/c start \"\" \"%DEST_DIR%\admin.html\"'; $s.WorkingDirectory = '%DEST_DIR%'; $s.IconLocation = 'shell32.dll,13'; $s.Save()"

echo Creating Start Menu shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $p = [Environment]::GetFolderPath('Programs') + '\%SHORTCUT_NAME%.lnk'; $s = $ws.CreateShortcut($p); $s.TargetPath = 'C:\Windows\System32\cmd.exe'; $s.Arguments = '/c start \"\" \"%DEST_DIR%\admin.html\"'; $s.WorkingDirectory = '%DEST_DIR%'; $s.IconLocation = 'shell32.dll,13'; $s.Save()"

:: ---- Run consent handler immediately ----------------------------------------
echo.
if exist "%DEST_DIR%\consent_handler.py" (
    echo Launching consent handler...
    python "%DEST_DIR%\consent_handler.py" --reset
) else (
    echo ERROR: consent_handler.py not found - cannot launch consent flow.
)

:End
echo.
echo ============================================
if "%COPY_OK%"=="0" (
    echo   Installation INCOMPLETE - see errors above.
) else (
        echo   Skair installation completed.
    )
echo ============================================
pause
