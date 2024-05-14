import json
from typing import List
from unittest.mock import ANY, MagicMock, call, mock_open, patch

import pytest
from dodal.devices.i24.pmac import PMAC

from mx_bluesky.I24.serial.fixed_target.ft_utils import Fiducials
from mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1 import (
    cs_maker,
    cs_reset,
    laser_control,
    moveto,
    moveto_preset,
    pumpprobe_calc,
    scrape_mtr_directions,
    scrape_mtr_fiducials,
)

mtr_dir_str = """#Some words
mtr1_dir=1
mtr2_dir=-1
mtr3_dir=-1"""

fiducial_1_str = """MTR RBV RAW Corr f_value
MTR1 0 0 1 0
MTR2 1 -1 -1 1
MTR3 0 0 -1 0"""

cs_json = '{"scalex":1, "scaley":2, "scalez":3, "skew":-0.5, "Sx_dir":1, "Sy_dir":-1, "Sz_dir":0}'


@pytest.fixture
def fake_pmac() -> MagicMock:
    mock_pmac: PMAC = MagicMock(spec=PMAC)
    return mock_pmac


@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.caget")
def test_moveto_oxford_origin(fake_caget: MagicMock, fake_pmac: MagicMock, RE):
    fake_caget.return_value = 0
    RE(moveto(Fiducials.origin, fake_pmac))
    assert fake_caget.call_count == 1
    fake_pmac.x.assert_has_calls([call.move(0.0, wait=False)])
    fake_pmac.y.assert_has_calls([call.move(0.0, wait=False)])


@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.caget")
def test_moveto_oxford_inner_f1(fake_caget: MagicMock, fake_pmac: MagicMock, RE):
    fake_caget.return_value = 1
    RE(moveto(Fiducials.fid1, fake_pmac))
    assert fake_caget.call_count == 1
    fake_pmac.x.assert_has_calls([call.move(24.60, wait=False)])
    fake_pmac.y.assert_has_calls([call.move(0.0, wait=False)])


def test_moveto_chip_unknown(fake_pmac: MagicMock, RE):
    RE(moveto("zero", fake_pmac))
    fake_pmac.pmac_string.assert_has_calls([call.set("!x0y0z0"), call.set().wait()])


@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.caput")
def test_moveto_preset(fake_caput: MagicMock, fake_pmac: MagicMock, RE):
    RE(moveto_preset("zero", fake_pmac))
    fake_pmac.pmac_string.assert_has_calls([call.set("!x0y0z0"), call.set().wait()])

    RE(moveto_preset("load_position", fake_pmac))
    assert fake_caput.call_count == 3


@pytest.mark.parametrize(
    "pos_request, expected_num_caput, expected_pmac_move",
    [
        ("collect_position", 3, [0.0, 0.0, 0.0]),
        ("microdrop_position", 0, [6.0, -7.8, 0.0]),
    ],
)
@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.caput")
def test_moveto_preset_with_pmac_move(
    fake_caput: MagicMock,
    pos_request: str,
    expected_num_caput: int,
    expected_pmac_move: List,
    fake_pmac: MagicMock,
    RE,
):
    RE(moveto_preset(pos_request, fake_pmac))
    assert fake_caput.call_count == expected_num_caput

    fake_pmac.x.assert_has_calls([call.move(expected_pmac_move[0], wait=False)])
    fake_pmac.y.assert_has_calls([call.move(expected_pmac_move[1], wait=False)])
    fake_pmac.z.assert_has_calls([call.move(expected_pmac_move[2], wait=False)])


@pytest.mark.parametrize(
    "laser_setting, expected_pmac_string",
    [
        ("laser1on", " M712=1 M711=1"),
        ("laser1off", " M712=0 M711=1"),
        ("laser2on", " M812=1 M811=1"),
        ("laser2off", " M812=0 M811=1"),
    ],
)
def test_laser_control_on_and_off(
    laser_setting: str, expected_pmac_string: str, fake_pmac: MagicMock, RE
):
    RE(laser_control(laser_setting, fake_pmac))

    fake_pmac.pmac_string.assert_has_calls(
        [call.set(expected_pmac_string), call.set().wait()]
    )


