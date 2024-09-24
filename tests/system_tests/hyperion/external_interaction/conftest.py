import os
from collections.abc import Callable, Sequence
from functools import partial
from typing import Any
from unittest.mock import patch

import ispyb.sqlalchemy
import numpy
import pytest
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.dcm import DCM
from dodal.devices.detector.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.flux import Flux
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.robot import BartRobot
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron, SynchrotronMode
from dodal.devices.undulator import Undulator
from dodal.devices.xbpm_feedback import XBPMFeedback
from dodal.devices.zebra import Zebra
from dodal.devices.zebra_controlled_shutter import ZebraShutter
from ispyb.sqlalchemy import DataCollection, DataCollectionGroup, GridInfo, Position
from ophyd.sim import NullStatus
from ophyd_async.core import AsyncStatus, set_mock_value
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mx_bluesky.hyperion.experiment_plans.grid_detect_then_xray_centre_plan import (
    GridDetectThenXRayCentreComposite,
)
from mx_bluesky.hyperion.experiment_plans.rotation_scan_plan import (
    RotationScanComposite,
)
from mx_bluesky.hyperion.external_interaction.ispyb.ispyb_store import StoreInIspyb
from mx_bluesky.hyperion.parameters.constants import CONST
from mx_bluesky.hyperion.parameters.gridscan import ThreeDGridScan
from mx_bluesky.hyperion.utils.utils import convert_angstrom_to_eV

from ....conftest import fake_read, pin_tip_edge_data, raw_params_from_file

TEST_RESULT_LARGE = [
    {
        "centre_of_mass": [1, 2, 3],
        "max_voxel": [1, 2, 3],
        "max_count": 105062,
        "n_voxels": 35,
        "total_count": 2387574,
        "bounding_box": [[2, 2, 2], [8, 8, 7]],
    }
]
TEST_RESULT_MEDIUM = [
    {
        "centre_of_mass": [1, 2, 3],
        "max_voxel": [2, 4, 5],
        "max_count": 105062,
        "n_voxels": 35,
        "total_count": 2387574,
        "bounding_box": [[1, 2, 3], [3, 4, 4]],
    }
]
TEST_RESULT_SMALL = [
    {
        "centre_of_mass": [1, 2, 3],
        "max_voxel": [1, 2, 3],
        "max_count": 105062,
        "n_voxels": 35,
        "total_count": 1387574,
        "bounding_box": [[2, 2, 2], [3, 3, 3]],
    }
]


def get_current_datacollection_comment(Session: Callable, dcid: int) -> str:
    """Read the 'comments' field from the given datacollection id's ISPyB entry.
    Returns an empty string if the comment is not yet initialised.
    """
    try:
        with Session() as session:
            query = session.query(DataCollection).filter(
                DataCollection.dataCollectionId == dcid
            )
            current_comment: str = query.first().comments
    except Exception:
        current_comment = ""
    return current_comment


def get_datacollections(Session: Callable, dcg_id: int) -> Sequence[int]:
    with Session.begin() as session:
        query = session.query(DataCollection.dataCollectionId).filter(
            DataCollection.dataCollectionGroupId == dcg_id
        )
        return [row[0] for row in query.all()]


def get_current_datacollection_attribute(
    Session: Callable, dcid: int, attr: str
) -> str:
    """Read the specified field 'attr' from the given datacollection id's ISPyB entry.
    Returns an empty string if the attribute is not found.
    """
    try:
        with Session() as session:
            query = session.query(DataCollection).filter(
                DataCollection.dataCollectionId == dcid
            )
            first_result = query.first()
            data: str = getattr(first_result, attr)
    except Exception:
        data = ""
    return data


def get_current_datacollection_grid_attribute(
    Session: Callable, grid_id: int, attr: str
) -> Any:
    with Session() as session:
        query = session.query(GridInfo).filter(GridInfo.gridInfoId == grid_id)
        first_result = query.first()
        return getattr(first_result, attr)


