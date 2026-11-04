"""
Igbo TTS via YarnGPT-local — a transformers-native model purpose-built for
Yoruba/Igbo/Hausa speech synthesis (SmolLM2 architecture + WavTokenizer
audio codec), trained on the NaijaVoices dataset by Saheed Azeez, 2025.

Unlike the MMS/VITS path used for Yoruba and Hausa, this needs no
monotonic_align, no VITS, and no C/C++ compiler — pure pip-installable
Python. This is the backend for Igbo specifically, since Meta never
published an Igbo MMS-TTS checkpoint (confirmed via repeated 404s on
every known path — individual HF repo, full_models/ibo, and models/ibo).

ONE-TIME SETUP (before first run):
  1. Clone the yarngpt helper package (not a pip package) into the
     project's vendor/ folder:
       git clone https://github.com/saheedniyi02/yarngpt.git vendor/yarngpt
  2. pip install outetts==0.2.3 uroman gdown
     (already in requirements.txt — this note is just for manual setup
     if you're installing outside of requirements.txt)

On first preload(), this module also downloads the WavTokenizer audio
codec weights (~1.3GB, one-time, needs internet) into
~/.cache/visioexam/yarngpt/. After that, everything runs fully offline.

License: CC-BY-NC-SA-4.0 (free for non-commercial / academic use — cite
Saheed Azeez, 2025, "YarnGPT-local", Hugging Face, in your report. Note
the ShareAlike clause: derivative *models* you redistribute would need
the same license — this doesn't affect simply using the pretrained model
in your app).
"""

import logging
import os
import sys
import threading
import time
from pathlib import Path

from core.app_paths import bundled_root

import numpy as np

logger = logging.getLogger(__name__)

HF_MODEL_ID = "saheedniyi/YarnGPT-local"
WAVTOKENIZER_CONFIG_URL = (
    "https://huggingface.co/novateur/WavTokenizer-medium-speech-75token/"
    "resolve/main/wavtokenizer_mediumdata_frame75_3s_nq1_code4096_dim512_kmeans200_attn.yaml"
)
WAVTOKENIZER_CKPT_GDRIVE_ID = "1-ASeEkrn4HY49yZWHTASgfGFNXdVnLTt"

DEFAULT_CACHE_DIR = (
    user_data_dir() / "models" / "yarngpt"
    if getattr(sys, "frozen", False)
    else Path.home() / ".cache" / "visioexam" / "yarngpt"
)
DEFAULT_VENDOR_DIR = bundled_root() / "vendor" / "yarngpt"

# Available voices per the model card: igbo_female1, igbo_female2, igbo_male2
DEFAULT_VOICE = "igbo_female1"

SAMPLE_RATE = 24000


