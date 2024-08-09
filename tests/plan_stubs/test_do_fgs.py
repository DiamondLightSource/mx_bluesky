from unittest.mock import MagicMock, patch

import pytest
from bluesky import plan_stubs as bps
from bluesky.plan_stubs import null
from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator
from dodal.beamlines.i03 import eiger
from dodal.devices.fast_grid_scan import ZebraFastGridScan
from dodal.devices.synchrotron import Synchrotron, SynchrotronMode
from ophyd_async.core import DeviceCollector, set_mock_value

from mx_bluesky.plan_stubs.do_fgs import do_fgs


@pytest.fixture
def fgs_devices(RE):
    with DeviceCollector(mock=True):
        synchrotron = Synchrotron()
        grid_scan_device = ZebraFastGridScan("zebra_fgs")

    # Eiger done separately as not ophyd-async yet
    detector = eiger(fake_with_ophyd_sim=True)

    return {
        "synchrotron": synchrotron,
        "grid_scan_device": grid_scan_device,
        "detector": detector,
    }


def test_pre_and_post_plans_called_optionally(
    sim_run_engine: RunEngineSimulator, fgs_devices
):
    def null_plan():
        yield from null()

    synchrotron = fgs_devices["synchrotron"]
    detector = fgs_devices["detector"]
    fgs_device = fgs_devices["grid_scan_device"]
    post_plan = MagicMock(side_effect=null_plan)
    pre_plan = MagicMock(side_effect=null_plan)
    with patch("mx_bluesky.plan_stubs.do_fgs.check_topup_and_wait_if_necessary"):
        msgs = sim_run_engine.simulate_plan(
            do_fgs(
                fgs_device,
                detector,
                synchrotron,
                post_plans=post_plan,
                pre_plans=pre_plan,
            )
        )
        null_messages = [msg for msg in msgs if msg.command == "null"]
        assert len(null_messages) == 2
    with patch("mx_bluesky.plan_stubs.do_fgs.check_topup_and_wait_if_necessary"):
        msgs = sim_run_engine.simulate_plan(
            do_fgs(
                fgs_device,
                detector,
                synchrotron,
            )
        )
        null_messages = [msg for msg in msgs if msg.command == "null"]
        assert len(null_messages) == 0


def test_do_fgs_with_run_engine(RE: RunEngine, fgs_devices):
    synchrotron = fgs_devices["synchrotron"]
    set_mock_value(synchrotron.synchrotron_mode, SynchrotronMode.DEV)
    detector = fgs_devices["detector"]
    fgs_device: ZebraFastGridScan = fgs_devices["grid_scan_device"]

    def do_fgs_plan_in_run():
        yield from bps.open_run()
        yield from do_fgs(fgs_device, detector, synchrotron)
        yield from bps.close_run()

    set_mock_value(fgs_device.status, 1)

    with patch("mx_bluesky.plan_stubs.do_fgs.bps.complete"):
        RE(do_fgs_plan_in_run())
