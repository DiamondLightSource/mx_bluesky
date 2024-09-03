import uuid
from collections.abc import Callable
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
import pytest_asyncio
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.aperturescatterguard import ApertureValue
from dodal.devices.smargon import Smargon
from ophyd.sim import NullStatus
from ophyd_async.core import set_mock_value

from mx_bluesky.hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_during_collection,
    read_hardware_pre_collection,
)
from mx_bluesky.hyperion.device_setup_plans.xbpm_feedback import (
    transmission_and_xbpm_feedback_for_collection_decorator,
)
from mx_bluesky.hyperion.exceptions import WarningException
from mx_bluesky.hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
    flyscan_xray_centre,
)
from mx_bluesky.hyperion.external_interaction.callbacks.common.callback_util import (
    create_gridscan_callbacks,
)
from mx_bluesky.hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from mx_bluesky.hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    GridscanNexusFileCallback,
)
from mx_bluesky.hyperion.external_interaction.ispyb.ispyb_store import IspybIds
from mx_bluesky.hyperion.parameters.constants import CONST
from mx_bluesky.hyperion.parameters.gridscan import ThreeDGridScan

from ....conftest import default_raw_params
from ..external_interaction.conftest import (  # noqa
    fetch_comment,
    zocalo_env,
)


@pytest.fixture
def params():
    params = ThreeDGridScan(**default_raw_params())
    params.beamline = CONST.SIM.BEAMLINE
    params.zocalo_environment = "dev_artemis"
    yield params


@pytest.fixture()
def callbacks(params):
    with patch(
        "mx_bluesky.hyperion.external_interaction.callbacks.xray_centre.nexus_callback.NexusWriter"
    ):
        _, ispyb_cb = create_gridscan_callbacks()
        ispyb_cb.ispyb_config = CONST.SIM.DEV_ISPYB_DATABASE_CFG
    yield callbacks


def reset_positions(smargon: Smargon):
    yield from bps.mv(smargon.x, -1, smargon.y, -1, smargon.z, -1)


@pytest_asyncio.fixture
async def fxc_composite():
    with (
        patch("dodal.devices.zocalo.zocalo_results._get_zocalo_connection"),
        patch("dodal.devices.zocalo.zocalo_results.workflows.recipe"),
        patch("dodal.devices.zocalo.zocalo_results.workflows.recipe"),
    ):
        zocalo = i03.zocalo()

    composite = FlyScanXRayCentreComposite(
        attenuator=i03.attenuator(),
        aperture_scatterguard=i03.aperture_scatterguard(),
        backlight=i03.backlight(),
        dcm=i03.dcm(fake_with_ophyd_sim=True),
        eiger=i03.eiger(),
        zebra_fast_grid_scan=i03.zebra_fast_grid_scan(),
        flux=i03.flux(fake_with_ophyd_sim=True),
        robot=i03.robot(fake_with_ophyd_sim=True),
        panda=i03.panda(fake_with_ophyd_sim=True),
        panda_fast_grid_scan=i03.panda_fast_grid_scan(fake_with_ophyd_sim=True),
        s4_slit_gaps=i03.s4_slit_gaps(),
        smargon=i03.smargon(),
        undulator=i03.undulator(),
        synchrotron=i03.synchrotron(fake_with_ophyd_sim=True),
        xbpm_feedback=i03.xbpm_feedback(fake_with_ophyd_sim=True),
        zebra=i03.zebra(),
        zocalo=zocalo,
    )

    await composite.robot.barcode._backend.put("ABCDEFGHIJ")  # type: ignore
    composite.dcm.energy_in_kev.user_readback.sim_put(12.345)  # type: ignore

    large = composite.aperture_scatterguard._loaded_positions[ApertureValue.LARGE]
    await composite.aperture_scatterguard._set_raw_unsafe(large)
    composite.eiger.cam.manual_trigger.put("Yes")
    composite.eiger.odin.check_odin_initialised = lambda: (True, "")
    composite.eiger.stage = MagicMock(return_value=NullStatus())
    composite.eiger.unstage = MagicMock(return_value=NullStatus())

    set_mock_value(composite.xbpm_feedback.pos_ok, True)
    set_mock_value(composite.xbpm_feedback.pos_stable, True)

    return composite


