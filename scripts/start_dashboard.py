"""Start the local dashboard detached from the Ubuntu terminal."""
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8501"


def listening():
    try:
        with socket.create_connection(("127.0.0.1", 8501), timeout=1):
            return True
    except OSError:
        return False


def main():
    if sys.platform != "linux":
        print("Run this launcher in your Ubuntu/WSL terminal.")
        return 1
    import fcntl
    directory = ROOT / "reports"
    directory.mkdir(exist_ok=True)
    with (directory / "dashboard-start.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if listening():
            print(f"Port 8501 is already in use. Open {URL}.")
            print("If this is your foreground dashboard, stop it with Ctrl+C first, then run this launcher again.")
            return 0
        log_path = directory / "dashboard-server.log"
        with log_path.open("ab") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", str(ROOT / "dashboard.py"),
                 "--server.address", "127.0.0.1", "--server.port", "8501",
                 "--server.headless", "true"],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True,
            )
        for _ in range(30):
            if process.poll() is not None:
                print(f"Dashboard startup failed. See {log_path}")
                return 1
            try:
                with urlopen(URL + "/_stcore/health", timeout=1) as response:
                    if response.status == 200 and response.read() == b"ok":
                        print(f"Dashboard running in the background: {URL}")
                        print(f"PID: {process.pid}. To stop this server: kill {process.pid}")
                        print("You can now use this terminal. WSL shutdown or a Windows restart stops the server.")
                        return 0
            except OSError:
                pass
            time.sleep(1)
        print(f"Dashboard is still starting (PID {process.pid}). Check {log_path} and {URL}.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
