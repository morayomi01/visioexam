"""
MMS-TTS backend — free, offline neural text-to-speech for Yoruba and
Hausa (eSpeak-NG has no voice data for these languages at all).

Yoruba and Hausa load directly from Meta's Hugging Face mirror
(facebook/mms-tts-yor / -hau) via `transformers`.

Igbo is NOT handled here — Meta never published an Igbo MMS-TTS
checkpoint at all (confirmed via repeated 404s on every known path: the
individual facebook/mms-tts-ibo repo, full_models/ibo, and models/ibo).
Igbo is instead handled by core/yarngpt_igbo_backend.py, a different
model (YarnGPT-local) purpose-built for Yoruba/Igbo/Hausa. TTSEngine
routes to whichever backend applies per language — see MMS_LANGUAGES vs
YARNGPT_LANGUAGES in tts_engine.py.

License note: MMS-TTS checkpoints are CC-BY-NC-4.0 (free for
non-commercial / academic use — cite Pratap et al. 2023 in your report).
"""

import logging
import os

import numpy as np

logger = logging.getLogger(__name__)

# Hugging Face model IDs for languages Meta published individually.
MMS_MODEL_IDS = {
    "yo": "facebook/mms-tts-yor",   # Yoruba
    "ha": "facebook/mms-tts-hau",   # Hausa
}


class MMSTTSBackend:
    """
    Loads each language's VITS model once and keeps it resident in memory.
    Loading per-utterance would add several seconds of latency per call,
    which is unacceptable for an exam UI — always call preload() once at
    application startup.
    """

    def __init__(self):
        self._models: dict[str, object] = {}
        self._tokenizers: dict[str, object] = {}

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def preload(self, languages: list[str]):
        """
        Load model weights for the given languages into memory.
        Any language that fails to load (e.g. no internet on first run)
        is logged and simply left unavailable — it will not crash the
        caller.
        """
        from transformers import VitsModel, AutoTokenizer
        local_only = os.environ.get("VISIOEXAM_OFFLINE", "0") == "1"
        if local_only:
            os.environ["HF_HUB_OFFLINE"] = "1"

        for lang in languages:
            if lang in self._models:
                continue  # already loaded

            model_id = MMS_MODEL_IDS.get(lang)
            if not model_id:
                logger.warning(f"No MMS-TTS model configured for language '{lang}'.")
                continue

            try:
                logger.info(f"Loading MMS-TTS model for '{lang}' ({model_id})...")
                self._models[lang] = VitsModel.from_pretrained(
                    model_id, local_files_only=local_only
                )
                self._tokenizers[lang] = AutoTokenizer.from_pretrained(
                    model_id, local_files_only=local_only
                )
                logger.info(f"MMS-TTS model for '{lang}' ready.")
            except Exception as exc:
                logger.error(
                    f"Could not load MMS-TTS model for '{lang}' ({model_id}): {exc}",
                    exc_info=True,
                )

    def any_loaded(self) -> bool:
        return bool(self._models)

    def is_supported(self, lang: str) -> bool:
        """True only if this language's model is actually loaded and ready."""
        return lang in self._models and lang in self._tokenizers

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def synthesize(self, text: str, lang: str) -> tuple[np.ndarray, int]:
        """
        Returns (waveform, sample_rate) as a mono float32 numpy array.
        Raises KeyError if the language was never successfully preloaded —
        callers should check is_supported() first.
        """
        import torch

        model = self._models[lang]
        tokenizer = self._tokenizers[lang]
        inputs = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            output = model(**inputs).waveform
        waveform = output.squeeze().cpu().numpy().astype(np.float32)
        return waveform, model.config.sampling_rate
