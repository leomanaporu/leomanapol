import argparse
import ctypes
import sys
import subprocess
import os
import pathlib
import logging
import platform

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def parse_args():
    parser = argparse.ArgumentParser(description='Consent handler with optional admin elevation')
    parser.add_argument('--force', action='store_true', help='Force showing the consent dialog even if already authorized')
    parser.add_argument('--reset', action='store_true', help='Delete existing authorization file and start fresh')
    return parser.parse_args()



# ---------- ADMIN ELEVATION HELPERS ----------

def is_user_admin():
    """Return True if the current process has administrative privileges (Windows)."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def relaunch_as_admin():
    python_exe = sys.executable
    script_path = os.path.abspath(__file__)
    params = f'"{script_path}"'
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", python_exe, params, None, 1)
    if int(ret) <= 32:
        logging.error("Failed to request admin elevation (ShellExecute returned %s)", ret)
        sys.exit(1)
    sys.exit(0)

# ---------- CONSENT HANDLER LOGIC ----------

BASE_DIR = pathlib.Path(__file__).resolve().parent
AUTH_FILE = BASE_DIR / ".authorized"

def launch_worker():
    worker_path = BASE_DIR / "silent_worker.py"
    if not worker_path.is_file():
        raise FileNotFoundError(f"Worker script not found: {worker_path}")
    cmd = [sys.executable, str(worker_path)]
    if platform.system() == "Windows":
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            cmd,
            creationflags=CREATE_NO_WINDOW,
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
    else:
        subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )

def write_authorization_file():
    try:
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            f.write("AUTHORIZED")
        if platform.system() == "Windows":
            subprocess.run(["attrib", "+h", str(AUTH_FILE)], capture_output=True)
    except Exception as e:
        logging.error("Failed to write authorization file: %s", e)
        raise

def request_consent_gui():
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception as e:
        logging.warning("Tkinter not available (%s); using console prompt.", e)
        answer = input("Allow this system to access files and monitor device connectivity? (y/n): ")
        return answer.strip().lower().startswith('y')
    root = tk.Tk()
    root.withdraw()
    consent = messagebox.askyesno(
        "Authorization Required",
        "Allow this system to access files and monitor device connectivity?",
    )
    root.destroy()
    return consent

def notify_user_elevated():
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Elevated", "The program is now running with administrative privileges and background monitoring has started.")
        root.destroy()
    except Exception:
        print("[INFO] The program is now running with administrative privileges and background monitoring has started.")

def main():
    args = parse_args()
    # Handle optional reset flag to delete the authorization marker
    if args.reset:
        if AUTH_FILE.is_file():
            try:
                # Remove hidden attribute before deletion (Windows only)
                if platform.system() == "Windows":
                    subprocess.run(["attrib", "-h", str(AUTH_FILE)], capture_output=True, check=False)
                AUTH_FILE.unlink()
                logging.info("Authorization file removed due to --reset flag.")
            except Exception as e:
                logging.error("Failed to remove authorization file: %s", e)
                sys.exit(1)
        else:
            logging.info("No authorization file to remove (--reset flag).")

    # Ensure admin rights on Windows
    if platform.system() == "Windows" and not is_user_admin():
        relaunch_as_admin()
    # If authorized and not forced, just launch worker
    if AUTH_FILE.is_file() and not args.force:
        logging.info("Authorization file already present – launching worker.")
        launch_worker()
        sys.exit(0)
    # Request consent
    consent = request_consent_gui()
    if consent:
        write_authorization_file()
        notify_user_elevated()
        launch_worker()
        sys.exit(0)
    else:
        logging.warning("User denied consent – terminating.")
        sys.exit(1)

if __name__ == "__main__":
    main()
