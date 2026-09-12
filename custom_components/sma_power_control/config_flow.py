"""Config flow for the SMA Sunny Tripower integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from pymodbus.client import AsyncModbusTcpClient

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CONF_DEVICE_NAME,
    CONF_UNIT_ID,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    REG_OPERATING_MODE,
)

_LOGGER = logging.getLogger(__name__)


def _build_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the connection form schema, pre-filled with existing values."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Required(
                CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
            ): int,
            vol.Optional(
                CONF_DEVICE_NAME, default=defaults.get(CONF_DEVICE_NAME, DEFAULT_NAME)
            ): str,
        }
    )


def _make_unique_id(host: str, port: int, unit_id: int) -> str:
    return f"{host}_{port}_{unit_id}"


class CannotConnect(Exception):
    """Error to indicate we cannot connect to the inverter."""


async def _async_validate_connection(host: str, port: int, unit_id: int) -> None:
    """Attempt a real Modbus TCP connection and a read to validate the config."""
    client = AsyncModbusTcpClient(host, port=port)
    try:
        connected = await client.connect()
        if not connected:
            raise CannotConnect(f"Could not connect to {host}:{port}")
        try:
            result = await client.read_holding_registers(
                REG_OPERATING_MODE, count=2, slave=unit_id
            )
        except TypeError:
            result = await client.read_holding_registers(
                REG_OPERATING_MODE, count=2, device_id=unit_id
            )
        if result is None or result.isError():
            raise CannotConnect(f"Could not read from unit {unit_id} at {host}:{port}")
    finally:
        client.close()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMA Sunny Tripower."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            unit_id = user_input[CONF_UNIT_ID]
            device_name = user_input.get(CONF_DEVICE_NAME) or DEFAULT_NAME

            await self.async_set_unique_id(_make_unique_id(host, port, unit_id))
            self._abort_if_unique_id_configured()

            try:
                await _async_validate_connection(host, port, unit_id)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating SMA connection")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=device_name, data={**user_input, CONF_DEVICE_NAME: device_name}
                )

        return self.async_show_form(
            step_id="user", data_schema=_build_schema(), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow editing host/port/unit ID/device name of an existing entry.

        Lets the user fix connection details (e.g. after the inverter's IP
        changed) without deleting and re-adding the integration.
        """
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            unit_id = user_input[CONF_UNIT_ID]
            device_name = user_input.get(CONF_DEVICE_NAME) or DEFAULT_NAME

            await self.async_set_unique_id(_make_unique_id(host, port, unit_id))
            self._abort_if_unique_id_configured()

            try:
                await _async_validate_connection(host, port, unit_id)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating SMA connection")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=device_name,
                    data={**user_input, CONF_DEVICE_NAME: device_name},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_schema(reconfigure_entry.data),
            errors=errors,
        )
