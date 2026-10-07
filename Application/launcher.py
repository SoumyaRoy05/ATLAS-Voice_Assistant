from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8765
BASE_URL = f"http://{HOST}:{PORT}"


def backend_is_ready() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/status", timeout=1):
            return True
    except (OSError, urllib.error.URLError):
        return False


def start_backend() -> subprocess.Popen[bytes] | None:
    if backend_is_ready():
        print("[Launcher] Reusing the running Atlas backend.", flush=True)
        return None

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "Application.backend.server:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
    ]
    server: subprocess.Popen[bytes] = subprocess.Popen(command, cwd=PROJECT_ROOT)

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(
                f"The Atlas backend exited before startup (code {server.returncode})."
            )
        if backend_is_ready():
            return server
        time.sleep(0.25)

    server.terminate()
    raise TimeoutError("The Atlas backend did not become ready within 30 seconds.")


def main() -> None:
    server = start_backend()
    print(f"[Launcher] Atlas interface: {BASE_URL}", flush=True)
    webbrowser.open(BASE_URL)

    if server is None:
        return

    try:
        print("[Launcher] Backend is running. Press Ctrl+C to close it.", flush=True)
        server.wait()
    except KeyboardInterrupt:
        print("\n[Launcher] Shutting down the Atlas backend.", flush=True)
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    main()
