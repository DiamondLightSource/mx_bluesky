import asyncio
from unittest.mock import ANY, MagicMock, call, mock_open, patch

import bluesky.plan_stubs as bps
import pytest
from bluesky.utils import FailedStatus
from dodal.devices.hutch_shutter import HutchShutter
from dodal.devices.i24.pmac import PMAC
from dodal.devices.zebra import Zebra
from ophyd_async.core import callback_on_mock_put, get_mock_put, set_mock_value

from mx_bluesky.beamlines.i24.serial.fixed_target.ft_utils import (
    ChipType,
    MappingType,
    PumpProbeSetting,
)
from mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1 import (
    datasetsizei24,
    finish_i24,
    get_chip_prog_values,
    get_prog_num,
    kickoff_and_complete_collection,
    load_motion_program_data,
    run_aborted_plan,
    start_i24,
    tidy_up_after_collection_plan,
)

chipmap_str = """01status    P3011       1
02status    P3021       0
03status    P3031       0
04status    P3041       0"""


def fake_generator(value):
    yield from bps.null()
    return value


@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.caput")
def test_datasetsizei24_for_one_block_and_two_exposures(
    fake_caput, dummy_params_without_pp
):
    with patch(
        "mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.open",
        mock_open(read_data=chipmap_str),
    ):
        tot_num_imgs = datasetsizei24(2, dummy_params_without_pp.chip, MappingType.Lite)
    assert tot_num_imgs == 800
    fake_caput.assert_called_once_with("ME14E-MO-IOC-01:GP10", 800)


def test_get_chip_prog_values(dummy_params_without_pp):
    dummy_params_without_pp.num_exposures = 2
    chip_dict = get_chip_prog_values(
        dummy_params_without_pp,
    )
    assert isinstance(chip_dict, dict)
    assert chip_dict["X_NUM_STEPS"][1] == 20 and chip_dict["X_NUM_BLOCKS"][1] == 8
    assert chip_dict["PUMP_REPEAT"][1] == 0
    assert chip_dict["N_EXPOSURES"][1] == 2


@pytest.mark.parametrize(
    "chip_type, map_type, pump_repeat, expected_prog",
    [
        (ChipType.Oxford, MappingType.NoMap, PumpProbeSetting.NoPP, 11),
        (ChipType.Oxford, MappingType.Lite, PumpProbeSetting.NoPP, 12),
        (ChipType.OxfordInner, MappingType.Lite, PumpProbeSetting.NoPP, 12),
        (ChipType.Custom, MappingType.Lite, PumpProbeSetting.NoPP, 11),
        (ChipType.Minichip, MappingType.NoMap, PumpProbeSetting.NoPP, 11),
        (ChipType.Oxford, MappingType.Lite, PumpProbeSetting.Short2, 14),
        (ChipType.Minichip, MappingType.NoMap, PumpProbeSetting.Repeat5, 14),
        (ChipType.Custom, MappingType.Lite, PumpProbeSetting.Medium1, 14),
    ],
)
def test_get_prog_number(chip_type, map_type, pump_repeat, expected_prog):
    assert get_prog_num(chip_type, map_type, pump_repeat) == expected_prog


def test_get_prog_number_raises_error_for_disabled_map_setting():
    with pytest.raises(ValueError):
        get_prog_num(ChipType.Oxford, MappingType.Full, PumpProbeSetting.NoPP)


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
@patch(
    "mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.bps.sleep"
)
def test_load_motion_program_data(
    mock_sleep,
    map_type: int,
    pump_repeat: int,
    checker: bool,
    expected_calls: list,
    pmac: PMAC,
    RE,
):
    test_dict = {"N_EXPOSURES": [0, 1]}
    RE(load_motion_program_data(pmac, test_dict, map_type, pump_repeat, checker))
    call_list = []
    for i in expected_calls:
        call_list.append(call(i, wait=True, timeout=10.0))
    mock_pmac_str = get_mock_put(pmac.pmac_string)
    mock_pmac_str.assert_has_calls(call_list)


@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.DCID")
@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.caput")
@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.caget")
@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.sup")
@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.sleep")
def test_start_i24_with_eiger(
    fake_sleep,
    fake_sup,
    fake_caget,
    fake_caput,
    fake_dcid,
    zebra: Zebra,
    shutter: HutchShutter,
    RE,
    aperture,
    backlight,
    beamstop,
    detector_stage,
    dummy_params_without_pp,
):
    dummy_params_without_pp.total_num_images = 800
    RE(
        start_i24(
            zebra,
            aperture,
            backlight,
            beamstop,
            detector_stage,
            shutter,
            dummy_params_without_pp,
            fake_dcid,
        )
    )
    assert fake_sup.eiger.call_count == 1
    assert fake_sup.setup_beamline_for_collection_plan.call_count == 1
    assert fake_sup.move_detector_stage_to_position_plan.call_count == 1
    # Pilatus gets called for hack to create directory
    assert fake_sup.pilatus.call_count == 2
    assert fake_dcid.generate_dcid.call_count == 1

    shutter_call_list = [
        call("Reset", wait=True, timeout=10.0),
        call("Open", wait=True, timeout=10.0),
    ]
    mock_shutter = get_mock_put(shutter.control)
    mock_shutter.assert_has_calls(shutter_call_list)


