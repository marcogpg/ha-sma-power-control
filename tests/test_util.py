"""Unit tests for U32 encode/decode helpers and operating mode mapping.

These tests have no Home Assistant runtime dependency and can be run with
plain pytest.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "sma_power_control"))

from util import decode_u32, decode_u32_or_none, encode_u32, is_invalid_u32  # noqa: E402
from const import (  # noqa: E402
    LABEL_TO_OPERATING_MODE,
    MODE_EXTERNAL,
    MODE_MANUAL_PERCENT,
    MODE_MANUAL_W,
    MODE_OFF,
    OPERATING_MODE_TO_LABEL,
)


class TestOperatingModeMapping:
    def test_mode_to_label(self):
        assert OPERATING_MODE_TO_LABEL[MODE_OFF] == "Off"
        assert OPERATING_MODE_TO_LABEL[MODE_MANUAL_W] == "Manual setting in W"
        assert OPERATING_MODE_TO_LABEL[MODE_MANUAL_PERCENT] == "Manual setting in %"
        assert OPERATING_MODE_TO_LABEL[MODE_EXTERNAL] == "External active power setpoint"

    def test_label_to_mode(self):
        assert LABEL_TO_OPERATING_MODE["Off"] == MODE_OFF
        assert LABEL_TO_OPERATING_MODE["Manual setting in W"] == MODE_MANUAL_W
        assert LABEL_TO_OPERATING_MODE["Manual setting in %"] == MODE_MANUAL_PERCENT
        assert (
            LABEL_TO_OPERATING_MODE["External active power setpoint"] == MODE_EXTERNAL
        )

    def test_round_trip(self):
        for mode_value, label in OPERATING_MODE_TO_LABEL.items():
            assert LABEL_TO_OPERATING_MODE[label] == mode_value


class TestU32Encoding:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (20, [0, 20]),
            (50, [0, 50]),
            (100, [0, 100]),
            (1078, [0, 1078]),
            (4000, [0, 4000]),
            (303, [0, 303]),
            (1077, [0, 1077]),
            (1079, [0, 1079]),
            (0, [0, 0]),
            (65536, [1, 0]),
            (0xFFFFFFFF, [0xFFFF, 0xFFFF]),
        ],
    )
    def test_encode_u32(self, value, expected):
        assert encode_u32(value) == expected

    def test_encode_u32_out_of_range(self):
        with pytest.raises(ValueError):
            encode_u32(-1)
        with pytest.raises(ValueError):
            encode_u32(0x100000000)

    def test_encode_u32_rejects_non_int(self):
        with pytest.raises(TypeError):
            encode_u32(20.0)

    @pytest.mark.parametrize(
        ("registers", "expected"),
        [
            ([0, 20], 20),
            ([0, 1078], 1078),
            ([0, 4000], 4000),
            ([1, 0], 65536),
            ([0xFFFF, 0xFFFF], 0xFFFFFFFF),
        ],
    )
    def test_decode_u32(self, registers, expected):
        assert decode_u32(registers) == expected

    def test_round_trip_encode_decode(self):
        for value in (0, 20, 50, 100, 303, 1077, 1078, 1079, 4000):
            assert decode_u32(encode_u32(value)) == value


class TestInvalidU32Sentinels:
    """SMA/SunSpec use specific register patterns to mean "not available"."""

    @pytest.mark.parametrize(
        "registers",
        [
            [0xFFFF, 0xFFFF],
            [0x8000, 0x0000],
        ],
    )
    def test_is_invalid_u32_detects_sentinels(self, registers):
        assert is_invalid_u32(registers) is True

    @pytest.mark.parametrize(
        "registers",
        [
            [0, 20],
            [0, 1078],
            [0xFFFF, 0x0000],
            [0x8000, 0xFFFF],
        ],
    )
    def test_is_invalid_u32_accepts_real_values(self, registers):
        assert is_invalid_u32(registers) is False

    @pytest.mark.parametrize(
        "registers",
        [[0xFFFF, 0xFFFF], [0x8000, 0x0000]],
    )
    def test_decode_u32_or_none_returns_none_for_sentinels(self, registers):
        assert decode_u32_or_none(registers) is None

    def test_decode_u32_or_none_returns_value_for_real_registers(self):
        assert decode_u32_or_none([0, 20]) == 20
        assert decode_u32_or_none([0, 4000]) == 4000
