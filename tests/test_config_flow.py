"""Config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.allpowers.const import CONF_UPDATE_INTERVAL, DOMAIN

from .helpers import P300_ADDRESS, P300_NAME, service_info

SETUP = "custom_components.allpowers.async_setup_entry"
DISCOVERED = "custom_components.allpowers.config_flow.async_discovered_service_info"


async def test_bluetooth_discovery(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == P300_NAME
    assert result["data"] == {CONF_ADDRESS: P300_ADDRESS, CONF_NAME: P300_NAME}
    assert result["result"].unique_id == P300_ADDRESS


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant):
    MockConfigEntry(
        domain=DOMAIN, unique_id=P300_ADDRESS, data={CONF_ADDRESS: P300_ADDRESS, CONF_NAME: P300_NAME}
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=service_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_new_address_same_station(hass: HomeAssistant):
    """A rotated random address of a configured (not connected) station is not offered again."""
    MockConfigEntry(
        domain=DOMAIN, unique_id=P300_ADDRESS, data={CONF_ADDRESS: P300_ADDRESS, CONF_NAME: P300_NAME}
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info(address="7A:00:00:00:00:01"),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_lists_supported_stations(hass: HomeAssistant):
    others = [service_info(address="AA:BB:CC:DD:EE:FF", name="Flower care"), service_info()]
    with patch(DISCOVERED, return_value=others):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    options = result["data_schema"].schema[CONF_ADDRESS].container
    assert list(options) == [P300_ADDRESS]
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: P300_ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: P300_ADDRESS, CONF_NAME: P300_NAME}


async def test_user_flow_no_devices(hass: HomeAssistant):
    with patch(DISCOVERED, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_options_flow_update_interval(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=P300_ADDRESS, data={CONF_ADDRESS: P300_ADDRESS, CONF_NAME: P300_NAME}
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    defaults = {str(key): key.default() for key in result["data_schema"].schema}
    assert defaults[CONF_UPDATE_INTERVAL] == 15
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_UPDATE_INTERVAL: 30})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_UPDATE_INTERVAL: 30}