@pytest.mark.s03
def test_s03_devices_connect(fxc_composite: FlyScanXRayCentreComposite):
    assert fxc_composite.aperture_scatterguard
    assert fxc_composite.backlight


@pytest.mark.s03
def test_read_hardware_pre_collection(
    RE: RunEngine,
    fxc_composite: FlyScanXRayCentreComposite,
):
    @bpp.run_decorator()
    def read_run(u, s, g, r, a, f, dcm, ap_sg, sm):
        yield from read_hardware_pre_collection(
            undulator=u, synchrotron=s, s4_slit_gaps=g, robot=r, smargon=sm
        )
        yield from read_hardware_during_collection(
            ap_sg, a, f, dcm, fxc_composite.eiger
        )

    RE(
        read_run(
            fxc_composite.undulator,
            fxc_composite.synchrotron,
            fxc_composite.s4_slit_gaps,
            fxc_composite.robot,
            fxc_composite.attenuator,
            fxc_composite.flux,
            fxc_composite.dcm,
            fxc_composite.aperture_scatterguard,
            fxc_composite.smargon,
        )
    )


@pytest.mark.s03
async def test_xbpm_feedback_decorator(
    RE: RunEngine,
    fxc_composite: FlyScanXRayCentreComposite,
    params: ThreeDGridScan,
    callbacks: tuple[GridscanNexusFileCallback, GridscanISPyBCallback],
):
    # This test is currently kind of more a unit test since we are faking XBPM feedback
    # with ophyd.sim, but it should continue to pass when we replace it with something
    # in S03

    @transmission_and_xbpm_feedback_for_collection_decorator(
        fxc_composite.xbpm_feedback,
        fxc_composite.attenuator,
        params.transmission_frac,
    )
    def decorated_plan():
        yield from bps.sleep(0.1)

    RE(decorated_plan())
    assert await fxc_composite.xbpm_feedback.pos_stable.get_value() == 1


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait", autospec=True)
@patch("bluesky.plan_stubs.kickoff", autospec=True)
@patch("bluesky.plan_stubs.complete", autospec=True)
@patch(
    "mx_bluesky.hyperion.experiment_plans.flyscan_xray_centre_plan.run_gridscan_and_move",
    autospec=True,
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.flyscan_xray_centre_plan.set_zebra_shutter_to_manual",
    autospec=True,
)
def test_full_plan_tidies_at_end(
    set_shutter_to_manual: MagicMock,
    run_gridscan_and_move: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    fxc_composite: FlyScanXRayCentreComposite,
    params: ThreeDGridScan,
    RE: RunEngine,
    callbacks: tuple[GridscanNexusFileCallback, GridscanISPyBCallback],
):
    RE(reset_positions(fxc_composite.smargon))
    nexus_cb, ispyb_cb = callbacks
    nexus_cb.nexus_writer_1 = MagicMock()
    nexus_cb.nexus_writer_2 = MagicMock()
    ispyb_cb.ispyb_ids = IspybIds(
        data_collection_ids=(0, 0), data_collection_group_id=0, grid_ids=(0,)
    )
    [RE.subscribe(cb) for cb in callbacks]
    RE(flyscan_xray_centre(fxc_composite, params))
    set_shutter_to_manual.assert_called_once()


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait", autospec=True)
@patch("bluesky.plan_stubs.kickoff", autospec=True)
@patch("bluesky.plan_stubs.complete", autospec=True)
@patch(
    "mx_bluesky.hyperion.experiment_plans.flyscan_xray_centre_plan.run_gridscan_and_move",
    autospec=True,
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.flyscan_xray_centre_plan.set_zebra_shutter_to_manual",
    autospec=True,
)
def test_full_plan_tidies_at_end_when_plan_fails(
    set_shutter_to_manual: MagicMock,
    run_gridscan_and_move: MagicMock,
    complete: MagicMock,
    kickoff: MagicMock,
    wait: MagicMock,
    fxc_composite: FlyScanXRayCentreComposite,
    params: ThreeDGridScan,
    RE: RunEngine,
):
    class _Exception(Exception): ...

    run_gridscan_and_move.side_effect = _Exception()
    with pytest.raises(_Exception):
        RE(flyscan_xray_centre(fxc_composite, params))
    set_shutter_to_manual.assert_called_once()


