from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.i24.i24_vgonio import VGonio
from dodal.devices.zebra import Zebra

from mx_bluesky.i24.jungfrau_commissioning.plans.rotation_scan_plans import (
    cleanup_plan,
    get_rotation_scan_plan,
)
from mx_bluesky.i24.jungfrau_commissioning.plans.zebra_plans import arm_zebra
from mx_bluesky.i24.jungfrau_commissioning.utils.params import RotationScan


@patch(
    "mx_bluesky.i24.jungfrau_commissioning.plans.rotation_scan_plans.NexusFileHandlerCallback",
)
def test_rotation_scan_get_plan(
    nexus_callback: MagicMock, fake_create_devices_function
):
    minimal_params = RotationScan.from_file(
        "tests/unit_tests/beamlines/i24/jungfrau_commissioning/test_data/example_params.json"
    )
    with patch(
        "mx_bluesky.i24.jungfrau_commissioning.plans.rotation_scan_plans.create_rotation_scan_devices",
        fake_create_devices_function,
    ):
        plan = get_rotation_scan_plan(minimal_params)
    assert plan is not None
    nexus_callback.assert_called_once()


@patch(
    "bluesky.plan_stubs.wait",
)
async def test_cleanup_plan(bps_wait, fake_devices, RE: RunEngine):
    zebra: Zebra = fake_devices["zebra"]
    gonio: VGonio = fake_devices["gonio"]
    RE(arm_zebra(zebra))
    armed = await zebra.pc.arm.armed.get_value()
    assert armed.value == 1
    RE(cleanup_plan(zebra, gonio))
    armed = await zebra.pc.arm.armed.get_value()
    assert armed.value == 0


@patch(
    "bluesky.plan_stubs.wait",
)
@patch(
    "mx_bluesky.i24.jungfrau_commissioning.plans.rotation_scan_plans.NexusFileHandlerCallback",
)
def test_rotation_scan_do_plan(
    nexus_callback: MagicMock,
    bps_wait: MagicMock,
    fake_create_devices_function,
    RE: RunEngine,
):
    minimal_params = RotationScan.from_file(
        "tests/unit_tests/beamlines/i24/jungfrau_commissioning/test_data/example_params.json"
    )
    with patch(
        "mx_bluesky.i24.jungfrau_commissioning.plans.rotation_scan_plans.create_rotation_scan_devices",
        fake_create_devices_function,
    ):
        plan = get_rotation_scan_plan(minimal_params)

    RE(plan)
    devices = fake_create_devices_function()
    gonio: VGonio = devices["gonio"]
    assert gonio.omega.user_readback.get() == pytest.approx(-366.1)
