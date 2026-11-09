# Android Device Tester

This is a local Windows desktop utility for testing Android devices connected by USB. It uses Python's built-in Tkinter UI and does not install Python packages, start a network server, or enable wireless ADB.

## Setup

1. Install Google's Android SDK Platform-Tools and note the location of `adb.exe`.
2. Install scrcpy from its official project release and note the location of `scrcpy.exe` if you want the screen-view window.
3. On the Android device, enable Developer options and USB debugging.
4. Connect the device over USB, unlock it, and approve the Android prompt to allow USB debugging from this computer.
5. Run `android_device_tester.py` with Python 3.10 or newer. If `python` is not on PATH, use the full path to your Python executable.
6. Browse to `adb.exe`, select **Refresh**, choose an authorized device, and select **Read screen size** before sending a tap.

## Included actions

- List attached ADB devices and select one explicitly. Network-style serials containing `:` are excluded.
- Read the selected device's reported screen size.
- Send a single tap only when integer coordinates are inside that screen's bounds.
- Capture a PNG directly from the selected device and save it to a chosen path on this PC.
- Open the selected device in scrcpy's own viewer window with audio disabled.

Screenshot capture uses `adb -s <serial> exec-out screencap -p` with binary stdout piped into the desktop process. The PNG bytes are validated and written to the PC path selected in the save dialog; no screenshot file is created on Android storage. Other ADB operations use argument-list process launches with shell execution disabled. The UI does not accept arbitrary shell commands. Android USB debugging authorization remains under the device owner's control. Close the tester to stop a scrcpy process it launched.

## Limits

The screen viewer is a separate scrcpy window, not embedded in this dashboard. The tool is intended for local, authorized USB testing; it does not use `adb connect`, remote-control services, or device-file browsing.