"""
TTS Engine — self-voicing audio output.

Hybrid backend:
  - English         -> eSpeak-NG (fast, lightweight, already installed locally)
  - Yoruba, Hausa    -> Meta MMS-TTS via `transformers` (eSpeak-NG has NO
    voice data for these languages at all, confirmed against espeak-ng
    >= 1.51 and github.com/espeak-ng/espeak-ng/issues/2360, still open as
    of this writing). CC-BY-NC-4.0, ~145MB each, runs fully offline.
  - Igbo             -> YarnGPT-local via `transformers` (a different model
    purpose-built for Yoruba/Igbo/Hausa — Meta never published an Igbo
    MMS-TTS checkpoint at all, confirmed via repeated 404s on every known
    path). CC-BY-NC-SA-4.0. See core/yarngpt_igbo_backend.py docstring for
    the one-time setup (vendoring the yarngpt helper package + downloading
    WavTokenizer weights).

Vocalization latency target: <= 500ms from call to first audio.
NOTE: both neural paths (MMS and YarnGPT) are slower than eSpeak-NG
(typically 1-5s on CPU for a sentence) since they're neural models, not
formant synthesis. Preload both at application startup (see preload calls
in __init__) so the model-load cost is paid once, not per utterance.
"""

import subprocess
import threading
import logging
import queue
import shutil
from dataclasses import dataclass
from typing import Callable

from core.mms_tts_backend import MMSTTSBackend
from core.yarngpt_igbo_backend import YarnGPTIgboBackend

logger = logging.getLogger(__name__)

# eSpeak-NG voice identifiers — English only. Yoruba/Hausa/Igbo are handled
# by the two neural backends instead; they are intentionally absent here
# since no eSpeak-NG voice data exists for them.
VOICE_MAP = {
    "en": "en",
}

# Languages routed to the MMS-TTS neural backend instead of eSpeak-NG.
MMS_LANGUAGES = ("yo", "ha")

# Languages routed to the YarnGPT-local neural backend instead of eSpeak-NG.
YARNGPT_LANGUAGES = ("ig",)

# Fallback announcement strings per language when TTS itself fails
SILENT_MODE_LABEL = {
    "en": "[Audio unavailable — please read on screen]",
    "yo": "[Ohun ko si — jọwọ ka loju iboju]",
    "ha": "[Ba sauti ba — don Allah karanta a allon]",
    "ig": "[Olu adịghị — biko gụọ n'ihu ihuenyo]",
}


@dataclass
class SpeechRequest:
    text: str
    language: str = "en"
    rate: float = 1.0          # multiplier, 0.5–2.0
    interrupt: bool = False    # if True, stops current speech first
    generation: int = 0        # invalidates queued work after an interrupt


