from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "Application" / "frontend"
ATLAS_ENTRYPOINT = PROJECT_ROOT / "atlas.py"


class AtlasProcess:
    """Owns the Atlas subprocess and publishes its output to connected UIs."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._status = "stopped"
        self._logs: deque[str] = deque(maxlen=500)
        self._subscribers: dict[asyncio.Queue[dict[str, Any]], asyncio.AbstractEventLoop] = {}
        self._lock = threading.RLock()

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            process = self._process
            return {
                "status": self._status,
                "running": process is not None and process.poll() is None,
                "logs": list(self._logs),
            }

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return self.snapshot()

            environment = os.environ.copy()
            environment["PYTHONUNBUFFERED"] = "1"
            environment["PYTHONIOENCODING"] = "utf-8"
            self._process = subprocess.Popen(
                [sys.executable, str(ATLAS_ENTRYPOINT)],
                cwd=PROJECT_ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            self._status = "starting"
            self._publish_locked("[APP] Atlas process started.")
            threading.Thread(target=self._read_output, daemon=True).start()
            return self.snapshot()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            process = self._process
            if process is None or process.poll() is not None:
                self._status = "stopped"
                return self.snapshot()
            self._status = "stopping"
            self._publish_locked("[APP] Stop requested.")

        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

        with self._lock:
            self._status = "stopped"
            self._publish_locked("[APP] Atlas process stopped.")
            return self.snapshot()

    def subscribe(self) -> tuple[asyncio.Queue[dict[str, Any]], asyncio.AbstractEventLoop]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        with self._lock:
            self._subscribers[queue] = loop
        return queue, loop

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers.pop(queue, None)

    def _read_output(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return

        for line in process.stdout:
            text = line.rstrip()
            with self._lock:
                self._status = self._status_for_log(text, self._status)
                self._publish_locked(text)

        process.wait()
        with self._lock:
            if self._status not in {"stopping", "stopped"}:
                self._status = "error" if process.returncode else "stopped"
                self._publish_locked(
                    f"[APP] Atlas exited with code {process.returncode}."
                )

    def _publish_locked(self, text: str) -> None:
        event = {"type": "log", "status": self._status, "message": text}
        self._logs.append(text)
        for queue, loop in list(self._subscribers.items()):
            loop.call_soon_threadsafe(queue.put_nowait, event)

    @staticmethod
    def _status_for_log(message: str, current: str) -> str:
        if "EARS are listening" in message or message.startswith("[Ears]"):
            return "listening"
        if "BRAIN is thinking" in message or message.startswith("[Brain]"):
            return "thinking"
        if "MOUTH is speaking" in message or message.startswith("[Mouth]"):
            return "speaking"
        if "tool" in message.lower():
            return "working"
        if "Critical Fault" in message or "Traceback" in message:
            return "error"
        if "offline" in message.lower():
            return "stopped"
        return current


app = FastAPI(title="Atlas Local Application")
atlas = AtlasProcess()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_ROOT / "index.html")


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(FRONTEND_ROOT / "styles.css", media_type="text/css")


@app.get("/app.js")
def script() -> FileResponse:
    return FileResponse(FRONTEND_ROOT / "app.js", media_type="text/javascript")


@app.get("/api/status")
def status() -> dict[str, Any]:
    return atlas.snapshot()


@app.post("/api/start")
def start() -> dict[str, Any]:
    return atlas.start()


@app.post("/api/stop")
def stop() -> dict[str, Any]:
    return atlas.stop()


@app.websocket("/ws/logs")
async def logs(websocket: WebSocket) -> None:
    await websocket.accept()
    queue, _ = atlas.subscribe()
    try:
        await websocket.send_text(json.dumps({"type": "snapshot", **atlas.snapshot()}))
        while True:
            await websocket.send_text(json.dumps(await queue.get()))
    except WebSocketDisconnect:
        pass
    finally:
        atlas.unsubscribe(queue)
