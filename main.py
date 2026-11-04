"""
VisioExam - Personalized Multilingual Examination System for Visually Impaired Candidates
Entry point for the application.
"""

import sys
import logging
import os
from pathlib import Path

from core.app_paths import is_frozen, project_root, settings_file, user_data_dir

# Ensure the project root is on the path
PROJECT_ROOT = project_root()
sys.path.insert(0, str(PROJECT_ROOT))
from core.environment import load_env_file

load_env_file(settings_file())
if is_frozen():
    model_cache = user_data_dir() / "models" / "huggingface"
    os.environ.setdefault("HF_HOME", str(model_cache))

from core.database import Database
from core.profile_manager import ProfileManager
from ui.app import VisioExamApp

LOG_ROOT = user_data_dir() if is_frozen() else PROJECT_ROOT
LOG_PATH = LOG_ROOT / "logs" / "visioexam.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_handlers = [logging.FileHandler(LOG_PATH, encoding="utf-8")]
if sys.stdout is not None:
    _handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_handlers,
)

logger = logging.getLogger(__name__)


def main():
    logger.info("VisioExam starting up.")
    try:
        db = Database()
        db.initialize()

        profile_manager = ProfileManager(db)
        app = VisioExamApp(db, profile_manager)
        app.run()
    except Exception as e:
        logger.critical(f"Fatal error during startup: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