class TTSEngine:
    """
    Wraps eSpeak-NG in a background worker thread so speech never blocks the UI.
    Provides speak(), stop(), and a silent-mode fallback.
    """

    ESPEAK_RATE_BASE = 175     # eSpeak words-per-minute at rate=1.0

    def __init__(
        self,
        preload_mms_languages: tuple[str, ...] = (),
        preload_yarngpt: bool = False,
    ):
        self._espeak_path: str | None = shutil.which("espeak-ng") or shutil.which("espeak")
        self._espeak_available = self._espeak_path is not None
        self._queue: queue.Queue[SpeechRequest | None] = queue.Queue()
        self._current_proc: subprocess.Popen | None = None
        self._current_playback = None   # sounddevice playback handle (neural paths)
        self._lock = threading.Lock()
        self._request_lock = threading.Lock()
        self._request_generation = 0
        self._generation_cancelled = threading.Event()
        self._on_silent_mode_fallback: Callable[[str], None] | None = None

        self._mms = MMSTTSBackend()
        self._neural_load_lock = threading.Lock()
        self._mms_attempted: set[str] = set()
        self._yarngpt_attempted = False
        if preload_mms_languages:
            try:
                self._mms.preload(list(preload_mms_languages))
            except Exception as exc:
                logger.error(f"Failed to preload MMS-TTS models: {exc}", exc_info=True)

        self._yarngpt = YarnGPTIgboBackend()
        if preload_yarngpt:
            try:
                self._yarngpt.preload()
            except Exception as exc:
                logger.error(f"Failed to preload YarnGPT-local (Igbo): {exc}", exc_info=True)

        self._worker = threading.Thread(target=self._process_queue, daemon=True)
        self._worker.start()

        if not self._espeak_available:
            logger.warning(
                "eSpeak-NG not found on PATH. English TTS will be unavailable. "
                "Falling back to silent mode for English."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def speak(self, text: str, language: str = "en", rate: float = 1.0, interrupt: bool = True):
        """
        Queue a speech request. If interrupt=True, the current utterance is
        stopped before the new one begins (≤ 500ms target).
        """
        if not text or not text.strip():
            return
        with self._request_lock:
            if interrupt:
                self._request_generation += 1
                self._generation_cancelled.set()
                self._stop_current()
                self._discard_queued_requests()
            req = SpeechRequest(
                text=text,
                language=language,
                rate=rate,
                interrupt=interrupt,
                generation=self._request_generation,
            )
            self._queue.put(req)

    def stop(self):
        """Immediately stop any active and queued speech."""
        self._generation_cancelled.set()
        self._stop_current()
        self._discard_queued_requests()

    def _discard_queued_requests(self):
        """Remove pending utterances superseded by a newer interrupting request."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def set_silent_mode_callback(self, callback: Callable[[str], None]):
        """Register a UI callback invoked when TTS is unavailable."""
        self._on_silent_mode_fallback = callback

    @property
    def is_available(self) -> bool:
        """True if at least one backend (eSpeak-NG, MMS-TTS, or YarnGPT) is usable."""
        return self._espeak_available or self._mms.any_loaded() or self._yarngpt.is_ready()

    def is_language_available(self, language: str) -> bool:
        if language in MMS_LANGUAGES:
            return self._mms.is_supported(language)
        if language in YARNGPT_LANGUAGES:
            return self._yarngpt.is_ready()
        return self._espeak_available

    def shutdown(self):
        """Gracefully shut down the worker thread."""
        self.stop()
        self._queue.put(None)   # sentinel
        self._worker.join(timeout=2)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _stop_current(self):
        with self._lock:
            if self._current_proc and self._current_proc.poll() is None:
                try:
                    self._current_proc.terminate()
                except OSError:
                    pass
                self._current_proc = None
            if self._current_playback is not None:
                try:
                    import sounddevice as sd
                    sd.stop()
                except Exception:
                    pass
                self._current_playback = None

    def _process_queue(self):
        while True:
            req = self._queue.get()
            if req is None:
                break
            with self._request_lock:
                if req.generation != self._request_generation:
                    continue
                self._generation_cancelled.clear()
            self._speak_sync(req)

    def _speak_sync(self, req: SpeechRequest):
        if req.language in MMS_LANGUAGES:
            self._speak_mms(req)
        elif req.language in YARNGPT_LANGUAGES:
            self._speak_yarngpt(req)
        else:
            self._speak_espeak(req)

    def _speak_mms(self, req: SpeechRequest):
        """Yoruba / Hausa — neural TTS via MMS (no eSpeak-NG voice exists)."""
        self._ensure_mms(req.language)
        if not self._mms.is_supported(req.language):
            logger.warning(f"MMS-TTS model for '{req.language}' not loaded.")
            self._silent_fallback(req.text, req.language)
            return
        try:
            import sounddevice as sd
            wav, rate = self._mms.synthesize(req.text, req.language)
            if self._generation_cancelled.is_set():
                return
            with self._lock:
                sd.play(wav, samplerate=rate)
                self._current_playback = True
            sd.wait()
            self._current_playback = None
        except Exception as exc:
            logger.error(f"MMS-TTS error ({req.language}): {exc}", exc_info=True)
            self._current_playback = None
            self._silent_fallback(req.text, req.language)

    def _speak_yarngpt(self, req: SpeechRequest):
        """Igbo — neural TTS via YarnGPT-local (no MMS checkpoint exists for Igbo)."""
        self._ensure_yarngpt()
        if not self._yarngpt.is_ready():
            logger.warning("YarnGPT-local (Igbo) model not loaded.")
            self._silent_fallback(req.text, req.language)
            return
        try:
            import sounddevice as sd
            wav, rate = self._yarngpt.synthesize(
                req.text, cancel_event=self._generation_cancelled
            )
            logger.info(
                "Playing Igbo audio (%d samples at %d Hz).", len(wav), rate
            )
            with self._lock:
                sd.play(wav, samplerate=rate)
                self._current_playback = True
            sd.wait()
            self._current_playback = None
            logger.info("Igbo audio playback finished.")
        except InterruptedError:
            logger.debug("Cancelled superseded Igbo speech request.")
            self._current_playback = None
        except Exception as exc:
            logger.error(f"YarnGPT-local error (Igbo): {exc}", exc_info=True)
            self._current_playback = None
            self._silent_fallback(req.text, req.language)

    def _ensure_mms(self, language: str):
        if self._mms.is_supported(language):
            return
        with self._neural_load_lock:
            if language in self._mms_attempted:
                return
            self._mms_attempted.add(language)
            try:
                self._mms.preload([language])
            except Exception as exc:
                logger.error("Could not prepare %s speech model: %s", language, exc)

    def _ensure_yarngpt(self):
        if self._yarngpt.is_ready():
            return
        with self._neural_load_lock:
            if self._yarngpt_attempted:
                return
            self._yarngpt_attempted = True
            try:
                self._yarngpt.preload()
            except Exception as exc:
                logger.error("Could not prepare Igbo speech model: %s", exc)

    def _speak_espeak(self, req: SpeechRequest):
        """English — eSpeak-NG formant synthesis."""
        if not self._espeak_available:
            self._silent_fallback(req.text, req.language)
            return

        voice = VOICE_MAP.get(req.language, "en")
        wpm = max(80, min(450, int(self.ESPEAK_RATE_BASE * req.rate)))

        # NOTE: do NOT add "--ipa" here. That flag tells espeak-ng to PRINT
        # the phoneme transcription as text instead of speaking — combined
        # with stdout=DEVNULL it silently produces zero audio (confirmed by
        # running `espeak-ng --ipa "..."`, which prints IPA text and exits 0
        # with no sound). Plain synthesis already handles diacritics fine.
        cmd = [
            self._espeak_path,
            "-v", voice,
            "-s", str(wpm),
            req.text,
        ]

        try:
            with self._lock:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                self._current_proc = proc
            proc.wait()
            stderr = proc.stderr.read() if proc.stderr else b""
            if proc.returncode != 0:
                if stderr:
                    logger.warning(f"eSpeak-NG stderr: {stderr.decode(errors='replace')}")
                # Previously a nonzero exit code was logged but never
                # triggered the UI fallback, so the candidate got total
                # silence with no on-screen notice. Fixed here.
                self._silent_fallback(req.text, req.language)
        except FileNotFoundError:
            self._espeak_available = False
            logger.error("eSpeak-NG binary disappeared. Disabling English TTS.")
            self._silent_fallback(req.text, req.language)
        except Exception as exc:
            logger.error(f"TTS error: {exc}", exc_info=True)
            self._silent_fallback(req.text, req.language)

    def _silent_fallback(self, text: str, language: str):
        """
        TTS unavailable — notify the UI layer so it can display on-screen text.
        The exam must NOT crash when TTS fails (NFR reliability requirement).
        """
        label = SILENT_MODE_LABEL.get(language, SILENT_MODE_LABEL["en"])
        logger.warning(f"Silent mode — would have spoken: {text!r}")
        if self._on_silent_mode_fallback:
            self._on_silent_mode_fallback(label)
