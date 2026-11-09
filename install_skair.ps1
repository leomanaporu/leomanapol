# install_skair.ps1 - One‑click installer for Skair
# -----------------------------------------------------
# This script copies the Skair files to a permanent location,
# installs Node.js dependencies, registers a scheduled task
# that runs the consent handler at user logon, and creates a
# desktop shortcut to the admin UI.

# -------------------- Configuration --------------------
$installDir = "$env:ProgramFiles\Skair"
$sourceDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition  # folder containing this script
$desktop    = [Environment]::GetFolderPath('Desktop')
$startMenu  = Join-Path ([Environment]::GetFolderPath('Programs')) "Skair"

function Write-Log { param([string]$msg) Write-Host "[Skair Installer] $msg" }

# -------------------- Helper Functions --------------------
function Test-NodeInstalled {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Write-Log "Node.js not found. Please install Node.js (https://nodejs.org/) and re‑run this script."
        exit 1
    }
}

function Test-PythonInstalled {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Log "Python not found. Please install Python 3.8+ (https://www.python.org/) and ensure it is on PATH."
        exit 1
    }
}

function Copy-Files {
    Write-Log "Copying Skair files to $installDir ..."
    if (Test-Path $installDir) { Remove-Item -Recurse -Force $installDir }
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    # Copy everything in the current directory (except installer scripts)
    Get-ChildItem -Path $sourceDir -File | Where-Object { $_.Name -notmatch '^install_.*\.ps1$' } | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $installDir -Force
    }
    # Also copy subfolders (index.html, admin.html etc.)
    Get-ChildItem -Path $sourceDir -Directory | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $installDir -Recurse -Force
    }
}

function Install-NodeDependencies {
    Write-Log "Installing Node.js dependencies (express, socket.io, msgpack-lite)..."
    Push-Location $installDir
    npm install express socket.io msgpack-lite | Out-Null
    Pop-Location
}

function Register-ConsentHandlerTask {
    Write-Log "Registering scheduled task to launch consent_handler at logon..."
    $action = New-ScheduledTaskAction -Execute 'python' -Argument "`"$installDir\consent_handler.py`" --reset"
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
    $task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings (New-ScheduledTaskSettingsSet -Compatibility Win10)
    Register-ScheduledTask -TaskName "SkairConsentHandler" -InputObject $task -Force | Out-Null
}

function New-DesktopShortcut {
    $target = "`"$installDir\admin.html`""
    $shortcutPath = Join-Path $desktop "Skair Admin.lnk"
    $ws = New-Object -ComObject WScript.Shell
    $shortcut = $ws.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "C:\Windows\System32\cmd.exe"
    $shortcut.Arguments = "/c start `"$target`""
    $shortcut.IconLocation = "shell32.dll,13"
    $shortcut.Save()
    Write-Log "Desktop shortcut created: $shortcutPath"
}

function New-StartMenuFolder {
    if (-not (Test-Path $startMenu)) { New-Item -ItemType Directory -Path $startMenu | Out-Null }
    # Copy a shortcut into the start‑menu folder
    $target = "`"$installDir\admin.html`""
    $shortcutPath = Join-Path $startMenu "Skair Admin.lnk"
    $ws = New-Object -ComObject WScript.Shell
    $shortcut = $ws.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "C:\Windows\System32\cmd.exe"
    $shortcut.Arguments = "/c start `"$target`""
    $shortcut.IconLocation = "shell32.dll,13"
    $shortcut.Save()
    Write-Log "Start‑Menu shortcut created: $shortcutPath"
}

# -------------------- Execution --------------------
Write-Log "Starting Skair one‑click installer..."
Test-PythonInstalled
Test-NodeInstalled
Copy-Files
Install-NodeDependencies
Register-ConsentHandlerTask
New-DesktopShortcut
New-StartMenuFolder
Write-Log "Installation complete! The consent handler will run at next logon."
Write-Log "Double‑click the 'Skair Admin' shortcut to open the admin dashboard."

