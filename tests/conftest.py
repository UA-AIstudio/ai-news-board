import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# "Now" for every fixture: the fixtures are dated around this moment.
FIXTURE_NOW = datetime(2026, 6, 15, 9, 0, tzinfo=ZoneInfo("America/Phoenix"))


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def good_news():
    return load_fixture("good.json")


@pytest.fixture
def good_pinned():
    return load_fixture("pinned_good.json")