@patch(
    "mx_bluesky.hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger"
)
@pytest.mark.s03
def test_GIVEN_scan_invalid_WHEN_plan_run_THEN_ispyb_entry_made_but_no_zocalo_entry(
    zocalo_trigger: MagicMock,
    RE: RunEngine,
    fxc_composite: FlyScanXRayCentreComposite,
    fetch_comment: Callable,  # noqa
    params: ThreeDGridScan,
    callbacks: tuple[GridscanNexusFileCallback, GridscanISPyBCallback],
):
    _, ispyb_cb = callbacks
    params.storage_directory = "./tmp"
    params.file_name = str(uuid.uuid1())

    # Currently s03 calls anything with z_steps > 1 invalid
    params.z_steps = 100
    RE(reset_positions(fxc_composite.smargon))

    [RE.subscribe(cb) for cb in callbacks]
    with pytest.raises(WarningException):
        RE(flyscan_xray_centre(fxc_composite, params))

    ids = ispyb_cb.ispyb_ids
    assert ids.data_collection_group_id is not None
    dcid_used = ispyb_cb.ispyb_ids.data_collection_ids[0]

    comment = fetch_comment(dcid_used)

    assert "too long/short/bent" in comment
    zocalo_trigger.run_start.assert_not_called()


@pytest.mark.s03
async def test_complete_xray_centre_plan_with_no_callbacks_falls_back_to_centre(
    RE: RunEngine,
    fxc_composite: FlyScanXRayCentreComposite,
    zocalo_env: None,  # noqa
    params: ThreeDGridScan,
    callbacks,
    done_status,
):
    fxc_composite.zebra_fast_grid_scan.kickoff = MagicMock(return_value=done_status)
    fxc_composite.zebra_fast_grid_scan.complete = MagicMock(return_value=done_status)

    params.storage_directory = "./tmp"
    params.file_name = str(uuid.uuid1())

    # Currently s03 calls anything with z_steps > 1 invalid
    params.z_steps = 1

    RE(reset_positions(fxc_composite.smargon))

    def zocalo_trigger():
        fxc_composite.zocalo._raw_results_received.put({"results": []})
        return done_status

    # [RE.subscribe(cb) for cb in callbacks]
    fxc_composite.zocalo.trigger = MagicMock(side_effect=zocalo_trigger)
    RE(flyscan_xray_centre(fxc_composite, params))

    # The following numbers are derived from the centre returned in fake_zocalo
    assert (
        await fxc_composite.sample_motors.x.user_readback.get_value()
        == pytest.approx(-1)
    )
    assert (
        await fxc_composite.sample_motors.y.user_readback.get_value()
        == pytest.approx(-1)
    )
    assert (
        await fxc_composite.sample_motors.z.user_readback.get_value()
        == pytest.approx(-1)
    )


@pytest.mark.s03
async def test_complete_xray_centre_plan_with_callbacks_moves_to_centre(
    RE: RunEngine,
    fxc_composite: FlyScanXRayCentreComposite,
    zocalo_env: None,  # noqa
    params: ThreeDGridScan,
    callbacks,
    done_status,
):
    fxc_composite.zebra_fast_grid_scan.kickoff = MagicMock(return_value=done_status)
    fxc_composite.zebra_fast_grid_scan.complete = MagicMock(return_value=done_status)

    params.storage_directory = "./tmp"
    params.file_name = str(uuid.uuid1())

    # Currently s03 calls anything with z_steps > 1 invalid
    params.z_steps = 1

    RE(reset_positions(fxc_composite.smargon))

    [RE.subscribe(cb) for cb in callbacks]
    RE(flyscan_xray_centre(fxc_composite, params))

    # The following numbers are derived from the centre returned in fake_zocalo
    assert (
        await fxc_composite.sample_motors.x.user_readback.get_value()
        == pytest.approx(0.05)
    )
    assert (
        await fxc_composite.sample_motors.y.user_readback.get_value()
        == pytest.approx(0.15)
    )
    assert (
        await fxc_composite.sample_motors.z.user_readback.get_value()
        == pytest.approx(0.25)
    )
