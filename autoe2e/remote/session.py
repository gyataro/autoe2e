import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import IO, Self

from autoe2e.logger import logger

DISPLAY_NUMBER = 99
DISPLAY_SIZE = "1440x900x24"
VNC_PORT = 5900
NOVNC_PORT = 6080
STARTUP_TIMEOUT_SECONDS = 5.0
NOVNC_WEB_ROOTS = (Path("/usr/share/novnc"), Path("/usr/local/share/novnc"))


class RemoteSession:
    """Own the virtual display, VNC server, and noVNC proxy for one crawl."""

    def __init__(self, log_dir: Path, bind_host: str):
        self.log_dir = log_dir
        self.bind_host = bind_host
        self.display = f":{DISPLAY_NUMBER}"
        self._processes: list[subprocess.Popen] = []
        self._logs: list[IO[bytes]] = []
        self._closed = False

    @classmethod
    def start(cls, log_dir: Path) -> Self:
        bind_host = "0.0.0.0" if os.getenv("AUTOE2E_CONTAINER") == "1" else "127.0.0.1"
        session = cls(log_dir, bind_host)
        try:
            session._start()
        except Exception:
            session.close()
            raise
        return session

    @property
    def viewer_url(self) -> str:
        return f"http://127.0.0.1:{NOVNC_PORT}/vnc.html?autoconnect=true&resize=scale"

    def close(self) -> None:
        if self._closed:
            return
        for process in reversed(self._processes):
            if process.poll() is not None:
                continue
            try:
                process.terminate()
            except ProcessLookupError:
                continue
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except ProcessLookupError:
                    continue
                process.wait(timeout=3)
        for log_file in self._logs:
            log_file.close()
        self._closed = True

    def _start(self) -> None:
        xvfb = _require_executable("Xvfb")
        x11vnc = _require_executable("x11vnc")
        websockify = _require_executable("websockify")
        novnc_root = _find_novnc_root()

        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_port_available(VNC_PORT)
        self._ensure_port_available(NOVNC_PORT)

        logger.info(f"Starting remote browser display {self.display}")
        self._spawn(
            "xvfb",
            [
                xvfb,
                self.display,
                "-screen",
                "0",
                DISPLAY_SIZE,
                "-nolisten",
                "tcp",
            ],
        )
        self._wait_for_display()

        self._spawn(
            "x11vnc",
            [
                x11vnc,
                "-display",
                self.display,
                "-localhost",
                "-forever",
                "-shared",
                "-nopw",
                "-rfbport",
                str(VNC_PORT),
            ],
        )
        self._wait_for_port(VNC_PORT, "x11vnc")

        self._spawn(
            "novnc",
            [
                websockify,
                "--web",
                str(novnc_root),
                f"{self.bind_host}:{NOVNC_PORT}",
                f"127.0.0.1:{VNC_PORT}",
            ],
        )
        self._wait_for_port(NOVNC_PORT, "noVNC")
        logger.info(f"Remote browser ready at {self.viewer_url}")
        logger.info(
            f"From your computer, tunnel it with: "
            f"ssh -N -L {NOVNC_PORT}:127.0.0.1:{NOVNC_PORT} <user>@<server>"
        )

    def _spawn(self, name: str, command: list[str]) -> None:
        log_file = (self.log_dir / f"{name}.log").open("ab")
        self._logs.append(log_file)
        process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
        self._processes.append(process)

    def _wait_for_display(self) -> None:
        socket_path = Path(f"/tmp/.X11-unix/X{DISPLAY_NUMBER}")
        self._wait_until(lambda: socket_path.exists(), "Xvfb")

    def _wait_for_port(self, port: int, name: str) -> None:
        def accepting_connections() -> bool:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    return True
            except OSError:
                return False

        self._wait_until(accepting_connections, name)

    def _wait_until(self, ready, name: str) -> None:
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            failed = next(
                (process for process in self._processes if process.poll() is not None), None
            )
            if failed is not None:
                raise RuntimeError(f"{name} failed to start; inspect logs under {self.log_dir}")
            if ready():
                return
            time.sleep(0.05)
        raise RuntimeError(f"Timed out waiting for {name}; inspect logs under {self.log_dir}")

    @staticmethod
    def _ensure_port_available(port: int) -> None:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                pass
        except OSError:
            return
        raise RuntimeError(f"Remote browser port {port} is already in use")


def _require_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise RuntimeError(
            f"Remote browser requires {name}; use the AutoE2E Docker image or install "
            "Xvfb, x11vnc, noVNC, and websockify"
        )
    return executable


def _find_novnc_root() -> Path:
    for root in NOVNC_WEB_ROOTS:
        if (root / "vnc.html").is_file():
            return root
    raise RuntimeError(
        "Remote browser requires noVNC web assets; use the AutoE2E Docker image or "
        "install the noVNC package"
    )
