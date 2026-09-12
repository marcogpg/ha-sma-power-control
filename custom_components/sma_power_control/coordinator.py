"""DataUpdateCoordinator for the SMA Sunny Tripower integration.

Owns a single AsyncModbusTcpClient connection per config entry and serializes
all Modbus access behind an asyncio.Lock, since a single TCP connection to
the inverter cannot safely handle concurrent requests.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ACTIVE_POWER_LIMIT_PERCENT_OFFSET,
    DOMAIN,
    GRID_GUARD_RETRY_DELAY_SECONDS,
    OPERATING_BLOCK_COUNT,
    OPERATING_BLOCK_START,
    OPERATING_MODE_OFFSET,
    REG_ACTIVE_POWER_LIMIT_PERCENT,
    REG_GRID_GUARD_CODE,
    REG_OPERATING_MODE,
    UPDATE_INTERVAL_SECONDS,
)
from .util import decode_u32_or_none, encode_u32

_LOGGER = logging.getLogger(__name__)

KEY_OPERATING_MODE = "operating_mode"
KEY_ACTIVE_POWER_LIMIT_PERCENT = "active_power_limit_percent"


class SmaModbusCoordinator(DataUpdateCoordinator[dict[str, int | None]]):
    """Coordinate Modbus TCP communication with the SMA inverter."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        unit_id: int,
        grid_guard_code: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.grid_guard_code = grid_guard_code
        self.client = AsyncModbusTcpClient(host, port=port)
        self._lock = asyncio.Lock()

    async def async_close(self) -> None:
        """Close the Modbus TCP connection."""
        self.client.close()

    async def _async_ensure_connected(self) -> None:
        if not self.client.connected:
            await self.client.connect()
        if not self.client.connected:
            raise UpdateFailed(f"Unable to connect to {self.host}:{self.port}")

    async def _read_holding_registers(self, address: int, count: int):
        try:
            return await self.client.read_holding_registers(
                address, count=count, slave=self.unit_id
            )
        except TypeError:
            return await self.client.read_holding_registers(
                address, count=count, device_id=self.unit_id
            )

    async def _write_registers(self, address: int, values: list[int]):
        try:
            return await self.client.write_registers(address, values, slave=self.unit_id)
        except TypeError:
            return await self.client.write_registers(address, values, device_id=self.unit_id)

    async def _async_read_u32(self, address: int) -> int | None:
        """Read a single U32 register pair.

        Returns None if the inverter reports its "not available" sentinel
        pattern instead of a real value (SMA/SunSpec convention), rather than
        surfacing a bogus large integer to entities.
        """
        result = await self._read_holding_registers(address, 2)
        if result is None or result.isError():
            raise UpdateFailed(f"Error reading register {address}: {result}")
        return decode_u32_or_none(result.registers)

    async def _async_read_operating_block(self) -> tuple[int | None, int | None]:
        """Read operating mode (40210) and active power limit % (40214) in one
        Modbus request, since they fall within the same 6-register block.
        This halves the round trips compared to reading them separately.
        """
        result = await self._read_holding_registers(OPERATING_BLOCK_START, OPERATING_BLOCK_COUNT)
        if result is None or result.isError():
            raise UpdateFailed(
                f"Error reading register block starting at {OPERATING_BLOCK_START}: {result}"
            )
        registers = result.registers
        operating_mode = decode_u32_or_none(
            registers[OPERATING_MODE_OFFSET : OPERATING_MODE_OFFSET + 2]
        )
        active_power_limit_percent = decode_u32_or_none(
            registers[
                ACTIVE_POWER_LIMIT_PERCENT_OFFSET : ACTIVE_POWER_LIMIT_PERCENT_OFFSET + 2
            ]
        )
        return operating_mode, active_power_limit_percent

    async def _async_grid_guard_login(self) -> None:
        """Unlock Grid Guard protected parameters.

        Called by _async_write_u32 only after a write has been rejected, not
        before every write: some inverters reject writes to operating mode /
        active power limit with a Modbus exception (ILLEGAL FUNCTION) unless
        Grid Guard is unlocked first.
        """
        if not self.grid_guard_code:
            return
        registers = encode_u32(int(self.grid_guard_code))
        result = await self._write_registers(REG_GRID_GUARD_CODE, registers)
        if result is None or result.isError():
            raise UpdateFailed(
                f"Error unlocking Grid Guard at register {REG_GRID_GUARD_CODE}: {result}"
            )

    async def _async_write_u32(self, address: int, value: int) -> int | None:
        """Write a U32 value and read it back to confirm the value actually applied.

        If the write is rejected and a Grid Guard code is configured, unlock
        Grid Guard and retry the write once before giving up: some inverters
        reject writes to protected registers (operating mode, active power
        limit) until Grid Guard is unlocked, and the unlock can expire, so we
        only pay for the extra round trip when a write actually fails.
        """
        registers = encode_u32(value)
        result = await self._write_registers(address, registers)
        if (result is None or result.isError()) and self.grid_guard_code:
            await self._async_grid_guard_login()
            await asyncio.sleep(GRID_GUARD_RETRY_DELAY_SECONDS)
            result = await self._write_registers(address, registers)
        if result is None or result.isError():
            raise UpdateFailed(f"Error writing register {address}: {result}")
        return await self._async_read_u32(address)

    async def _async_update_data(self) -> dict[str, int | None]:
        async with self._lock:
            try:
                await self._async_ensure_connected()
                operating_mode, active_power_limit_percent = await self._async_read_operating_block()
            except ModbusException as err:
                raise UpdateFailed(f"Modbus communication error: {err}") from err

        return {
            KEY_OPERATING_MODE: operating_mode,
            KEY_ACTIVE_POWER_LIMIT_PERCENT: active_power_limit_percent,
        }

    async def async_set_operating_mode(self, mode_value: int) -> None:
        """Write the operating mode and refresh entity state with the read-back value."""
        async with self._lock:
            try:
                await self._async_ensure_connected()
                actual = await self._async_write_u32(REG_OPERATING_MODE, mode_value)
            except ModbusException as err:
                raise UpdateFailed(f"Modbus communication error: {err}") from err
        data = dict(self.data or {})
        data[KEY_OPERATING_MODE] = actual
        self.async_set_updated_data(data)

    async def async_set_active_power_limit_percent(self, value: int) -> None:
        """Write the active power limit (%) and refresh entity state with the read-back value."""
        async with self._lock:
            try:
                await self._async_ensure_connected()
                actual = await self._async_write_u32(REG_ACTIVE_POWER_LIMIT_PERCENT, value)
            except ModbusException as err:
                raise UpdateFailed(f"Modbus communication error: {err}") from err
        data = dict(self.data or {})
        data[KEY_ACTIVE_POWER_LIMIT_PERCENT] = actual
        self.async_set_updated_data(data)
