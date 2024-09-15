from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining
from bluesky.utils import Msg
from ophyd.sim import NullStatus
from ophyd_async.core import set_mock_value

from mx_bluesky.hyperion.experiment_plans.robot_load_then_centre_plan import (
    RobotLoadThenCentreComposite,
    robot_load_then_centre,
)
from mx_bluesky.hyperion.parameters.gridscan import (
    PinTipCentreThenXrayCentre,
    RobotLoadThenCentre,
)

from ....conftest import raw_params_from_file


@pytest.fixture
def robot_load_composite(
    smargon, dcm, robot, aperture_scatterguard, oav, webcam, thawer, lower_gonio, eiger
) -> RobotLoadThenCentreComposite:
    composite: RobotLoadThenCentreComposite = MagicMock()
    composite.smargon = smargon
    composite.dcm = dcm
    set_mock_value(composite.dcm.energy_in_kev.user_readback, 11.105)
    composite.robot = robot
    composite.aperture_scatterguard = aperture_scatterguard
    composite.smargon.stub_offsets.set = MagicMock(return_value=NullStatus())
    composite.aperture_scatterguard.set = MagicMock(return_value=NullStatus())
    composite.oav = oav
    composite.webcam = webcam
    composite.lower_gonio = lower_gonio
    composite.thawer = thawer
    composite.eiger = eiger
    return composite


@pytest.fixture
def robot_load_then_centre_params():
    params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_robot_load_and_centre_params.json"
    )
    return RobotLoadThenCentre(**params)


@pytest.fixture
def robot_load_then_centre_params_no_energy(robot_load_then_centre_params):
    robot_load_then_centre_params.demand_energy_ev = None
    return robot_load_then_centre_params


@patch(
    "mx_bluesky.hyperion.experiment_plans.robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.robot_load_then_centre_plan.full_robot_load_plan",
    MagicMock(return_value=iter([])),
)
def test_when_plan_run_then_centring_plan_run_with_expected_parameters(
    mock_centring_plan: MagicMock,
    robot_load_composite: RobotLoadThenCentreComposite,
    robot_load_then_centre_params: RobotLoadThenCentre,
):
    RE = RunEngine()

    RE(robot_load_then_centre(robot_load_composite, robot_load_then_centre_params))
    composite_passed = mock_centring_plan.call_args[0][0]
    params_passed: PinTipCentreThenXrayCentre = mock_centring_plan.call_args[0][1]

    for name, value in vars(composite_passed).items():
        assert value == getattr(robot_load_composite, name)

    assert isinstance(params_passed, PinTipCentreThenXrayCentre)
    assert params_passed.detector_params.expected_energy_ev == 11100


@patch(
    "mx_bluesky.hyperion.experiment_plans.robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.robot_load_then_centre_plan.full_robot_load_plan",
    MagicMock(return_value=iter([])),
)
def test_when_plan_run_with_requested_energy_specified_energy_set_on_eiger(
    mock_centring_plan: MagicMock,
    robot_load_composite: RobotLoadThenCentreComposite,
    robot_load_then_centre_params: RobotLoadThenCentre,
    sim_run_engine: RunEngineSimulator,
):
    robot_load_composite.eiger.set_detector_parameters = MagicMock()
    sim_run_engine.simulate_plan(
        robot_load_then_centre(robot_load_composite, robot_load_then_centre_params)
    )
    det_params = robot_load_composite.eiger.set_detector_parameters.call_args[0][0]
    assert det_params.expected_energy_ev == 11100
    params_passed: PinTipCentreThenXrayCentre = mock_centring_plan.call_args[0][1]
    assert params_passed.detector_params.expected_energy_ev == 11100


@patch(
    "mx_bluesky.hyperion.experiment_plans.robot_load_then_centre_plan.pin_centre_then_xray_centre_plan",
    MagicMock(),
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.robot_load_then_centre_plan.full_robot_load_plan",
    MagicMock(return_value=iter([])),
)
def test_given_no_energy_supplied_when_robot_load_then_centre_current_energy_set_on_eiger(
    robot_load_composite: RobotLoadThenCentreComposite,
    robot_load_then_centre_params_no_energy: RobotLoadThenCentre,
    sim_run_engine: RunEngineSimulator,
):
    robot_load_composite.eiger.set_detector_parameters = MagicMock()
    sim_run_engine.add_handler(
        "locate",
        lambda msg: {"readback": 11.105},
        "dcm-energy_in_kev",
    )
    sim_run_engine.simulate_plan(
        robot_load_then_centre(
            robot_load_composite,
            robot_load_then_centre_params_no_energy,
        )
    )
    det_params = robot_load_composite.eiger.set_detector_parameters.call_args[0][0]
    assert det_params.expected_energy_ev == 11105


def run_simulating_smargon_wait(
    robot_load_then_centre_params,
    robot_load_composite,
    total_disabled_reads,
    sim_run_engine: RunEngineSimulator,
):
    num_of_reads = 0

    def return_not_disabled_after_reads(_):
        nonlocal num_of_reads
        num_of_reads += 1
        return {"values": {"value": int(num_of_reads < total_disabled_reads)}}

    sim_run_engine.add_handler(
        "locate",
        lambda msg: {"readback": 11.105},
        "dcm-energy_in_kev",
    )
    sim_run_engine.add_handler(
        "read", return_not_disabled_after_reads, "smargon-disabled"
    )

    return sim_run_engine.simulate_plan(
        robot_load_then_centre(robot_load_composite, robot_load_then_centre_params)
    )


def dummy_robot_load_plan(*args, **kwargs):
    return (yield Msg("robot_load"))


@patch(
    "mx_bluesky.hyperion.experiment_plans.robot_load_then_centre_plan.pin_centre_then_xray_centre_plan",
    MagicMock(return_value=iter([])),
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.robot_load_then_centre_plan.full_robot_load_plan",
    MagicMock(side_effect=dummy_robot_load_plan),
)
def test_when_plan_run_then_detector_arm_started_before_wait_on_robot_load(
    robot_load_composite: RobotLoadThenCentreComposite,
    robot_load_then_centre_params: RobotLoadThenCentre,
    sim_run_engine,
):
    messages = sim_run_engine.simulate_plan(
        robot_load_then_centre(robot_load_composite, robot_load_then_centre_params)
    )
    messages = assert_message_and_return_remaining(
        messages, lambda msg: msg.command == "set" and msg.obj.name == "eiger_do_arm"
    )

    assert_message_and_return_remaining(
        messages,
        lambda msg: msg.command == "robot_load",
    )
