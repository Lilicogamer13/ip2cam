import subprocess
import tkinter as tk
from tkinter import messagebox
import signal
import os
import sys
import threading

try:
    from PIL import Image, ImageDraw
    import pystray
    from pystray import MenuItem as item
except ImportError:
    print("\n[!] Missing dependencies. Please run:")
    print("pip install pystray pillow\n")
    sys.exit(1)

class VirtualCamApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Linux Virtual Cam")
        self.root.geometry("420x240")
        self.ffmpeg_proc = None
        self.device_id = "10"
        self.device_path = f"/dev/video{self.device_id}"
        self.tray_icon = None

        # UI
        tk.Label(root, text="Stream URL:", font=('Arial', 10, 'bold')).pack(pady=5)
        self.url_entry = tk.Entry(root, width=50)
        self.url_entry.pack(pady=5)
        self.url_entry.insert(0, "http://")

        self.status_label = tk.Label(root, text="Status: Ready", fg="gray")
        self.status_label.pack(pady=2)
        
        self.btn = tk.Button(root, text="Start Camera", command=self.toggle_cam, bg="green", fg="white", width=20)
        self.btn.pack(pady=5)

        self.bg_btn = tk.Button(root, text="Go to Background", command=self.hide_window, bg="#444", fg="white", width=20)
        self.bg_btn.pack(pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        signal.signal(signal.SIGINT, self.signal_handler)

    def run_sudo_cmd(self, cmd_list):
        """Runs a command with sudo, prompting for password in terminal if needed."""
        try:
            # We use 'sudo -S' or just 'sudo' to handle elevation for specific tasks
            subprocess.run(['sudo'] + cmd_list, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def create_icon_image(self):
        image = Image.new('RGB', (64, 64), color=(0, 120, 215))
        d = ImageDraw.Draw(image)
        d.rectangle([16, 16, 48, 48], fill=(255, 255, 255))
        return image

    def hide_window(self):
        self.root.withdraw()
        # Create tray icon
        menu = (item('Show App', self.show_window), item('Exit Entirely', self.on_closing))
        self.tray_icon = pystray.Icon("cam_app", self.create_icon_image(), "Virtual Cam", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.after(0, self.root.deiconify)

    def setup_v4l2(self):
        if not os.path.exists(self.device_path):
            self.status_label.config(text="Status: Authenticating hardware...", fg="blue")
            success = self.run_sudo_cmd(["modprobe", "v4l2loopback", f"video_nr={self.device_id}", 
                                       "card_label=VirtualCam", "exclusive_caps=1"])
            if not success:
                messagebox.showerror("Auth Error", "Failed to load kernel module. Sudo required.")
                return False
        return True

    def get_external_users(self):
        if not os.path.exists(self.device_path): return []
        try:
            # lsof doesn't always need sudo to read, but we'll use it to be sure
            output = subprocess.check_output(['sudo', 'lsof', '-t', self.device_path], text=True)
            pids = output.strip().split('\n')
            my_pid = str(self.ffmpeg_proc.pid) if self.ffmpeg_proc else None
            return [p for p in pids if p != my_pid]
        except: return []

    def stop_all(self):
        if self.ffmpeg_proc:
            self.ffmpeg_proc.terminate()
            self.ffmpeg_proc.wait()
            self.ffmpeg_proc = None
        
        blockers = self.get_external_users()
        if not blockers and os.path.exists(self.device_path):
            self.run_sudo_cmd(["modprobe", "-r", "v4l2loopback"])
            self.status_label.config(text="Status: Device Removed", fg="gray")
        else:
            self.status_label.config(text="Status: Stopped (Device Busy)", fg="orange")
        
        self.btn.config(text="Start Camera", bg="green")

    def toggle_cam(self):
        if self.ffmpeg_proc is None:
            if self.setup_v4l2():
                url = self.url_entry.get().strip()
                # Run ffmpeg as user (no sudo needed for ffmpeg)
                cmd = ['ffmpeg', '-re', '-i', url, '-f', 'v4l2', '-pix_fmt', 'yuyv422', self.device_path]
                self.ffmpeg_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                self.btn.config(text="Stop Camera", bg="red")
                self.status_label.config(text="Status: Streaming Active", fg="green")
        else:
            self.stop_all()

    def on_closing(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.stop_all()
        self.root.destroy()
        os._exit(0)

    def signal_handler(self, sig, frame):
        self.on_closing()

if __name__ == "__main__":
    # IMPORTANT: Run this script as a NORMAL user, NOT with sudo.
    root = tk.Tk()
    app = VirtualCamApp(root)
    root.mainloop()