def get_current_position_attribute(
    Session: Callable, position_id: int, attr: str
) -> Any:
    with Session() as session:
        query = session.query(Position).filter(Position.positionId == position_id)
        first_result = query.first()
        if first_result is None:
            return None
        return getattr(first_result, attr)


def get_current_datacollectiongroup_attribute(
    Session: Callable, dcg_id: int, attr: str
):
    with Session() as session:
        query = session.query(DataCollectionGroup).filter(
            DataCollectionGroup.dataCollectionGroupId == dcg_id
        )
        first_result = query.first()
        return getattr(first_result, attr)


@pytest.fixture
def sqlalchemy_sessionmaker() -> sessionmaker:
    url = ispyb.sqlalchemy.url(CONST.SIM.DEV_ISPYB_DATABASE_CFG)
    engine = create_engine(url, connect_args={"use_pure": True})
    return sessionmaker(engine)


@pytest.fixture
def fetch_comment(sqlalchemy_sessionmaker) -> Callable:
    return partial(get_current_datacollection_comment, sqlalchemy_sessionmaker)


@pytest.fixture
def fetch_datacollection_ids_for_group_id(
    sqlalchemy_sessionmaker,
) -> Callable[[int], Sequence]:
    return partial(get_datacollections, sqlalchemy_sessionmaker)


@pytest.fixture
def fetch_datacollection_attribute(sqlalchemy_sessionmaker) -> Callable:
    return partial(get_current_datacollection_attribute, sqlalchemy_sessionmaker)


@pytest.fixture
def fetch_datacollection_grid_attribute(sqlalchemy_sessionmaker) -> Callable:
    return partial(get_current_datacollection_grid_attribute, sqlalchemy_sessionmaker)


@pytest.fixture
def fetch_datacollection_position_attribute(sqlalchemy_sessionmaker) -> Callable:
    return partial(get_current_position_attribute, sqlalchemy_sessionmaker)


@pytest.fixture
def fetch_datacollectiongroup_attribute(sqlalchemy_sessionmaker) -> Callable:
    return partial(get_current_datacollectiongroup_attribute, sqlalchemy_sessionmaker)


@pytest.fixture
def dummy_params():
    dummy_params = ThreeDGridScan(
        **raw_params_from_file(
            "tests/test_data/parameter_json_files/test_gridscan_param_defaults.json"
        )
    )
    dummy_params.visit = "cm31105-5"
    return dummy_params


@pytest.fixture
def dummy_ispyb(dummy_params) -> StoreInIspyb:
    return StoreInIspyb(CONST.SIM.DEV_ISPYB_DATABASE_CFG)


@pytest.fixture
def dummy_ispyb_3d(dummy_params) -> StoreInIspyb:
    return StoreInIspyb(CONST.SIM.DEV_ISPYB_DATABASE_CFG)


@pytest.fixture
def zocalo_env():
    os.environ["ZOCALO_CONFIG"] = "/dls_sw/apps/zocalo/live/configuration.yaml"


