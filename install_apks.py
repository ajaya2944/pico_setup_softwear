import subprocess
import os

# Define the path to adb (adjust as needed)
adb_path = "adb"  # Or "C:\\platform-tools\\adb.exe"

def uninstall_apk(package_name, callback=None):
    """Uninstall an APK by package name with optional GUI callback."""
    message = f"Uninstalling {package_name}..."
    if callback:
        callback(message)
    
    result = subprocess.run(
        [adb_path, "uninstall", package_name],
        capture_output=True,
        text=True
    )
    
    output = result.stdout.strip()
    if "Success" in output:
        message = f"Success: {package_name} uninstalled"
    elif "not installed" in output:
        message = f"Note: {package_name} not installed"
    else:
        message = f"Uninstall output: {output}"
    
    if callback:
        callback(message)
    return message

def install_apk(apk_file, callback=None):
    """Install an APK with optional GUI callback."""
    message = f"Installing {apk_file}..."
    if callback:
        callback(message)
    
    result = subprocess.run(
        [adb_path, "install", "-r", "-t", apk_file],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        message = f"Success: {apk_file} installed"
    else:
        message = f"Failed to install {apk_file}: {result.stderr.strip()}"
    
    if callback:
        callback(message)
    return message

def process_apks(apk_list, callback=None):
    """Process a list of APKs (uninstall then install each)."""
    for apk_info in apk_list:
        # Uninstall first
        uninstall_result = uninstall_apk(apk_info["package"], callback)
        
        # Then install
        install_result = install_apk(apk_info["file"], callback)
    
    return "APK processing complete"

# ✅ Add this missing function to be used by pico_setup.py
def run_install_process(callback=None):
    """Main function that runs installation process for default APKs."""
    apk_list = [
        {"package": "az.osmdroidprop", "file": "apk/tukpy_rev_27004.apk"},
        {"package": "net.openvpn.openvpn", "file": "apk/OpenVPN.apk"},
        # Add more APKs as needed
    ]

    if callback:
        callback("Starting APK installation process...")

    process_apks(apk_list, callback)

    if callback:
        callback("Installation process finished.")
