"""Gemini-backed translation for exam questions and their choices.

The API key is read from ``GEMINI_API_KEY`` or a ``.env`` file beside the
source project / packaged executable. Keys are never logged or sent as query
parameters.
"""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.app_paths import settings_file


LANGUAGE_NAMES = {
    "en": "English",
    "yo": "Yoruba",
    "ha": "Hausa",
    "ig": "Igbo",
}


def _settings_file() -> Path:
    return settings_file()


def _read_setting(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value:
        return value.strip()
    try:
        lines = _settings_file().read_text(encoding="utf-8").splitlines()
    except OSError:
        return default
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        if key.strip() == name:
            value = raw_value.strip().strip("\"'")
            return value or default
    return default


class GeminiLanguageModel:
    """Small dependency-free client for Gemini's generateContent REST API."""

    def __init__(self):
        self._model = _read_setting("GEMINI_MODEL", "gemini-3.8-flash")

    @property
    def is_configured(self) -> bool:
        return bool(_read_setting("GEMINI_API_KEY"))

    def translate_exam_item(
        self, question: str, options: list[str], target_language: str
    ) -> dict:
        """Translate question and choices while preserving choice order."""
        api_key = _read_setting("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Gemini API key not found. Add GEMINI_API_KEY to the .env file."
            )

        language_name = LANGUAGE_NAMES.get(target_language)
        if not language_name:
            raise ValueError(f"Unsupported translation language: {target_language}")

        content = {
            "question": question,
            "options": options,
        }
        prompt = (
            f"Translate this examination item faithfully into {language_name}. "
            "Preserve meaning, names, numbers, and technical terms. Translate "
            "each answer choice without changing its meaning or order. Do not "
            "answer the question, add explanations, or identify the correct "
            "choice. Return only JSON matching this shape: "
            '{"question":"translated question","options":["translated choice"]}.\n\n'
            f"Item: {json.dumps(content, ensure_ascii=False)}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "maxOutputTokens": 2048,
            },
        }
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent"
        )
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=45) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429:
                raise RuntimeError(
                    "Gemini free-tier limit reached. Wait a little and try again."
                ) from None
            if exc.code in (401, 403):
                raise RuntimeError(
                    "Gemini rejected the API key. Check the key and model access."
                ) from None
            raise RuntimeError(f"Gemini request failed (HTTP {exc.code}).") from None
        except (URLError, TimeoutError, OSError):
            raise RuntimeError(
                "Could not reach Gemini. Check the internet connection and try again."
            ) from None

        try:
            response_text = result["candidates"][0]["content"]["parts"][0]["text"]
            translated = json.loads(response_text)
            translated_question = translated["question"].strip()
            translated_options = translated["options"]
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            raise RuntimeError("Gemini returned an invalid translation response.") from None

        if (
            not translated_question
            or not isinstance(translated_options, list)
            or len(translated_options) != len(options)
            or any(not isinstance(option, str) or not option.strip() for option in translated_options)
        ):
            raise RuntimeError("Gemini returned an incomplete translation.")
        return {
            "question": translated_question,
            "options": [option.strip() for option in translated_options],
        }
