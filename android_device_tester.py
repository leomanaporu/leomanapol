from __future__ import annotations

import re
import subprocess
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    details: str


def parse_devices(output: str) -> list[Device]:
    devices = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[0] == "List" or parts[0].startswith("*"):
            continue
        serial, state = parts[:2]
        if ":" in serial:
            continue
        devices.append(Device(serial, state, " ".join(parts[2:])))
    return devices


def parse_screen_size(output: str) -> tuple[int, int]:
    matches = re.findall(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", output)
    if not matches:
        raise ValueError("ADB did not return a recognized screen size.")
    width, height = matches[-1]
    return int(width), int(height)


def validate_tap(x_text: str, y_text: str, width: int, height: int) -> tuple[int, int]:
    try:
        x, y = int(x_text), int(y_text)
    except ValueError as error:
        raise ValueError("Enter whole-number screen coordinates.") from error
    if width <= 0 or height <= 0 or not (0 <= x < width and 0 <= y < height):
        raise ValueError(f"Coordinates must be within 0..{width - 1} and 0..{height - 1}.")
    return x, y


def capture_screenshot(adb_path: str, serial: str) -> bytes:
    result = subprocess.run(
        [adb_path, "-s", serial, "exec-out", "screencap", "-p"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
        shell=False,
    )
    if result.returncode:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(error or f"ADB screenshot failed with exit code {result.returncode}.")
    if not result.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("ADB returned data that is not a valid PNG screenshot.")
    return result.stdout


class AndroidDeviceTester:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Android Device Tester")
        self.root.geometry("760x660")
        self.root.minsize(620, 520)
        self.root.configure(bg="#101412")

        self.adb_path = tk.StringVar(value="adb")
        self.scrcpy_path = tk.StringVar(value="scrcpy")
        self.device_label = tk.StringVar()
        self.coordinates = tk.StringVar(value="0, 0")
        self.device_map: dict[str, Device] = {}
        self.selected_device: Device | None = None
        self.screen_size: tuple[int, int] | None = None
        self.scrcpy_process: subprocess.Popen | None = None

        self._configure_styles()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#101412")
        style.configure("Panel.TFrame", background="#171d1a")
        style.configure("TLabel", background="#101412", foreground="#e6eee9", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground="#9baaa1")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 19), foreground="#f1f5f2")
        style.configure("Section.TLabel", background="#171d1a", font=("Segoe UI Semibold", 11), foreground="#d9e5dd")
        style.configure("TButton", padding=(12, 8), font=("Segoe UI", 10))
        style.configure("Accent.TButton", background="#a8d5b5", foreground="#111814", font=("Segoe UI Semibold", 10))
        style.map("Accent.TButton", background=[("active", "#c2e5ca")])
        style.configure("TEntry", fieldbackground="#0e1310", foreground="#f1f5f2", insertcolor="#f1f5f2")
        style.configure("TCombobox", fieldbackground="#0e1310", foreground="#f1f5f2", arrowcolor="#e6eee9")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=22)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="ANDROID DEVICE TESTER", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Local USB debugging · explicit device selection · no network connections",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 18))

        tools = ttk.Frame(outer, style="Panel.TFrame", padding=14)
        tools.pack(fill="x", pady=(0, 12))
        ttk.Label(tools, text="LOCAL TOOLS", style="Section.TLabel").grid(row=0, column=0, sticky="w", columnspan=3, pady=(0, 10))
        ttk.Label(tools, text="ADB executable", style="Section.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 12))
        ttk.Entry(tools, textvariable=self.adb_path).grid(row=1, column=1, sticky="ew")
        ttk.Button(tools, text="Browse", command=self.choose_adb).grid(row=1, column=2, padx=(8, 0))
        ttk.Label(tools, text="scrcpy executable", style="Section.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=(8, 0))
        ttk.Entry(tools, textvariable=self.scrcpy_path).grid(row=2, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(tools, text="Browse", command=self.choose_scrcpy).grid(row=2, column=2, padx=(8, 0), pady=(8, 0))
        tools.columnconfigure(1, weight=1)

        device_panel = ttk.Frame(outer, style="Panel.TFrame", padding=14)
        device_panel.pack(fill="x", pady=(0, 12))
        ttk.Label(device_panel, text="CONNECTED DEVICE", style="Section.TLabel").grid(row=0, column=0, sticky="w", columnspan=3, pady=(0, 10))
        self.device_combo = ttk.Combobox(device_panel, textvariable=self.device_label, state="readonly")
        self.device_combo.grid(row=1, column=0, sticky="ew")
        self.device_combo.bind("<<ComboboxSelected>>", self.on_device_selected)
        ttk.Button(device_panel, text="Refresh", command=self.refresh_devices).grid(row=1, column=1, padx=(8, 0))
        ttk.Button(device_panel, text="Read screen size", command=self.read_screen_size).grid(row=1, column=2, padx=(8, 0))
        device_panel.columnconfigure(0, weight=1)

        actions = ttk.Frame(outer, style="Panel.TFrame", padding=14)
        actions.pack(fill="x", pady=(0, 12))
        ttk.Label(actions, text="TEST ACTIONS", style="Section.TLabel").grid(row=0, column=0, sticky="w", columnspan=4, pady=(0, 10))
        ttk.Label(actions, text="Tap coordinates (x, y)", style="Section.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Entry(actions, textvariable=self.coordinates, width=18).grid(row=1, column=1, sticky="w", padx=(8, 12))
        ttk.Button(actions, text="Send tap", style="Accent.TButton", command=self.send_tap).grid(row=1, column=2, sticky="w")
        ttk.Button(actions, text="View screen in scrcpy", command=self.open_scrcpy).grid(row=2, column=0, columnspan=3, sticky="w", pady=(12, 0))
        ttk.Button(actions, text="Capture screenshot to PC", command=self.save_screenshot).grid(row=2, column=3, sticky="e", pady=(12, 0))

        self.status = tk.StringVar(value="Choose the ADB executable, then refresh to find USB-connected devices.")
        ttk.Label(outer, textvariable=self.status, style="Muted.TLabel", wraplength=700).pack(anchor="w", pady=(0, 10))

        log_panel = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        log_panel.pack(fill="both", expand=True)
        ttk.Label(log_panel, text="ACTIVITY", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self.log = tk.Text(log_panel, height=8, wrap="word", bg="#0e1310", fg="#cbd8cf", insertbackground="#f1f5f2", relief="flat", padx=10, pady=8, font=("Consolas", 10), state="disabled")
        self.log.pack(fill="both", expand=True)
        self._log("Ready. USB debugging must be enabled and authorized on the device.")

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _run_adb(self, arguments: list[str], timeout: int = 12) -> str:
        result = subprocess.run(
            [self.adb_path.get().strip(), *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
        if result.returncode:
            details = result.stderr.strip() or result.stdout.strip() or f"Exit code {result.returncode}"
            raise RuntimeError(details)
        return result.stdout

    def choose_adb(self) -> None:
        selected = filedialog.askopenfilename(title="Select Android Debug Bridge", filetypes=[("ADB executable", "adb.exe"), ("All files", "*.*")])
        if selected:
            self.adb_path.set(selected)

    def choose_scrcpy(self) -> None:
        selected = filedialog.askopenfilename(title="Select scrcpy", filetypes=[("scrcpy executable", "scrcpy.exe"), ("All files", "*.*")])
        if selected:
            self.scrcpy_path.set(selected)

    def refresh_devices(self) -> None:
        try:
            devices = parse_devices(self._run_adb(["devices", "-l"]))
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            self.status.set(f"Could not query ADB: {error}")
            self._log(f"ADB error: {error}")
            return

        self.device_map.clear()
        labels = []
        for device in devices:
            label = f"{device.serial}  [{device.state}]  {device.details}".strip()
            self.device_map[label] = device
            labels.append(label)
        self.device_combo.configure(values=labels)
        self.device_label.set(labels[0] if labels else "")
        self.selected_device = None
        self.screen_size = None
        if labels:
            self.device_combo.current(0)
            self.on_device_selected()
        else:
            self.status.set("No USB-connected Android device found. Network-style serials are filtered out.")
            self._log("No USB device detected.")

    def on_device_selected(self, _event: tk.Event | None = None) -> None:
        self.selected_device = self.device_map.get(self.device_label.get())
        self.screen_size = None
        if self.selected_device and self.selected_device.state == "device":
            self.status.set(f"Selected {self.selected_device.serial}. Read screen size before sending taps.")
        elif self.selected_device:
            self.status.set(f"{self.selected_device.serial} reports '{self.selected_device.state}'. Unlock it and approve the USB debugging prompt, then refresh.")

    def _require_ready_device(self) -> Device:
        device = self.selected_device
        if not device or device.state != "device":
            raise RuntimeError("Select an authorized USB device first. Approve its USB debugging prompt and refresh.")
        return device

    def read_screen_size(self) -> None:
        try:
            device = self._require_ready_device()
            output = self._run_adb(["-s", device.serial, "shell", "wm", "size"])
            self.screen_size = parse_screen_size(output)
            self.status.set(f"Screen size: {self.screen_size[0]} × {self.screen_size[1]} pixels.")
            self._log(f"Read screen size for {device.serial}: {self.screen_size[0]}x{self.screen_size[1]}")
        except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as error:
            self.status.set(str(error))
            self._log(f"Screen-size error: {error}")

    def send_tap(self) -> None:
        try:
            device = self._require_ready_device()
            if self.screen_size is None:
                raise RuntimeError("Read the selected device's screen size before tapping.")
            pieces = [piece.strip() for piece in self.coordinates.get().split(",")]
            if len(pieces) != 2:
                raise ValueError("Enter coordinates as x, y.")
            x, y = validate_tap(*pieces, *self.screen_size)
            self._run_adb(["-s", device.serial, "shell", "input", "tap", str(x), str(y)])
            self._log(f"Tap sent to {device.serial} at ({x}, {y}).")
            self.status.set(f"Tap sent at ({x}, {y}).")
        except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as error:
            self.status.set(str(error))
            self._log(f"Tap not sent: {error}")

    def save_screenshot(self) -> None:
        device = self.selected_device
        if not device or device.state != "device":
            self.status.set("Select an authorized USB device before capturing a screenshot.")
            return

        filename = f"android-screenshot-{datetime.now():%Y%m%d-%H%M%S}.png"
        output_path = filedialog.asksaveasfilename(
            title="Save screenshot on this PC",
            initialfile=filename,
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
        )
        if not output_path:
            return

        try:
            image_data = capture_screenshot(self.adb_path.get().strip(), device.serial)
            Path(output_path).write_bytes(image_data)
            self.status.set(f"Screenshot saved on this PC: {output_path}")
            self._log(f"Captured {len(image_data):,} PNG bytes from {device.serial} to local file {output_path}.")
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            self.status.set(f"Screenshot failed: {error}")
            self._log(f"Screenshot failed: {error}")

    def open_scrcpy(self) -> None:
        try:
            device = self._require_ready_device()
            if self.scrcpy_process and self.scrcpy_process.poll() is None:
                raise RuntimeError("A scrcpy viewer is already running from this dashboard.")
            self.scrcpy_process = subprocess.Popen(
                [self.scrcpy_path.get().strip(), "--serial", device.serial, "--no-audio"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
            self.status.set(f"Started scrcpy for {device.serial}. Close its window to end screen viewing.")
            self._log(f"Started local scrcpy viewer for {device.serial}.")
        except (OSError, RuntimeError) as error:
            self.status.set(str(error))
            self._log(f"Could not start scrcpy: {error}")

    def close(self) -> None:
        if self.scrcpy_process and self.scrcpy_process.poll() is None:
            self.scrcpy_process.terminate()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AndroidDeviceTester(root)
    root.mainloop()


if __name__ == "__main__":
    main()