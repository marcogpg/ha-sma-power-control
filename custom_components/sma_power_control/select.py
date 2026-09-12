"""Select entity for the SMA Sunny Tripower operating mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_NAME,
    DEFAULT_NAME,
    DOMAIN,
    LABEL_TO_OPERATING_MODE,
    OPERATING_MODE_TO_LABEL,
    build_device_info,
)
from .coordinator import KEY_OPERATING_MODE, SmaModbusCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the operating mode select entity."""
    coordinator: SmaModbusCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SmaOperatingModeSelect(coordinator, entry)])


class SmaOperatingModeSelect(CoordinatorEntity[SmaModbusCoordinator], SelectEntity):
    """Represents register 40210 (Operating mode active power setting)."""

    _attr_has_entity_name = True
    _attr_name = "Operating Mode"
    _attr_options = list(OPERATING_MODE_TO_LABEL.values())
    _attr_icon = "mdi:tune"

    def __init__(self, coordinator: SmaModbusCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_operating_mode"
        device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_NAME)
        self._attr_device_info = build_device_info(entry.entry_id, device_name)

    @property
    def current_option(self) -> str | None:
        if not self.coordinator.data:
            return None
        mode_value = self.coordinator.data.get(KEY_OPERATING_MODE)
        return OPERATING_MODE_TO_LABEL.get(mode_value)

    async def async_select_option(self, option: str) -> None:
        mode_value = LABEL_TO_OPERATING_MODE[option]
        current = self.coordinator.data.get(KEY_OPERATING_MODE) if self.coordinator.data else None
        if mode_value == current:
            return
        await self.coordinator.async_set_operating_mode(mode_value)
