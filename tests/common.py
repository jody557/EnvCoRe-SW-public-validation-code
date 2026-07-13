from __future__ import annotations

import atexit
import os
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import envcore_sw_public_release_tools as release_tools


CONFIG = release_tools.load_config(REPO_ROOT / "config" / "release_config.yaml")
_CACHE = None


def _prepared_release():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    release_value = os.environ.get("ENVCORE_RELEASE", "").strip()
    if not release_value:
        raise unittest.SkipTest("Set ENVCORE_RELEASE to the EnvCoRe-SW v5 ZIP or extracted release root.")
    root, temporary, zip_info = release_tools.prepare_release(Path(release_value), CONFIG)
    if temporary is not None:
        atexit.register(temporary.cleanup)
    _CACHE = (root, temporary, zip_info)
    return _CACHE


class ReleaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release, cls._temporary, cls.zip_info = _prepared_release()
        cls.config = CONFIG
        cls.files = release_tools.required_files(CONFIG)
        cls.counts = release_tools.expected_counts(CONFIG)
