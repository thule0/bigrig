import os.path
from pathlib import Path

import pytest


@pytest.fixture
def datadir():
    return Path(os.path.dirname(os.path.realpath(__file__))) / "data"
