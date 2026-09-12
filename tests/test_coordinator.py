"""Tests for SmaModbusCoordinator: reads, writes, read-back confirmation and
error handling.

Requires pytest-homeassistant-custom-component (provides the `hass` fixture)
since SmaModbusCoordinator subclasses DataUpdateCoordinator.
"""
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.sma_power_control.coordinator import (
    KEY_ACTIVE_POWER_LIMIT_PERCENT,
    KEY_OPERATING_MODE,
    SmaModbusCoordinator,
)


class FakeModbusResponse:
    """Minimal stand-in for a pymodbus response object."""

    def __init__(self, registers=None, error=False):
        self.registers = registers or []
        self._error = error

    def isError(self):  # noqa: N802 (pymodbus API name)
        return self._error


@pytest.fixture
def coordinator(hass):
    coord = SmaModbusCoordinator(hass, "192.0.2.10", 502, 3)
    coord.client = AsyncMock()
    type(coord.client).connected = PropertyMock(return_value=True)
    coord.client.connect = AsyncMock(return_value=True)
    return coord


async def test_async_update_data_reads_all_registers(coordinator):
    coordinator.client.read_holding_registers.side_effect = [
        # 40210..40215 in one 6-register batch: mode, reserved (W-limit), limit %
        FakeModbusResponse([0, 1078, 0, 0, 0, 20]),
    ]

    data = await coordinator._async_update_data()

    assert data[KEY_OPERATING_MODE] == 1078
    assert data[KEY_ACTIVE_POWER_LIMIT_PERCENT] == 20

    # Operating mode + active power limit % must be read in a single batched
    # call (address 40210, count 6), not two separate reads.
    coordinator.client.read_holding_registers.assert_awaited_once_with(
        40210, count=6, slave=3
    )


async def test_async_update_data_raises_on_error_response(coordinator):
    coordinator.client.read_holding_registers.side_effect = [
        FakeModbusResponse(error=True),
    ]

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_async_update_data_returns_none_for_sentinel_registers(coordinator):
    """If the inverter reports its "not available" sentinel pattern instead
    of a real value, the coordinator must expose None rather than a bogus
    large integer."""
    coordinator.client.read_holding_registers.side_effect = [
        FakeModbusResponse([0, 1078, 0, 0, 0xFFFF, 0xFFFF]),  # limit % unavailable
    ]

    data = await coordinator._async_update_data()

    assert data[KEY_OPERATING_MODE] == 1078
    assert data[KEY_ACTIVE_POWER_LIMIT_PERCENT] is None


async def test_async_set_operating_mode_writes_and_reads_back(coordinator):
    coordinator.client.write_registers.return_value = FakeModbusResponse()
    coordinator.client.read_holding_registers.return_value = FakeModbusResponse([0, 1078])

    await coordinator.async_set_operating_mode(1078)

    coordinator.client.write_registers.assert_awaited_once_with(
        40210, [0, 1078], slave=3
    )
    assert coordinator.data[KEY_OPERATING_MODE] == 1078


async def test_async_set_active_power_limit_percent_writes_and_reads_back(coordinator):
    coordinator.client.write_registers.return_value = FakeModbusResponse()
    coordinator.client.read_holding_registers.return_value = FakeModbusResponse([0, 20])

    await coordinator.async_set_active_power_limit_percent(20)

    coordinator.client.write_registers.assert_awaited_once_with(40214, [0, 20], slave=3)
    assert coordinator.data[KEY_ACTIVE_POWER_LIMIT_PERCENT] == 20


async def test_write_reflects_actual_device_value_when_different_from_requested(coordinator):
    """If the inverter accepts the write but reports back a different value,
    the coordinator must reflect the actual value, not the requested one."""
    coordinator.client.write_registers.return_value = FakeModbusResponse()
    coordinator.client.read_holding_registers.return_value = FakeModbusResponse([0, 50])

    await coordinator.async_set_active_power_limit_percent(20)

    assert coordinator.data[KEY_ACTIVE_POWER_LIMIT_PERCENT] == 50


