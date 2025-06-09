import subprocess
import time
import sys
import os
import re
from datetime import datetime
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
from install_apks import uninstall_apk, install_apk, process_apks, run_install_process


class PicoSetupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pico Device Setup Automation")
        self.root.geometry("700x500")
        
        # IP address entry
        tk.Label(root, text="Device IP Address:").pack(anchor='w', padx=10, pady=(10,0))
        self.entry_ip = tk.Entry(root, width=30)
        self.entry_ip.pack(anchor='w', padx=10)
        
        # Buttons
        self.btn_start = tk.Button(root, text="Start Setup", command=self.start_process)
        self.btn_start.pack(pady=10)
        
        # Log area
        self.txt_log = scrolledtext.ScrolledText(root, state='normal', width=85, height=25, wrap='word')
        self.txt_log.pack(padx=10, pady=10, fill='both', expand=True)
        
        # Initial message
        self.log("Welcome to Pico Device Setup Automation.\nEnter the device IP and click 'Start Setup' to begin.\n")

    def log(self, message):
        """Thread-safe logging to the GUI."""
        self.txt_log.configure(state='normal')
        self.txt_log.insert(tk.END, message + '\n')
        self.txt_log.see(tk.END)
        self.txt_log.configure(state='disabled')
        self.root.update_idletasks()

    def validate_ip(self, ip):
        """Validate IPv4 format using regex."""
        pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        return re.match(pattern, ip) is not None

    def run_adb_command(self, command, timeout=30):
        """Run adb command and return output or None on failure."""
        try:
            result = subprocess.run(['adb'] + command,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 text=True,
                                 timeout=timeout,
                                 check=True)
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            self.log(f"Command timed out after {timeout} seconds: {' '.join(command)}")
            return None
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {' '.join(command)}\nError: {e.stderr.strip()}")
            return None

    def mount_system_rw(self, serial=None):
        """Mount /system partition as read-write."""
        self.log("\nMounting /system as read-write...")
        base_command = ['shell', 'su', '-c', 'mount -o rw,remount /system']
        if serial:
            base_command = ['-s', serial] + base_command

        result = self.run_adb_command(base_command)
        if result is None:
            self.log("Failed to remount /system as read-write")
            return False
        self.log("Successfully mounted /system as read-write")
        return True

    def connect_device(self, ip, port=5555, max_retries=5, delay=5):
        """Attempt to connect to the device via adb over network."""
        for attempt in range(1, max_retries + 1):
            self.log(f"\nConnection attempt {attempt} of {max_retries} to {ip}:{port}...")
            self.run_adb_command(['disconnect'], timeout=5)
            result = self.run_adb_command(['connect', f"{ip}:{port}"])
            if result and "connected" in result:
                devices = self.run_adb_command(['devices'])
                if devices and f"{ip}:{port}" in devices:
                    self.log("Connection successful!")
                    return True
            self.log(f"Connection failed. Retrying in {delay} seconds...")
            time.sleep(delay)
        self.log(f"Failed to connect to {ip} after {max_retries} attempts")
        return False

    def verify_files_exist(self, script_dir):
        """Check required files exist on device."""
        required_files = [
            '1_Kandel_setup.sh',
            '2_Kandel_setup.sh',
            'dev900.ovpn',
            'debian_stretch_rootfs_release_20200309.tgz'
        ]
        self.log("\nVerifying required files on device...")
        missing_files = []

        dir_check = self.run_adb_command(['shell', f'[ -d "{script_dir}" ] && echo "exists"'])
        if dir_check != "exists":
            self.log(f"Directory not found: {script_dir}")
            return False

        for file in required_files:
            file_path = os.path.join(script_dir, file).replace('\\', '/')
            res = self.run_adb_command(['shell', f'[ -f "{file_path}" ] && echo "exists"'])
            if res == "exists":
                self.log(f"Found: {file}")
            else:
                self.log(f"Missing: {file}")
                missing_files.append(file)

        if missing_files:
            self.log("\nMissing required files:")
            for file in missing_files:
                self.log(f"- {file}")
            return False

        self.log("All required files found.")
        return True

    def execute_script(self, script_name, script_dir, ip, max_retries=3):
        """Run a shell script on device as root with reconnection handling."""
        attempt = 1
        while attempt <= max_retries:
            self.log(f"\nExecuting {script_name} (Attempt {attempt} of {max_retries})...")
            start = datetime.now()
            self.log(f"Start time: {start.strftime('%H:%M:%S')}")

            cmd = f"su -c 'cd {script_dir} && sh {script_name}'"
            self.log(f"Running command: adb shell {cmd}")

            try:
                timeout = 600 if script_name == "1_Kandel_setup.sh" else 300
                result = subprocess.run(['adb', 'shell', cmd],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     text=True,
                                     timeout=timeout,
                                     check=True)
                
                output = result.stdout.strip()
                self.log("\nScript output:\n" + "-" * 60)
                self.log(output)
                self.log("-" * 60)

                if "END Kandel SETUP" not in output:
                    self.log(f"Warning: {script_name} may not have completed successfully.")

                error_keywords = ["No such file", "can't open", "Permission denied"]
                if any(err in output for err in error_keywords):
                    self.log(f"Errors detected in {script_name} output.")
                    return False

                end = datetime.now()
                duration = (end - start).total_seconds()
                self.log(f"Execution time: {duration:.2f} seconds")
                self.log(f"End time: {end.strftime('%H:%M:%S')}")
                return True

            except subprocess.TimeoutExpired:
                self.log(f"Error: {script_name} timed out.")
                attempt += 1
                if attempt <= max_retries:
                    self.log("Waiting 10 seconds before retrying...")
                    time.sleep(10)
                continue
                
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.strip()
                self.log(f"Error executing {script_name}:\n{error_msg}")
                
                if "device offline" in error_msg.lower():
                    self.log("Device went offline during execution. Attempting to reconnect...")
                    if not self.reboot_device_and_wait(ip):
                        self.log("Failed to reconnect to device.")
                        return False
                    attempt += 1
                    continue
                    
                return False

        self.log(f"Failed to execute {script_name} after {max_retries} attempts")
        return False

    def reboot_device_and_wait(self, ip, reboot_timeout=60, connect_timeout=300):
        """Reboot device and wait until it reconnects."""
        self.log("\nRebooting device...")
        reboot_result = self.run_adb_command(['reboot'], timeout=reboot_timeout)
        if reboot_result is None:
            self.log("Warning: adb reboot command failed or timed out.")

        self.log("Waiting for device to go offline...")
        start_time = time.time()
        device_offline = False

        while time.time() - start_time < connect_timeout:
            try:
                devices_output = subprocess.run(['adb', 'devices'],
                                              capture_output=True, text=True, check=True, timeout=10).stdout
                if f"{ip}:5555\toffline" in devices_output or f"{ip}:5555" not in devices_output:
                    self.log("Device offline detected. Waiting for reconnection...")
                    device_offline = True
                    break
            except Exception:
                self.log("ADB command error, assuming device is rebooting...")
                device_offline = True
                break
            time.sleep(5)

        if not device_offline:
            self.log("Timeout waiting for device to go offline.")
            return False

        self.log("Waiting for device to reconnect...")
        while time.time() - start_time < connect_timeout:
            if self.connect_device(ip, max_retries=1, delay=2):
                self.log("Device reconnected successfully.")
                return True
            time.sleep(5)

        self.log("Timeout waiting for device to reconnect.")
        return False

    def run_setup_process(self, ip):
        try:
            device_serial = f"{ip}:5555"

            # Step 1: Connect to device
            if not self.connect_device(ip):
                self.show_error_and_reset("Connection Failed", f"Could not connect to device at {ip}")
                return

            # Show OTG cable removal message right after successful connection
            self.root.after(0, lambda: messagebox.showinfo(
                "Connection Successful", 
                "Connection to device was successful!\nPlease remove the OTG cable before proceeding."
            ))
            
            # Step 2: Mount /system FIRST
            self.log("\n=== Mounting /system as read-write ===")
            if not self.mount_system_rw(serial=device_serial):
                self.show_error_and_reset("Mount Failed", "Failed to mount /system as read-write")
                return

            # Step 3: Run APK installations AFTER mounting
            self.log("\n=== Starting APK installations ===")
            run_install_process(self.log)  # This uses the callback to log messages
                
            script_dir = "/mnt/media_rw/40F465C7F465C030/Akiba_new_setup"

            # Step 4: Verify files
            if not self.verify_files_exist(script_dir):
                self.show_error_and_reset("File Check Failed", "Required files missing on device.\nPlease check the directory and files.")
                return

            # Rest of the setup process remains the same...
            # Step 5: Execute 1st script
            if not self.execute_script("1_Kandel_setup.sh", script_dir, ip):
                self.show_error_and_reset("Script Failed", "First setup script failed. Aborting.")
                return

            # Step 6: Reboot
            if not self.reboot_device_and_wait(ip):
                self.show_error_and_reset("Reboot Failed", "Device did not reboot and reconnect successfully.")
                return

            # Step 7: Execute 2nd script
            if not self.execute_script("2_Kandel_setup.sh", script_dir, ip):
                self.show_error_and_reset("Script Failed", "Second setup script failed.")
                return

            self.show_info_and_reset("Setup Complete", "Device setup process finished successfully.\nPlease verify device status manually.")
            self.log("\n=== Setup process finished ===")

        except Exception as e:
            self.log(f"Unexpected error: {str(e)}")
            self.show_error_and_reset("Error", f"An unexpected error occurred: {str(e)}")

    def show_error_and_reset(self, title, message):
        """Show error message and reset UI."""
        self.root.after(0, lambda: messagebox.showerror(title, message))
        self.root.after(0, lambda: self.btn_start.config(state='normal'))

    def show_info_and_reset(self, title, message):
        """Show info message and reset UI."""
        self.root.after(0, lambda: messagebox.showinfo(title, message))
        self.root.after(0, lambda: self.btn_start.config(state='normal'))

    def start_process(self):
        """Start the setup process."""
        ip = self.entry_ip.get().strip()
        if not self.validate_ip(ip):
            messagebox.showerror("Invalid IP", "Please enter a valid IP address (e.g., 192.168.1.100).")
            return

        self.btn_start.config(state='disabled')
        self.log(f"\n=== Starting setup for device {ip} ===")

        # Run the process in a separate thread
        threading.Thread(target=self.run_setup_process, args=(ip,), daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = PicoSetupApp(root)
    root.mainloop()