@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.caget")
def test_laser_control_burn_setting(fake_caget: MagicMock, fake_pmac: MagicMock, RE):
    fake_caget.return_value = 0.1
    RE(laser_control("laser1burn", fake_pmac))

    fake_pmac.pmac_string.assert_has_calls(
        [
            call.set(" M712=1 M711=1"),
            call.set().wait(),
            call.set(" M712=0 M711=1"),
            call.set().wait(),
        ]
    )


@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.open",
    mock_open(read_data=mtr_dir_str),
)
def test_scrape_mtr_directions():
    res = scrape_mtr_directions()
    assert len(res) == 3
    assert res == (1.0, -1.0, -1.0)


@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.open",
    mock_open(read_data=fiducial_1_str),
)
def test_scrape_mtr_fiducials():
    res = scrape_mtr_fiducials(1)
    assert len(res) == 3
    assert res == (0.0, 1.0, 0.0)


def test_cs_reset(fake_pmac: MagicMock, RE):
    RE(cs_reset(fake_pmac))
    fake_pmac.pmac_string.assert_has_calls(
        [
            call.set("&2"),
            call.set().wait(),
            call.set("#1->-10000X+0Y+0Z"),
            call.set().wait(),
            call.set("#2->+0X+10000Y+0Z"),
            call.set().wait(),
            call.set("#3->0X+0Y+10000Z"),
            call.set().wait(),
        ]
    )


@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.open",
    mock_open(read_data='{"a":11, "b":12,}'),
)
@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.caget")
@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.scrape_mtr_directions"
)
@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.scrape_mtr_fiducials"
)
def test_cs_maker_raises_error_for_invalid_json(
    fake_fid: MagicMock,
    fake_dir: MagicMock,
    fake_caget: MagicMock,
    fake_pmac: MagicMock,
    RE,
):
    fake_dir.return_value = (1, 1, 1)
    fake_fid.return_value = (0, 0, 0)
    with pytest.raises(json.JSONDecodeError):
        RE(cs_maker(fake_pmac))


@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.open",
    mock_open(read_data='{"scalex":11, "skew":12}'),
)
@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.caget")
@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.scrape_mtr_directions"
)
@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.scrape_mtr_fiducials"
)
def test_cs_maker_raises_error_for_missing_key_in_json(
    fake_fid: MagicMock,
    fake_dir: MagicMock,
    fake_caget: MagicMock,
    fake_pmac: MagicMock,
    RE,
):
    fake_dir.return_value = (1, 1, 1)
    fake_fid.return_value = (0, 0, 0)
    with pytest.raises(KeyError):
        RE(cs_maker(fake_pmac))


@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.open",
    mock_open(read_data=cs_json),
)
@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.caget")
@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.scrape_mtr_directions"
)
@patch(
    "mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.scrape_mtr_fiducials"
)
def test_cs_maker_raises_error_for_wrong_direction_in_json(
    fake_fid: MagicMock,
    fake_dir: MagicMock,
    fake_caget: MagicMock,
    fake_pmac: MagicMock,
    RE,
):
    fake_dir.return_value = (1, 1, 1)
    fake_fid.return_value = (0, 0, 0)
    with pytest.raises(ValueError):
        RE(cs_maker(fake_pmac))


@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.caput")
@patch("mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_Manager_py3v1.caget")
def test_pumpprobe_calc(fake_caget: MagicMock, fake_caput: MagicMock, RE):
    fake_caget.side_effect = [0.01, 0.005]
    RE(pumpprobe_calc())
    assert fake_caget.call_count == 2
    assert fake_caput.call_count == 5
    fake_caput.assert_has_calls(
        [
            call(ANY, 0.62),
            call(ANY, 1.24),
            call(ANY, 1.86),
            call(ANY, 3.1),
            call(ANY, 6.2),
        ]
    )
