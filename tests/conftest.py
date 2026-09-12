"""Test fixtures for the SMA Sunny Tripower integration tests.

test_util.py has no Home Assistant dependency and always runs with plain
pytest. test_coordinator.py requires a full Home Assistant dev environment
(pytest-homeassistant-custom-component + homeassistant core), so the plugin
below is loaded only if it is actually installed.
"""
import importlib.util

import pytest

if importlib.util.find_spec("pytest_homeassistant_custom_component") is not None:
    pytest_plugins = "pytest_homeassistant_custom_component"

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations):
        """Enable custom integrations for all tests in this package."""
        yield