@patch(
    "mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.write_userlog"
)
@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.sleep")
@patch(
    "mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.cagetstring"
)
@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.caget")
@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.sup")
@patch(
    "mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.reset_zebra_when_collection_done_plan"
)
@patch("mx_bluesky.beamlines.i24.serial.extruder.i24ssx_Extruder_Collect_py3v2.bps.rd")
def test_finish_i24(
    fake_read,
    fake_reset_zebra,
    fake_sup,
    fake_caget,
    fake_cagetstring,
    fake_sleep,
    fake_userlog,
    zebra,
    pmac,
    shutter,
    dcm,
    dummy_params_without_pp,
    RE,
):
    fake_read.side_effect = [fake_generator(0.6)]
    fake_caget.return_value = 0.0
    fake_cagetstring.return_value = "chip_01"
    RE(finish_i24(zebra, pmac, shutter, dcm, dummy_params_without_pp))

    fake_reset_zebra.assert_called_once()

    fake_sup.eiger.assert_called_once_with("return-to-normal", None)

    mock_pmac_string = get_mock_put(pmac.pmac_string)
    mock_pmac_string.assert_has_calls([call("!x0y0z0", wait=True, timeout=ANY)])

    mock_shutter = get_mock_put(shutter.control)
    mock_shutter.assert_has_calls([call("Close", wait=True, timeout=ANY)])

    fake_userlog.assert_called_once_with(dummy_params_without_pp, "chip_01", 0.0, 0.6)


@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.DCID")
def test_run_aborted_plan(fake_dcid: MagicMock, pmac: PMAC, RE, done_status):
    pmac.abort_program.trigger = MagicMock(return_value=done_status)
    RE(run_aborted_plan(pmac, fake_dcid))

    pmac.abort_program.trigger.assert_called_once()
    fake_dcid.collection_complete.assert_called_once_with(ANY, aborted=True)


@patch(
    "mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.finish_i24"
)
@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.sleep")
@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.DCID")
@patch("mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.caput")
async def test_tidy_up_after_collection_plan(
    fake_caput,
    fake_dcid,
    fake_sleep,
    mock_finish,
    zebra,
    pmac,
    shutter,
    dcm,
    RE,
    dummy_params_without_pp,
):
    RE(
        tidy_up_after_collection_plan(
            zebra, pmac, shutter, dcm, dummy_params_without_pp, fake_dcid
        )
    )
    assert await zebra.inputs.soft_in_2.get_value() == "No"

    fake_dcid.notify_end.assert_called_once()

    fake_caput.assert_has_calls([call(ANY, 0), call(ANY, "Done")])

    mock_finish.assert_called_once()


@patch(
    "mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.calculate_collection_timeout"
)
async def test_kick_off_and_complete_collection(
    fake_collection_time, pmac, dummy_params_with_pp, RE, done_status
):
    pmac.run_program.kickoff = MagicMock(return_value=done_status)
    pmac.run_program.complete = MagicMock(return_value=done_status)

    async def go_high_then_low():
        set_mock_value(pmac.scanstatus, 1)
        await asyncio.sleep(0.1)
        set_mock_value(pmac.scanstatus, 0)

    callback_on_mock_put(
        pmac.pmac_string,
        lambda *args, **kwargs: asyncio.create_task(go_high_then_low()),  # type: ignore
    )
    fake_collection_time.return_value = 2.0
    res = RE(kickoff_and_complete_collection(pmac, dummy_params_with_pp))

    assert await pmac.program_number.get_value() == 14
    assert await pmac.collection_time.get_value() == 2.0

    pmac.run_program.kickoff.assert_called_once()
    pmac.run_program.complete.assert_called_once()

    assert res.exit_status == "success"


@patch(
    "mx_bluesky.beamlines.i24.serial.fixed_target.i24ssx_Chip_Collect_py3v1.calculate_collection_timeout"
)
async def test_kickoff_and_complete_fails_if_scan_status_pv_does_not_change(
    fake_collection_time, pmac, dummy_params_without_pp, RE
):
    fake_collection_time.return_value = 1.0
    pmac.run_program.KICKOFF_TIMEOUT = 0.1
    set_mock_value(pmac.scanstatus, 0)
    with pytest.raises(FailedStatus):
        RE(kickoff_and_complete_collection(pmac, dummy_params_without_pp))
