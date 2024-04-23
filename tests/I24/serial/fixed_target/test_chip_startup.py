from unittest.mock import patch

import pytest

from mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_StartUp_py3v1 import (
    check_files,
    fiducials,
    get_format,
    pathli,
)


def test_fiducials():
    assert len(fiducials(0)) == 0
    assert len(fiducials(1)) == 0


def test_get_format_for_oxford_chip():
    # oxford chip
    fmt = get_format(0)
    assert fmt == [8, 8, 20, 20, 0.125, 0.800, 0.800]


def test_get_format_for_oxford_minichip():
    # 1 block of oxford chip
    fmt = get_format(3)
    assert fmt == [1, 1, 20, 20, 0.125, 0.0, 0.0]


@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_StartUp_py3v1.os")
@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_StartUp_py3v1.read_parameter_file"
)
def test_check_files(fake_read_params, mock_os, dummy_params_without_pp):
    fake_read_params.return_value = dummy_params_without_pp
    check_files("i24", [".a", ".b"])


@pytest.mark.parametrize(
    "list_in, way, reverse, expected_res",
    [
        (
            [1, 2, 3],
            "typewriter",
            False,
            [1, 2, 3] * 3,
        ),  # Result should be list * len(list)
        ([1, 2, 3], "typewriter", True, [3, 2, 1] * 3),  # list[::-1] * len(list)
        ([4, 5], "snake", False, [4, 5, 5, 4]),  # Snakes the list
        ([4, 5], "expand", False, [4, 4, 5, 5]),  # Repeats each value
    ],
)
def test_pathli(list_in, way, reverse, expected_res):
    assert pathli(list_in, way, reverse) == expected_res