async def test_write_raises_on_error_response(coordinator):
    coordinator.client.write_registers.return_value = FakeModbusResponse(error=True)

    with pytest.raises(UpdateFailed):
        await coordinator.async_set_active_power_limit_percent(20)


async def test_no_grid_guard_write_on_first_time_success(coordinator):
    """The Grid Guard code must not be sent when the write succeeds on the
    first try, so the common case pays no extra round trip."""
    coordinator.grid_guard_code = "123456"
    coordinator.client.write_registers.return_value = FakeModbusResponse()
    coordinator.client.read_holding_registers.return_value = FakeModbusResponse([0, 20])

    await coordinator.async_set_active_power_limit_percent(20)

    coordinator.client.write_registers.assert_awaited_once_with(40214, [0, 20], slave=3)


async def test_grid_guard_login_and_retry_on_rejected_write(coordinator):
    """When the first write is rejected (e.g. ILLEGAL FUNCTION because Grid
    Guard is locked) and a code is configured, the coordinator must unlock
    Grid Guard and retry the write once before giving up."""
    coordinator.grid_guard_code = "123456"
    coordinator.client.write_registers.side_effect = [
        FakeModbusResponse(error=True),  # first write to 40214 rejected
        FakeModbusResponse(),  # grid guard login to 43090 succeeds
        FakeModbusResponse(),  # retried write to 40214 succeeds
    ]
    coordinator.client.read_holding_registers.return_value = FakeModbusResponse([0, 20])

    with patch(
        "custom_components.sma_power_control.coordinator.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await coordinator.async_set_active_power_limit_percent(20)

    assert coordinator.client.write_registers.await_args_list[0].args == (
        40214,
        [0, 20],
    )
    assert coordinator.client.write_registers.await_args_list[1].args == (
        43090,
        [0, 123456],
    )
    assert coordinator.client.write_registers.await_args_list[2].args == (
        40214,
        [0, 20],
    )
    assert coordinator.data[KEY_ACTIVE_POWER_LIMIT_PERCENT] == 20


async def test_no_retry_when_grid_guard_code_not_configured(coordinator):
    coordinator.client.write_registers.return_value = FakeModbusResponse(error=True)

    with pytest.raises(UpdateFailed):
        await coordinator.async_set_active_power_limit_percent(20)

    coordinator.client.write_registers.assert_awaited_once_with(40214, [0, 20], slave=3)


async def test_raises_when_retry_after_grid_guard_login_still_fails(coordinator):
    coordinator.grid_guard_code = "123456"
    coordinator.client.write_registers.side_effect = [
        FakeModbusResponse(error=True),  # first write rejected
        FakeModbusResponse(),  # grid guard login succeeds
        FakeModbusResponse(error=True),  # retried write still rejected
    ]

    with patch(
        "custom_components.sma_power_control.coordinator.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        with pytest.raises(UpdateFailed):
            await coordinator.async_set_active_power_limit_percent(20)


async def test_ensure_connected_reconnects_when_disconnected(hass):
    coord = SmaModbusCoordinator(hass, "192.0.2.10", 502, 3)
    coord.client = AsyncMock()
    connected_values = [False, True]
    type(coord.client).connected = PropertyMock(side_effect=lambda: connected_values.pop(0))
    coord.client.connect = AsyncMock(return_value=True)

    await coord._async_ensure_connected()

    coord.client.connect.assert_awaited_once()


async def test_ensure_connected_raises_when_connection_fails(hass):
    coord = SmaModbusCoordinator(hass, "192.0.2.10", 502, 3)
    coord.client = AsyncMock()
    type(coord.client).connected = PropertyMock(return_value=False)
    coord.client.connect = AsyncMock(return_value=False)

    with pytest.raises(UpdateFailed):
        await coord._async_ensure_connected()
