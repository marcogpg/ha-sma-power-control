"""Pure helper functions for U32 Modbus register encoding/decoding."""
from __future__ import annotations

_U32_MAX = 0xFFFFFFFF

# SMA/SunSpec "not available" sentinel patterns for U32 registers (high, low).
# The inverter can return these instead of a real value when a register is
# transiently not applicable (e.g. read shortly after a mode change).
_INVALID_U32_SENTINELS = frozenset({(0xFFFF, 0xFFFF), (0x8000, 0x0000)})


def encode_u32(value: int) -> list[int]:
    """Encode an integer into two 16-bit Modbus registers (high word first).

    Example: 20 -> [0, 20], 1078 -> [0, 1078].
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"value must be an int, got {type(value)!r}")
    if not 0 <= value <= _U32_MAX:
        raise ValueError(f"value {value} out of range for U32 (0-{_U32_MAX})")
    high = (value >> 16) & 0xFFFF
    low = value & 0xFFFF
    return [high, low]


def decode_u32(registers: list[int]) -> int:
    """Decode two 16-bit Modbus registers (high word first) into an integer."""
    if len(registers) < 2:
        raise ValueError("registers must contain at least 2 elements")
    high, low = registers[0], registers[1]
    return (high << 16) | low


def is_invalid_u32(registers: list[int]) -> bool:
    """Return True if the register pair is an SMA "not available" sentinel."""
    if len(registers) < 2:
        raise ValueError("registers must contain at least 2 elements")
    return (registers[0], registers[1]) in _INVALID_U32_SENTINELS


def decode_u32_or_none(registers: list[int]) -> int | None:
    """Decode a U32 register pair, returning None for "not available" sentinels."""
    if is_invalid_u32(registers):
        return None
    return decode_u32(registers)
