"""term.py — the PTY session host.

Spec file mapping: this module is the twist's replacement for `lib/tmux.sh`.
Where the original drove a dedicated `tmux -L balamba` server (windows, panes,
chrome, mouse), this manager owns *plain terminal sessions* directly:
``os.forkpty`` children on Linux, each with its own reader thread.  Nothing
about the interface lives here — only process and fd mechanics.  (README.md,
"Server reinterpretation".)
"""

from __future__ import annotations

import fcntl
import os
import signal
import struct
import subprocess
import sys
import threading
import time

try:
    import pty as _pty_mod
except ImportError:  # pragma: no cover - Windows unsupported per spec
    _pty_mod = None


class PtySession:
    """One hosted terminal session: a PTY + child process + reader thread."""

    def __init__(self,
                 command: str,
                 cwd: str,
                 cols: int = 80,
                 rows: int = 24,
                 env: dict[str, str] | None = None) -> None:
        self.command = command
        self.cwd = cwd
        self.cols = cols
        self.rows = rows
        self.fd: int | None = None
        self.pid: int | None = None
        self._proc: subprocess.Popen | None = None
        self.exit_code: int | None = None
        self.started_at = time.time()
        self.env_overrides = env or {}
        self.on_data = None      # callable(bytes) — invoked from reader thread
        self.on_exit = None      # callable(int)  — invoked from reader thread
        self._thread: threading.Thread | None = None
        self._closed = False
        self._early = bytearray()
        self._early_exit: int | None = None
        self._cb_lock = threading.Lock()

    # -- callbacks (thread-safe, with early-delivery replay) -------------------
    @property
    def on_data(self):
        return self.__dict__.get("_on_data_cb")

    @on_data.setter
    def on_data(self, cb):
        self._on_data_cb = cb
        if cb is not None:
            with self._cb_lock:
                if self._early:
                    data = bytes(self._early)
                    self._early.clear()
                    cb(data)

    @property
    def on_exit(self):
        return self.__dict__.get("_on_exit_cb")

    @on_exit.setter
    def on_exit(self, cb):
        self._on_exit_cb = cb
        if cb is not None:
            with self._cb_lock:
                if self._early_exit is not None:
                    code = self._early_exit
                    self._early_exit = None
                    cb(code)

    def _emit_data(self, data: bytes) -> None:
        cb = self.on_data
        if cb is None:
            with self._cb_lock:
                self._early.extend(data)
            return
        cb(data)

    def _emit_exit(self, code: int) -> None:
        cb = self.on_exit
        if cb is None:
            with self._cb_lock:
                self._early_exit = code
            return
        cb(code)

    # -- lifecycle -----------------------------------------------------------
    def spawn(self) -> None:
        if not pty_available():  # pragma: no cover
            raise RuntimeError("pty is unavailable on this platform")
        import pty
        child_env = self._build_env()
        master_fd, slave_fd = _pty_mod.openpty()
        self._set_winsize(slave_fd, self.rows, self.cols)
        argv = ["/bin/sh", "-c", self.command]
        try:
            self._proc = subprocess.Popen(
                argv,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=self.cwd,
                env=child_env,
                start_new_session=True,   # own process group + session leader
                close_fds=True,
            )
        except OSError:
            os.close(master_fd)
            os.close(slave_fd)
            raise
        os.close(slave_fd)               # parent keeps only the master side
        self.fd = master_fd
        self.pid = self._proc.pid
        self._thread = threading.Thread(
            target=self._read_loop, name=f"balamba-pty-{self.pid}", daemon=True)
        self._thread.start()

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.setdefault("LANG", "C.UTF-8")
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["BALAMBA"] = "1"
        env.pop("TMUX", None)
        env.update({k: str(v) for k, v in self.env_overrides.items()})
        return env

    @staticmethod
    def _set_winsize(fd: int, rows: int, cols: int) -> None:
        try:
            fcntl.ioctl(fd, termios_tiocswinsz(), struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

    def write(self, data: bytes) -> None:
        if self.fd is None or self._closed:
            return
        try:
            os.write(self.fd, data)
        except OSError:
            pass

    def resize(self, cols: int, rows: int) -> None:
        if self.fd is None or self._closed:
            return
        if (cols, rows) == (self.cols, self.rows):
            return
        self.cols, self.rows = cols, rows
        self._set_winsize(self.fd, rows, cols)

    def live_cwd(self) -> str | None:
        """Current child cwd via /proc (Linux); None elsewhere (README note)."""
        if self.pid is None:
            return None
        try:
            return os.readlink(f"/proc/{self.pid}/cwd")
        except OSError:
            return None

    def alive(self) -> bool:
        return not self._closed and self.exit_code is None

    def kill(self, grace: float = 0.4) -> None:
        if self._closed or self.pid is None:
            return
        try:
            os.killpg(self.pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        deadline = time.time() + grace
        while self.exit_code is None and time.time() < deadline:
            time.sleep(0.02)
        if self.exit_code is None:
            try:
                os.killpg(self.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass

    # -- reader --------------------------------------------------------------
    def _read_loop(self) -> None:
        fd = self.fd
        assert fd is not None
        dbg = os.environ.get("BALAMBA_DEBUG")
        if dbg:
            print(f"[reader] started pid={self.pid} cmd={self.command[:40]!r}",
                  file=sys.stderr, flush=True)
        try:
            while True:
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    break  # EIO once the child is gone
                if not data:
                    break
                if dbg:
                    print(f"[reader] pid={self.pid} got {len(data)} bytes",
                          file=sys.stderr, flush=True)
                self._emit_data(data)
        finally:
            code = -1
            if self._proc is not None:
                try:
                    code = self._proc.wait(timeout=10)
                except Exception:
                    code = -1
            self.exit_code = code
            try:
                os.close(fd)
            except OSError:
                pass
            self._closed = True
            self._emit_exit(code)

    def deliver(self, data: bytes) -> None:
        """Inject bytes as if the child produced them (used by tests)."""
        self._emit_data(data)


def termios_tiocswinsz() -> int:
    import termios
    return termios.TIOCSWINSZ


def pty_available() -> bool:
    return _pty_mod is not None and hasattr(_pty_mod, "openpty")


def which_or_none(cmd: str) -> str | None:
    import shutil
    return shutil.which(cmd)


def quick_version(cmd: str) -> str:
    try:
        out = subprocess.run([cmd, "--version"], capture_output=True, text=True,
                             timeout=5).stdout
        return out.splitlines()[0] if out else ""
    except Exception:
        return ""


def default_shell() -> str:
    return os.environ.get("SHELL") or "/bin/sh"


IS_LINUX = sys.platform.startswith("linux")
