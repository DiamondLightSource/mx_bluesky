from unittest.mock import MagicMock, call, mock_open, patch

import pytest
from dodal.devices.i24.pmac import PMAC
from dodal.devices.zebra import Zebra
from ophyd_async.core import get_mock_put

from mx_bluesky.I24.serial.fixed_target.ft_utils import ChipType, MappingType
from mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Collect_py3v1 import (
    datasetsizei24,
    get_chip_prog_values,
    get_prog_num,
    load_motion_program_data,
    start_i24,
)

chipmap_str = """01status    P3011       1
02status    P3021       0
03status    P3031       0
04status    P3041       0"""


@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.caput")
def test_datasetsizei24_for_one_block_and_two_exposures(fake_caput):
    with patch(
        "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.open",
        mock_open(read_data=chipmap_str),
    ):
        tot_num_imgs = datasetsizei24(2, ChipType.Oxford, MappingType.Lite)
    assert tot_num_imgs == 800
    fake_caput.assert_called_once_with("ME14E-MO-IOC-01:GP10", 800)


def test_get_chip_prog_values():
    chip_dict = get_chip_prog_values(
        0,
        0,
        0,
        0,
        0,
        n_exposures=2,
    )
    assert isinstance(chip_dict, dict)
    assert chip_dict["X_NUM_STEPS"][1] == 20 and chip_dict["X_NUM_BLOCKS"][1] == 8
    assert chip_dict["PUMP_REPEAT"][1] == 0
    assert chip_dict["N_EXPOSURES"][1] == 2


@pytest.mark.parametrize(
    "chip_type, map_type, pump_repeat, expected_prog",
    [
        (0, 0, 0, 11),  # Oxford chip, full chip, no pump
        (0, 1, 0, 12),  # Oxford chip, map generated by mapping lite, no pump
        (2, "", 0, 11),  # Custom chip, map type not needed(full assumed), no pump
        (0, "", 2, 14),  # Oxford chip, assumes mapping lite, pump 2
        (3, "", 0, 11),  # Minichip, no map type, no pump probe
    ],
)
def test_get_prog_number(chip_type, map_type, pump_repeat, expected_prog):
    assert get_prog_num(chip_type, map_type, pump_repeat) == expected_prog


@pytest.mark.parametrize(
    "map_type, pump_repeat, checker, expected_calls",
    [
        (0, 0, False, ["P1100=1"]),  # Full chip, no pump probe, no checker
        (1, 0, False, ["P1200=1"]),  # Mapping lite, no pp, no checker
        (
            1,
            2,
            False,
            ["P1439=0", "P1441=0", "P1400=1"],
        ),  # Map irrelevant, pp to Repeat1, no checker
        (
            0,
            3,
            True,
            ["P1439=0", "P1439=1", "P1441=0", "P1400=1"],
        ),  # Map irrelevant, pp to Repeat2, checker enabled
        (
            1,
            8,
            False,
            ["P1439=0", "P1441=50", "P1400=1"],
        ),  # Map irrelevant, pp to Medium1, checker disabled
    ],
)
@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.caget")
def test_load_motion_program_data(
    fake_caget: MagicMock,
    map_type: int,
    pump_repeat: int,
    checker: bool,
    expected_calls: list,
    pmac: PMAC,
    RE,
):
    test_dict = {"N_EXPOSURES": [0, 1]}
    fake_caget.return_value = checker
    RE(load_motion_program_data(pmac, test_dict, map_type, pump_repeat))
    call_list = []
    for i in expected_calls:
        call_list.append(call(i, wait=True, timeout=10.0))
    mock_pmac_str = get_mock_put(pmac.pmac_string)
    mock_pmac_str.assert_has_calls(call_list)


@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.datasetsizei24")
@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.DCID")
@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.caput")
@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.caget")
@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.sup")
@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.sleep")
def test_start_i24_with_eiger(
    fake_sleep,
    fake_sup,
    fake_caget,
    fake_caput,
    fake_dcid,
    fake_size,
    zebra: Zebra,
    RE,
    aperture,
    backlight,
    beamstop,
    detector_stage,
    dummy_params_without_pp,
):
    fake_size.return_value = 800
    RE(
        start_i24(
            zebra,
            aperture,
            backlight,
            beamstop,
            detector_stage,
            dummy_params_without_pp,
        )
    )
    assert fake_sup.eiger.call_count == 1
    assert fake_sup.setup_beamline_for_collection_plan.call_count == 1
    assert fake_sup.setup_beamline_for_quickshot_plan.call_count == 1
    # Pilatus gets called for hack to create directory
    assert fake_sup.pilatus.call_count == 2
    assert fake_dcid.call_count == 1