# noinspection PyUnreachableCode
@pytest.fixture
def grid_detect_then_xray_centre_composite(
    fast_grid_scan,
    backlight,
    smargon,
    undulator_for_system_test,
    synchrotron,
    s4_slit_gaps,
    attenuator,
    xbpm_feedback,
    detector_motion,
    zocalo,
    aperture_scatterguard,
    zebra,
    eiger,
    robot,
    oav_for_system_test,
    dcm,
    flux,
    ophyd_pin_tip_detection,
    sample_shutter,
):
    composite = GridDetectThenXRayCentreComposite(
        zebra_fast_grid_scan=fast_grid_scan,
        pin_tip_detection=ophyd_pin_tip_detection,
        backlight=backlight,
        panda_fast_grid_scan=None,  # type: ignore
        smargon=smargon,
        undulator=undulator_for_system_test,
        synchrotron=synchrotron,
        s4_slit_gaps=s4_slit_gaps,
        attenuator=attenuator,
        xbpm_feedback=xbpm_feedback,
        detector_motion=detector_motion,
        zocalo=zocalo,
        aperture_scatterguard=aperture_scatterguard,
        zebra=zebra,
        eiger=eiger,
        panda=None,  # type: ignore
        robot=robot,
        oav=oav_for_system_test,
        dcm=dcm,
        flux=flux,
        sample_shutter=sample_shutter,
    )

    @AsyncStatus.wrap
    async def mock_pin_tip_detect():
        tip_x_px, tip_y_px, top_edge_array, bottom_edge_array = pin_tip_edge_data()
        set_mock_value(
            ophyd_pin_tip_detection.triggered_top_edge,
            top_edge_array,
        )

        set_mock_value(
            ophyd_pin_tip_detection.triggered_bottom_edge,
            bottom_edge_array,
        )
        set_mock_value(
            zocalo.bbox_sizes, numpy.array([[10, 10, 10]], dtype=numpy.uint64)
        )
        set_mock_value(ophyd_pin_tip_detection.triggered_tip, (tip_x_px, tip_y_px))

    @AsyncStatus.wrap
    async def mock_complete_status():
        pass

    @AsyncStatus.wrap
    async def mock_zocalo_complete():
        await zocalo._put_results(TEST_RESULT_MEDIUM, {"dcid": 0, "dcgid": 0})

    with (
        patch.object(eiger, "wait_on_arming_if_started"),
        # xsize, ysize will always be wrong since computed as 0 before we get here
        # patch up load_microns_per_pixel connect to receive non-zero values
        patch.object(
            ophyd_pin_tip_detection, "trigger", side_effect=mock_pin_tip_detect
        ),
        patch.object(fast_grid_scan, "kickoff", return_value=NullStatus()),
        patch.object(fast_grid_scan, "complete", return_value=NullStatus()),
        patch.object(zocalo, "trigger", side_effect=mock_zocalo_complete),
    ):
        yield composite


@pytest.fixture
def composite_for_rotation_scan(
    eiger: EigerDetector,
    smargon: Smargon,
    zebra: Zebra,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    attenuator: Attenuator,
    flux: Flux,
    undulator_for_system_test: Undulator,
    aperture_scatterguard: ApertureScatterguard,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    dcm: DCM,
    robot: BartRobot,
    oav_for_system_test: OAV,
    sample_shutter: ZebraShutter,
    xbpm_feedback: XBPMFeedback,
):
    set_mock_value(smargon.omega.max_velocity, 131)
    oav_for_system_test.zoom_controller.zrst.sim_put("1.0x")  # type: ignore
    oav_for_system_test.zoom_controller.fvst.sim_put("5.0x")  # type: ignore

    fake_create_rotation_devices = RotationScanComposite(
        attenuator=attenuator,
        backlight=backlight,
        dcm=dcm,
        detector_motion=detector_motion,
        eiger=eiger,
        flux=flux,
        smargon=smargon,
        undulator=undulator_for_system_test,
        aperture_scatterguard=aperture_scatterguard,
        synchrotron=synchrotron,
        s4_slit_gaps=s4_slit_gaps,
        zebra=zebra,
        robot=robot,
        oav=oav_for_system_test,
        sample_shutter=sample_shutter,
        xbpm_feedback=xbpm_feedback,
    )

    energy_ev = convert_angstrom_to_eV(0.71)
    set_mock_value(
        fake_create_rotation_devices.dcm.energy_in_kev.user_readback,
        energy_ev / 1000,  # pyright: ignore
    )
    set_mock_value(
        fake_create_rotation_devices.synchrotron.synchrotron_mode,
        SynchrotronMode.USER,
    )
    set_mock_value(
        fake_create_rotation_devices.synchrotron.top_up_start_countdown,  # pyright: ignore
        -1,
    )
    fake_create_rotation_devices.s4_slit_gaps.xgap.user_readback.sim_put(  # pyright: ignore
        0.123
    )
    fake_create_rotation_devices.s4_slit_gaps.ygap.user_readback.sim_put(  # pyright: ignore
        0.234
    )

    with (
        patch("bluesky.preprocessors.__read_and_stash_a_motor", fake_read),
        patch("bluesky.plan_stubs.wait"),
    ):
        yield fake_create_rotation_devices
