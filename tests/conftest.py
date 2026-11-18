"""Fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    yield


@pytest.fixture(autouse=True)
def _bluetooth(enable_bluetooth):
    """Every test runs with the (mocked) Bluetooth stack loaded."""
    yield
