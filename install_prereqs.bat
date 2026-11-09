@echo off
:: ---------------------------------------------------------------
:: install_prereqs.bat - Check for Python, Node.js, npm and install
:: via winget if missing.  Returns errorlevel 0 on success.
:: ---------------------------------------------------------------

setlocal EnableExtensions

:: ---------- Check for Python ----------
set "PYTHON_INSTALLED=0"
where python >nul 2>&1 && set "PYTHON_INSTALLED=1"
if "%PYTHON_INSTALLED%"=="0" (
    echo Python is not installed or not on PATH.
) else (
    echo Python detected.
)

:: ---------- Check for Node.js ----------
set "NODE_INSTALLED=0"
where node >nul 2>&1 && set "NODE_INSTALLED=1"
:: Also check the default install path if not on PATH
if "%NODE_INSTALLED%"=="0" (
    if exist "C:\Program Files\nodejs\node.exe" (
        echo Node.js found at C:\Program Files\nodejs but not on PATH - adding...
        set "PATH=%PATH%;C:\Program Files\nodejs"
        set "NODE_INSTALLED=1"
    ) else (
        echo Node.js is not installed or not on PATH.
    )
) else (
    echo Node.js detected.
)

:: ---------- Check for npm ----------
set "NPM_INSTALLED=0"
where npm >nul 2>&1 && set "NPM_INSTALLED=1"
if "%NPM_INSTALLED%"=="0" (
    :: npm ships with Node; check default path
    if exist "C:\Program Files\nodejs\npm.cmd" (
        set "NPM_INSTALLED=1"
    ) else (
        echo npm is not available.
    )
) else (
    echo npm detected.
)

:: ---------- Auto-install missing components via winget ----------
if "%PYTHON_INSTALLED%"=="1" if "%NODE_INSTALLED%"=="1" goto :AllPresent

where winget >nul 2>&1
if %errorlevel% neq 0 (
    echo winget not found - cannot auto-install.
    if "%PYTHON_INSTALLED%"=="0" echo Please install Python from https://www.python.org/downloads/
    if "%NODE_INSTALLED%"=="0"   echo Please install Node.js from https://nodejs.org/en/download/
    endlocal
    exit /b 1
)

echo winget found - attempting to install missing components.

if "%PYTHON_INSTALLED%"=="0" (
    echo Installing Python via winget...
    winget install --id Python.Python.3 -e --accept-source-agreements --accept-package-agreements
)

if "%NODE_INSTALLED%"=="0" (
    echo Installing Node.js via winget...
    winget install --id OpenJS.NodeJS -e --accept-source-agreements --accept-package-agreements
    :: Add to current session PATH
    if exist "C:\Program Files\nodejs\node.exe" (
        echo Node.js installed, adding to session PATH...
        set "PATH=%PATH%;C:\Program Files\nodejs"
    )
)

:AllPresent
:: ---------- Final verification ----------
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo *** ERROR: Python is still missing after install attempt.
    endlocal
    exit /b 1
)
echo Python ready.

where node >nul 2>&1
if %errorlevel% neq 0 (
    if exist "C:\Program Files\nodejs\node.exe" (
        set "PATH=%PATH%;C:\Program Files\nodejs"
    ) else (
        echo *** ERROR: Node.js is still missing after install attempt.
        endlocal
        exit /b 1
    )
)
echo Node.js ready.

where npm >nul 2>&1
if %errorlevel% neq 0 (
    if exist "C:\Program Files\nodejs\npm.cmd" (
        echo npm available via direct path.
    ) else (
        echo *** WARNING: npm not found. npm install step will be skipped.
    )
) else (
    echo npm ready.
)

:: Pass PATH changes back to parent by ending setlocal and re-setting PATH
endlocal & set "PATH=%PATH%"
exit /b 0

