import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from ad_optimizer.client.mock_client import MockAdClient


@pytest.fixture
def mock_client():
    return MockAdClient()
