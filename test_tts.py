# test_tts.py
# Quick manual check that every language actually produces audio.
# Run:  python3 test_tts.py
import sys
sys.path.insert(0, ".")
from core.tts_engine import TTSEngine
import time

tts = TTSEngine()   # preloads MMS-TTS models for yo/ha/ig on first run (needs internet once)
print(f"TTS available (any backend): {tts.is_available}")
for lang in ("en", "yo", "ha", "ig"):
    print(f"  {lang} available: {tts.is_language_available(lang)}")

samples = {
    "en": "This is a test. Question one of three. What is the capital of Nigeria?",
    "yo": "Kaabo si idanwo yii.",
    "ha": "Barka da zuwa jarrabawar.",
    "ig": "Nnoo na ule a.",
}

for lang, text in samples.items():
    print(f"Speaking [{lang}]: {text}")
    tts.speak(text, language=lang, interrupt=False)
    time.sleep(4)   # give each utterance time to actually play before the next

tts.shutdown()