"""Number entity for the SMA Sunny Tripower active power limit (%)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME, DEFAULT_NAME, DOMAIN, build_device_info
from .coordinator import KEY_ACTIVE_POWER_LIMIT_PERCENT, SmaModbusCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the active power limit number entity."""
    coordinator: SmaModbusCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SmaActivePowerLimitPercentNumber(coordinator, entry)])


class SmaActivePowerLimitPercentNumber(CoordinatorEntity[SmaModbusCoordinator], NumberEntity):
    """Represents register 40214 (Active power limitation in %).

    Only meaningful when Operating Mode (register 40210) is set to
    "Manual setting in %" (1078). A separate number entity for the W-based
    limit (register TBD, used when mode is 1077) can be added later; see
    const.REG_ACTIVE_POWER_LIMIT_W.
    """

    _attr_has_entity_name = True
    _attr_name = "Active Power Limit"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:solar-power"

    def __init__(self, coordinator: SmaModbusCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_active_power_limit_percent"
        device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_NAME)
        self._attr_device_info = build_device_info(entry.entry_id, device_name)

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(KEY_ACTIVE_POWER_LIMIT_PERCENT)

    async def async_set_native_value(self, value: float) -> None:
        int_value = int(value)
        current = (
            self.coordinator.data.get(KEY_ACTIVE_POWER_LIMIT_PERCENT)
            if self.coordinator.data
            else None
        )
        if int_value == current:
            return
        await self.coordinator.async_set_active_power_limit_percent(int_value)
