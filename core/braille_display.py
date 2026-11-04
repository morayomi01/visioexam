"""
Braille Display Module.
Translates text to Unified English Braille (UEB) via liblouis and pushes
output to a connected refreshable Braille display over USB/Bluetooth HID.

Supports 40-cell and 80-cell display configurations.
Falls back gracefully to TTS when no display is detected (FR-4.5).
"""

import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)

# liblouis table for each supported language
LOUIS_TABLE = {
    "en": "en-ueb-g1.ctb",
    "yo": "en-ueb-g1.ctb",   # Yoruba Braille tables not widely standardized; use UEB as base
    "ha": "en-ueb-g1.ctb",
    "ig": "en-ueb-g1.ctb",
}

DISPLAY_WIDTHS = {40, 80}
DEFAULT_WIDTH = 40


class BrailleDisplay:
    """
    Abstraction over a physical refreshable Braille display.
    If liblouis or a connected display is unavailable, all methods
    silently succeed (with a log warning) so the exam never crashes.
    """

    def __init__(self, cell_width: int = DEFAULT_WIDTH):
        if cell_width not in DISPLAY_WIDTHS:
            cell_width = DEFAULT_WIDTH
        self.cell_width = cell_width
        self._connected = False
        self._louis_available = self._check_louis()
        self._hid_device = None
        self._current_text = ""
        self._pan_offset = 0
        self._lock = threading.Lock()
        self._on_fallback: Callable[[str], None] | None = None

        self.reconnect()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def display(self, text: str, language: str = "en"):
        """
        Translate text to Braille and push to display.
        If no display is connected, logs a warning and returns.
        """
        with self._lock:
            self._current_text = text
            self._pan_offset = 0

        if not self._connected:
            logger.debug("No Braille display connected — skipping output.")
            return

        cells = self._translate(text, language)
        self._send_cells(cells[: self.cell_width])

    def pan_right(self, language: str = "en"):
        """Advance one display-width to the right in the current text."""
        with self._lock:
            new_offset = self._pan_offset + self.cell_width
            cells = self._translate(self._current_text, language)
            if new_offset < len(cells):
                self._pan_offset = new_offset
                self._send_cells(cells[new_offset: new_offset + self.cell_width])

    def pan_left(self, language: str = "en"):
        """Step back one display-width to the left."""
        with self._lock:
            new_offset = max(0, self._pan_offset - self.cell_width)
            self._pan_offset = new_offset
            cells = self._translate(self._current_text, language)
            self._send_cells(cells[new_offset: new_offset + self.cell_width])

    def set_fallback_callback(self, callback: Callable[[str], None]):
        self._on_fallback = callback

    def is_connected(self) -> bool:
        return self._connected

    @property
    def status(self) -> str:
        if not self._louis_available:
            return "Translation unavailable (install liblouis)"
        if self._connected:
            return "Connected"
        return "No compatible HID display found"

    def reconnect(self) -> bool:
        """Retry translation and HID discovery after setup or device changes."""
        if self._connected:
            return True
        self._louis_available = self._check_louis()
        self._try_connect()
        return self._connected

    def disconnect(self):
        if self._hid_device:
            try:
                self._hid_device.close()
            except Exception:
                pass
        self._connected = False
        self._hid_device = None
        logger.info("Braille display disconnected.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _check_louis() -> bool:
        try:
            import louis  # type: ignore  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "liblouis Python bindings not found. "
                "Braille output will be unavailable."
            )
            return False

    def _try_connect(self):
        """
        Attempt to open the first available HID Braille device.
        Uses the 'hid' library (hidapi Python bindings).
        """
        try:
            import hid  # type: ignore
            # Common HID vendor IDs for popular Braille displays
            # (Freedom Scientific, Humanware, HIMS, etc.)
            BRAILLE_VENDOR_IDS = {0x0F4E, 0x1C71, 0x045E, 0x04B3}
            for device_info in hid.enumerate():
                if device_info["vendor_id"] in BRAILLE_VENDOR_IDS:
                    dev = hid.device()
                    dev.open(device_info["vendor_id"], device_info["product_id"])
                    dev.set_nonblocking(True)
                    self._hid_device = dev
                    self._connected = True
                    logger.info(
                        f"Braille display connected: {device_info.get('product_string', 'unknown')} "
                        f"(VID={device_info['vendor_id']:#06x})"
                    )
                    return
            logger.info("No Braille display detected. TTS-only mode active.")
        except ImportError:
            logger.warning("hid (hidapi) library not available. Braille HID unsupported.")
        except Exception as exc:
            logger.error(f"Error during Braille display detection: {exc}")

    def _translate(self, text: str, language: str) -> list[int]:
        """
        Translate plain text to a list of Braille cell integers using liblouis.
        Returns an empty list on failure.
        """
        if not self._louis_available or not text:
            return []
        try:
            import louis  # type: ignore
            table = LOUIS_TABLE.get(language, LOUIS_TABLE["en"])
            # python-louis returns a Unicode string. HID cells use the
            # Unicode Braille Patterns block's low eight dot bits.
            translated = louis.translateString([table], text, typeform=None, mode=0)
            return [
                ord(char) - 0x2800 if 0x2800 <= ord(char) <= 0x28FF else 0
                for char in translated
            ]
        except Exception as exc:
            logger.error(f"liblouis translation error: {exc}")
            return []

    def _send_cells(self, cells: list[int]):
        """Write Braille cell bytes to the HID device."""
        if not self._louis_available:
            logger.warning("Cannot connect Braille display: liblouis is unavailable.")
            return
        if not self._connected or self._hid_device is None:
            return
        try:
            # Most displays accept raw dot-pattern bytes; prepend report ID 0
            payload = [0] + cells[: self.cell_width]
            # Pad to full display width
            payload += [0x00] * (self.cell_width + 1 - len(payload))
            self._hid_device.write(payload)
        except Exception as exc:
            logger.error(f"Failed to write to Braille display: {exc}")
            self._connected = False
            if self._on_fallback:
                self._on_fallback("Braille display disconnected.")
