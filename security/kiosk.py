"""
Kiosk Session Module.
Tracks an active exam presentation without disabling operating-system input.

Critical design constraint (FR-3.2):
  Windows accessibility APIs (MSAA / UI Automation) and Linux AT-SPI MUST remain
  accessible so that the built-in TTS and any fallback screen reader (NVDA) can
  continue to function. This is the core resolution to the Security-Accessibility
  Paradox described in the PRD.

The desktop application must never block operating-system shortcuts. Windows
kiosk policies belong to a managed OS account, not an ordinary app keyboard
hook. This module records exam kiosk state and watches for screen readers.

What is NOT blocked (intentionally):
  - WM_GETOBJECT / IAccessible / UIAutomation COM calls
  - AT-SPI D-Bus service on Linux
  - TTS process spawned by the application itself
"""

import logging
import platform
import subprocess
import threading
from typing import Callable

from security.audit_logger import AuditLogger, AuditEvent

logger = logging.getLogger(__name__)

_OS = platform.system()   # "Windows" | "Linux" | "Darwin"


class KioskManager:
    """
    Platform-aware exam presentation/session controller.
    Call enter() when an exam starts and exit() when it ends.
    """

    def __init__(self, audit: AuditLogger, session_id: str | None = None):
        self._audit = audit
        self._session_id = session_id
        self._active = False
        self._hook_handle = None          # Windows keyboard hook handle
        self._hook_thread: threading.Thread | None = None
        self._hook_thread_id: int | None = None
        self._hook_ready = threading.Event()
        self._hook_proc = None             # Keep ctypes callback alive
        self._screen_reader_watcher: threading.Thread | None = None
        self._stop_watcher = threading.Event()
        self._on_screen_reader_detected: Callable[[str], None] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enter(self):
        """Activate kiosk mode."""
        if self._active:
            return
        if _OS == "Windows":
            self._enter_windows()
        elif _OS == "Linux":
            self._enter_linux()
        else:
            logger.warning(f"Kiosk mode not implemented for OS '{_OS}'. Running unsecured.")

        self._active = True
        self._start_screen_reader_watcher()
        self._audit.log(AuditEvent.KIOSK_ENTER, f"os={_OS}", self._session_id)
        logger.info(f"Kiosk mode activated ({_OS}).")

    def exit(self):
        """Deactivate kiosk mode and restore normal OS behaviour."""
        if not self._active:
            return
        self._stop_watcher.set()
        if _OS == "Windows":
            self._exit_windows()
        elif _OS == "Linux":
            self._exit_linux()
        self._active = False
        self._audit.log(AuditEvent.KIOSK_EXIT, f"os={_OS}", self._session_id)
        logger.info("Kiosk mode deactivated.")

    def is_active(self) -> bool:
        return self._active

    def on_screen_reader_detected(self, callback: Callable[[str], None]):
        """Register a callback invoked if an external screen reader attaches (FR-3.5)."""
        self._on_screen_reader_detected = callback

    # ------------------------------------------------------------------
    # Windows implementation
    # ------------------------------------------------------------------

    def _enter_windows(self):
        # Keep OS shortcuts available so a desktop app cannot trap the user.
        # Full-screen presentation is controlled by VisioExamApp only.
        logger.info("Windows exam presentation enabled; operating-system shortcuts remain available.")

    def _windows_hook_loop(self):
        """Install a keyboard hook on a message-pumping thread."""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        self._hook_thread_id = kernel32.GetCurrentThreadId()
        hook_type = 13  # WH_KEYBOARD_LL
        wm_keydown, wm_syskeydown = 0x0100, 0x0104
        wm_quit = 0x0012
        vk_tab, vk_escape = 0x09, 0x1B
        vk_lwin, vk_rwin = 0x5B, 0x5C
        vk_shift, vk_control, vk_menu = 0x10, 0x11, 0x12

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.c_void_p)]

        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t
        )
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int, callback_type, wintypes.HINSTANCE, wintypes.DWORD
        ]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p

        def callback(code, message, data):
            if code >= 0 and message in (wm_keydown, wm_syskeydown):
                key = ctypes.cast(data, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents.vkCode
                alt_down = bool(user32.GetAsyncKeyState(vk_menu) & 0x8000)
                ctrl_down = bool(user32.GetAsyncKeyState(vk_control) & 0x8000)
                shift_down = bool(user32.GetAsyncKeyState(vk_shift) & 0x8000)
                blocked = (
                    key in (vk_lwin, vk_rwin)
                    or (key == vk_tab and alt_down)
                    or (key == vk_escape and ctrl_down)
                    or (key == vk_escape and ctrl_down and shift_down)
                )
                if blocked:
                    return 1
            return user32.CallNextHookEx(self._hook_handle, code, message, data)

        self._hook_proc = callback_type(callback)
        try:
            self._hook_handle = user32.SetWindowsHookExW(
                hook_type, self._hook_proc, kernel32.GetModuleHandleW(None), 0
            )
            if not self._hook_handle:
                raise ctypes.WinError()
            self._hook_ready.set()
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == wm_quit:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as exc:
            logger.error(f"Failed to install Windows keyboard hook: {exc}")
            self._hook_ready.set()
        finally:
            if self._hook_handle:
                user32.UnhookWindowsHookEx(self._hook_handle)
                self._hook_handle = None
            self._hook_proc = None

    def _exit_windows(self):
        # No low-level keyboard hook is installed by this application.
        self._hook_thread = None
        self._hook_thread_id = None
        self._hook_handle = None

    # ------------------------------------------------------------------
    # Linux implementation
    # ------------------------------------------------------------------

    def _enter_linux(self):
        """
        Linux implementation is only best-effort. It does not block shortcuts
        or provide a secure kiosk; use a managed kiosk account/session instead.
        """
        try:
            # Disable desktop screensaver / DPMS during exam
            subprocess.Popen(["xdg-screensaver", "reset"], stderr=subprocess.DEVNULL)
            logger.warning(
                "Linux screensaver reset only; keyboard shortcuts are not blocked. "
                "Use an OS-managed kiosk session for secure examinations."
            )
        except FileNotFoundError:
            logger.warning("xdg-screensaver or xdotool not found; limited kiosk on Linux.")

    def _exit_linux(self):
        try:
            subprocess.Popen(["xdg-screensaver", "activate"], stderr=subprocess.DEVNULL)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Screen reader watcher (FR-3.5)
    # ------------------------------------------------------------------

    SCREEN_READER_PROCS = {
        "Windows": ["nvda.exe", "jaws32.exe", "jfw.exe", "supernova.exe"],
        "Linux": ["orca", "speakup", "brltty"],
    }

    def _start_screen_reader_watcher(self):
        self._stop_watcher.clear()
        self._screen_reader_watcher = threading.Thread(
            target=self._watch_screen_readers, daemon=True
        )
        self._screen_reader_watcher.start()

    def _watch_screen_readers(self):
        import time
        import psutil  # type: ignore

        known_procs = set(self.SCREEN_READER_PROCS.get(_OS, []))
        already_alerted: set[str] = set()

        while not self._stop_watcher.is_set():
            try:
                for proc in psutil.process_iter(["name"]):
                    name = (proc.info.get("name") or "").lower()
                    if name in known_procs and name not in already_alerted:
                        already_alerted.add(name)
                        msg = f"External screen reader detected: {name}"
                        logger.warning(msg)
                        self._audit.log(
                            AuditEvent.SCREEN_READER_ATTACH, name, self._session_id
                        )
                        if self._on_screen_reader_detected:
                            self._on_screen_reader_detected(name)
            except Exception as exc:
                logger.debug(f"Screen reader watcher error: {exc}")
            time.sleep(5)