class YarnGPTIgboBackend:
    """
    Loads the YarnGPT-local model once and keeps it resident in memory.
    Loading per-utterance would add real latency — always call preload()
    once at application startup, same as the MMS backend.
    """

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR, vendor_dir: Path = DEFAULT_VENDOR_DIR):
        self._cache_dir = cache_dir
        self._vendor_dir = vendor_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._audio_tokenizer = None
        self._model = None
        self._ready = False

    def preload(self):
        if self._ready:
            return
        try:
            self._offline_only = os.environ.get("VISIOEXAM_OFFLINE", "0") == "1"
            if self._offline_only:
                os.environ["HF_HUB_OFFLINE"] = "1"
            self._ensure_vendor_on_path()
            self._ensure_wavtokenizer_files()

            import torch  # noqa: F401  (imported to fail fast if missing)
            from transformers import AutoModelForCausalLM
            from yarngpt.audiotokenizer import AudioTokenizerForLocal

            config_path = self._cache_dir / "wavtokenizer_config.yaml"
            ckpt_path = self._cache_dir / "wavtokenizer.ckpt"

            logger.info("Loading YarnGPT-local (Igbo TTS)...")
            self._audio_tokenizer = AudioTokenizerForLocal(
                HF_MODEL_ID, str(ckpt_path), str(config_path)
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                HF_MODEL_ID,
                torch_dtype="auto",
                local_files_only=self._offline_only,
            ).to(self._audio_tokenizer.device)
            self._ready = True
            logger.info("YarnGPT-local (Igbo TTS) ready.")
        except Exception as exc:
            logger.error(f"Could not load YarnGPT-local Igbo model: {exc}", exc_info=True)
            self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def synthesize(
        self,
        text: str,
        voice: str = DEFAULT_VOICE,
        cancel_event: threading.Event | None = None,
    ) -> tuple[np.ndarray, int]:
        """Returns (waveform, sample_rate) as a mono float32 numpy array."""
        if not self._ready:
            raise RuntimeError("YarnGPT-local model not loaded — call preload() first.")

        prompt = self._audio_tokenizer.create_prompt(text, "igbo", voice)
        input_ids = self._audio_tokenizer.tokenize_prompt(prompt)
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList

        class CancelGeneration(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return bool(cancel_event and cancel_event.is_set())

        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Igbo speech request was superseded.")
        started = time.monotonic()
        # Bound decoder work: max_length=4000 could take a long time when EOS
        # was not emitted. Estimate a sensible cap from the input length, and
        # use greedy decoding so CPU-only PCs do not pay the multi-beam cost.
        # The estimate allows roughly 16 audio tokens per input word plus a
        # small fixed margin, capped at 512 tokens for long exam prompts.
        token_budget = max(128, min(512, len(text.split()) * 16 + 64))
        with torch.inference_mode():
            output = self._model.generate(
                input_ids=input_ids,
                repetition_penalty=1.1,
                num_beams=1,
                max_new_tokens=token_budget,
                stopping_criteria=StoppingCriteriaList([CancelGeneration()]),
            )
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Igbo speech request was superseded.")
        logger.info(
            "Igbo speech tokens generated in %.1fs (input=%d, output=%d).",
            time.monotonic() - started,
            input_ids.shape[-1],
            output.shape[-1] - input_ids.shape[-1],
        )
        codes = self._audio_tokenizer.get_codes(output)
        audio_tensor = self._audio_tokenizer.get_audio(codes)
        waveform = audio_tensor.squeeze().detach().cpu().numpy().astype(np.float32)
        if waveform.size == 0 or not np.isfinite(waveform).all():
            raise RuntimeError("Igbo speech synthesis returned empty or invalid audio.")
        if float(np.max(np.abs(waveform))) < 1e-6:
            raise RuntimeError("Igbo speech synthesis returned silence.")
        return waveform, SAMPLE_RATE

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _ensure_vendor_on_path(self):
        if not self._vendor_dir.is_dir():
            raise FileNotFoundError(
                f"yarngpt helper package not found at {self._vendor_dir}. "
                "Run: git clone https://github.com/saheedniyi02/yarngpt.git "
                f"\"{self._vendor_dir}\""
            )
        parent = str(self._vendor_dir.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)

    def _ensure_wavtokenizer_files(self):
        config_path = self._cache_dir / "wavtokenizer_config.yaml"
        ckpt_path = self._cache_dir / "wavtokenizer.ckpt"

        if getattr(self, "_offline_only", False) and (
            not config_path.is_file() or not ckpt_path.is_file()
        ):
            raise RuntimeError(
                "Offline mode is enabled, but the cached WavTokenizer files are "
                "missing. Disable VISIOEXAM_OFFLINE for one connected setup run."
            )

        if not config_path.is_file():
            import urllib.request
            logger.info("Downloading WavTokenizer config (one-time)...")
            urllib.request.urlretrieve(WAVTOKENIZER_CONFIG_URL, config_path)

        if not ckpt_path.is_file():
            import gdown
            logger.info("Downloading WavTokenizer checkpoint (~1.3GB, one-time)...")
            result = gdown.download(
                id=WAVTOKENIZER_CKPT_GDRIVE_ID,
                output=str(ckpt_path),
                quiet=False,
            )
            if not result or not ckpt_path.is_file() or ckpt_path.stat().st_size < 100_000_000:
                ckpt_path.unlink(missing_ok=True)
                raise RuntimeError(
                    "The Igbo speech model download did not complete. Check the "
                    "internet connection and available disk space, then try again."
                )
