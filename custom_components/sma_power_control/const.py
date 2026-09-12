"""Constants for the SMA Sunny Tripower integration."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

DOMAIN = "sma_power_control"

CONF_UNIT_ID = "unit_id"
CONF_DEVICE_NAME = "device_name"
CONF_GRID_GUARD_CODE = "grid_guard_code"

DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 3
DEFAULT_NAME = "SMA Sunny Tripower 4.0"

MANUFACTURER = "SMA"
MODEL = "STP4.0-3AV-40"

# Modbus holding register addresses (as confirmed working against the
# inverter via the native Home Assistant Modbus integration).
REG_OPERATING_MODE = 40210
REG_ACTIVE_POWER_LIMIT_PERCENT = 40214

# Grid Guard is SMA's installer-level lock on parameters that affect grid
# feed-in behavior. Per SMA's official Modbus Technical Information, writes
# to protected registers (operating mode, active power limit) are rejected
# with a Modbus exception (ILLEGAL FUNCTION) unless the Grid Guard code has
# been unlocked first by writing it (U32) here under unit ID 3; writing 0
# logs out. The login is tied to the client IP and only one client can be
# logged in with the code at a time (e.g. a portal/Sunny Explorer session
# can conflict with this integration's login).
REG_GRID_GUARD_CODE = 43090

# Empirically, the inverter needs a brief moment after the Grid Guard login
# write before it accepts the retried write; retrying immediately can still
# be rejected once even though the login itself succeeded.
GRID_GUARD_RETRY_DELAY_SECONDS = 1.0

# 40210 (operating mode) and 40214 (active power limit %) are 4 registers
# apart with a 2-register gap in between (reserved for a future W-based
# limit register). Both fit in a single 6-register read starting at 40210,
# which halves the round trips needed per poll compared to reading them
# separately.
OPERATING_BLOCK_START = REG_OPERATING_MODE
OPERATING_BLOCK_COUNT = 6
OPERATING_MODE_OFFSET = REG_OPERATING_MODE - OPERATING_BLOCK_START
ACTIVE_POWER_LIMIT_PERCENT_OFFSET = REG_ACTIVE_POWER_LIMIT_PERCENT - OPERATING_BLOCK_START

# Reserved for a future "Manual setting in W" number entity. The exact
# register for writing an absolute W setpoint under mode 1077 has not been
# confirmed against the inverter, so it is intentionally left unset.
REG_ACTIVE_POWER_LIMIT_W: int | None = None

# Reserved for a future "External active power setpoint" control. The
# register used to feed the external setpoint under mode 1079 is not known,
# so no write path is implemented for it yet.
REG_EXTERNAL_ACTIVE_POWER_SETPOINT: int | None = None

# Operating mode values (register 40210), confirmed against the inverter.
MODE_OFF = 303
MODE_MANUAL_W = 1077
MODE_MANUAL_PERCENT = 1078
MODE_EXTERNAL = 1079

OPERATING_MODE_TO_LABEL: dict[int, str] = {
    MODE_OFF: "Off",
    MODE_MANUAL_W: "Manual setting in W",
    MODE_MANUAL_PERCENT: "Manual setting in %",
    MODE_EXTERNAL: "External active power setpoint",
}

LABEL_TO_OPERATING_MODE: dict[str, int] = {
    label: mode for mode, label in OPERATING_MODE_TO_LABEL.items()
}

UPDATE_INTERVAL_SECONDS = 5


def build_device_info(entry_id: str, device_name: str = DEFAULT_NAME) -> "DeviceInfo":
    """Return the DeviceInfo shared by all entities of a config entry."""
    from homeassistant.helpers.device_registry import DeviceInfo

    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=device_name,
    )
