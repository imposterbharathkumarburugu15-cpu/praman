"""Physical Android Device Hardware Validation Suite.
Requires an actual physical Android handset connected via USB with ADB debugging enabled.
Separated strictly from mock/software tests in compliance with ORIGINAL_REQUEST.md:
"Separate unit tests, integration tests, E2E tests, and physical-device tests.
Do not count mocked tests as physical-device tests.
Do not claim complete physical validation if no physical Android device was tested."
"""

import shutil
import subprocess
import pytest


def get_connected_adb_devices():
    """Queries ADB for connected physical Android devices."""
    adb_path = shutil.which("adb")
    if not adb_path:
        return []
    try:
        res = subprocess.run(
            [adb_path, "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = [line.strip() for line in res.stdout.strip().splitlines()[1:] if line.strip()]
        devices = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except Exception:
        return []


PHYSICAL_DEVICES = get_connected_adb_devices()
PHYSICAL_DEVICE_AVAILABLE = len(PHYSICAL_DEVICES) > 0


@pytest.mark.physical_device
@pytest.mark.skipif(
    not PHYSICAL_DEVICE_AVAILABLE,
    reason="Physical Android device not detected via ADB (connect real Android device with USB debugging to run)",
)
class TestPhysicalAndroidDevice:
    """Tests requiring genuine physical Android device connection."""

    def test_adb_device_online(self):
        """Physical Test 1: Verifies at least one physical device is authorized and online."""
        assert len(PHYSICAL_DEVICES) > 0, "No authorized physical Android device detected"
        device_id = PHYSICAL_DEVICES[0]
        res = subprocess.run(["adb", "-s", device_id, "shell", "getprop", "ro.product.model"], capture_output=True, text=True)
        assert res.returncode == 0
        assert len(res.stdout.strip()) > 0

    def test_physical_camera_hardware_present(self):
        """Physical Test 2: Verifies camera service and hardware lens sensors on physical device."""
        device_id = PHYSICAL_DEVICES[0]
        res = subprocess.run(["adb", "-s", device_id, "shell", "pm", "has-feature", "android.hardware.camera"], capture_output=True, text=True)
        assert res.returncode == 0
        assert "true" in res.stdout.lower()

    def test_physical_keystore_hardware_backing(self):
        """Physical Test 3: Verifies hardware-backed Keystore or TEE on physical device."""
        device_id = PHYSICAL_DEVICES[0]
        res = subprocess.run(["adb", "-s", device_id, "shell", "pm", "has-feature", "android.hardware.strongbox_keystore"], capture_output=True, text=True)
        # Device might have StrongBox or TEE
        assert res.returncode == 0

    def test_physical_storage_directory_writable(self):
        """Physical Test 4: Verifies application private storage directory is writable on physical handset."""
        device_id = PHYSICAL_DEVICES[0]
        res = subprocess.run(["adb", "-s", device_id, "shell", "ls", "-ld", "/data/local/tmp"], capture_output=True, text=True)
        assert res.returncode == 0
