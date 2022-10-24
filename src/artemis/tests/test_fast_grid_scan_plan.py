import types
from unittest.mock import MagicMock, call, patch

import pytest
from bluesky.run_engine import RunEngine
from ophyd.sim import make_fake_device

from artemis.devices.det_dim_constants import (
    EIGER2_X_4M_DIMENSION,
    EIGER_TYPE_EIGER2_X_4M,
    EIGER_TYPE_EIGER2_X_16M,
)
from artemis.devices.eiger import EigerDetector
from artemis.devices.fast_grid_scan_composite import FGSComposite
from artemis.devices.slit_gaps import SlitGaps
from artemis.devices.synchrotron import Synchrotron
from artemis.devices.undulator import Undulator
from artemis.fast_grid_scan_plan import read_hardware_for_ispyb, run_gridscan
from artemis.parameters import FullParameters

DUMMY_TIME_STRING = "1970-01-01 00:00:00"
GOOD_ISPYB_RUN_STATUS = "DataCollection Successful"
BAD_ISPYB_RUN_STATUS = "DataCollection Unsuccessful"


def test_given_full_parameters_dict_when_detector_name_used_and_converted_then_detector_constants_correct():
    params = FullParameters().to_dict()
    assert (
        params["detector_params"]["detector_size_constants"] == EIGER_TYPE_EIGER2_X_16M
    )
    params["detector_params"]["detector_size_constants"] = EIGER_TYPE_EIGER2_X_4M
    params: FullParameters = FullParameters.from_dict(params)
    det_dimension = params.detector_params.detector_size_constants.det_dimension
    assert det_dimension == EIGER2_X_4M_DIMENSION


def test_when_run_gridscan_called_then_generator_returned():
    plan = run_gridscan(MagicMock(), MagicMock())
    assert isinstance(plan, types.GeneratorType)


def test_ispyb_params_update_from_ophyd_devices_correctly():
    RE = RunEngine({})
    params = FullParameters()

    undulator_test_value = 1.234
    FakeUndulator = make_fake_device(Undulator)
    undulator: Undulator = FakeUndulator(name="undulator")
    undulator.gap.user_readback.sim_put(undulator_test_value)

    synchrotron_test_value = "test"
    FakeSynchrotron = make_fake_device(Synchrotron)
    synchrotron: Synchrotron = FakeSynchrotron(name="synchrotron")
    synchrotron.machine_status.synchrotron_mode.sim_put(synchrotron_test_value)

    xgap_test_value = 0.1234
    ygap_test_value = 0.2345
    FakeSlitGaps = make_fake_device(SlitGaps)
    slit_gaps: SlitGaps = FakeSlitGaps(name="slit_gaps")
    slit_gaps.xgap.sim_put(xgap_test_value)
    slit_gaps.ygap.sim_put(ygap_test_value)

    from bluesky.callbacks import CallbackBase

    class TestCB(CallbackBase):
        params = FullParameters()

        def event(self, doc: dict):
            params.ispyb_params.undulator_gap = doc["data"]["undulator_gap"]
            params.ispyb_params.synchrotron_mode = doc["data"][
                "synchrotron_machine_status_synchrotron_mode"
            ]
            params.ispyb_params.slit_gap_size_x = doc["data"]["slit_gaps_xgap"]
            params.ispyb_params.slit_gap_size_y = doc["data"]["slit_gaps_ygap"]

    testcb = TestCB()
    testcb.params = params
    RE.subscribe(testcb)
    RE(read_hardware_for_ispyb(undulator, synchrotron, slit_gaps))
    params = testcb.params

    assert params.ispyb_params.undulator_gap == undulator_test_value
    assert params.ispyb_params.synchrotron_mode == synchrotron_test_value
    assert params.ispyb_params.slit_gap_size_x == xgap_test_value
    assert params.ispyb_params.slit_gap_size_y == ygap_test_value


@pytest.fixture
def dummy_3d_gridscan_args():
    params = FullParameters()
    params.grid_scan_params.z_steps = 2

    FakeFGSComposite = make_fake_device(FGSComposite)
    fgs_composite: FGSComposite = FakeFGSComposite(name="fgs", insertion_prefix="")

    FakeEiger = make_fake_device(EigerDetector)
    eiger: EigerDetector = FakeEiger(
        detector_params=params.detector_params, name="eiger"
    )

    return fgs_composite, eiger, params


@patch("artemis.fast_grid_scan_plan.run_start")
@patch("artemis.fast_grid_scan_plan.run_end")
@patch("artemis.fast_grid_scan_plan.wait_for_result")
@patch("artemis.fast_grid_scan_plan.StoreInIspyb3D.store_grid_scan")
@patch("artemis.fast_grid_scan_plan.StoreInIspyb3D.get_current_time_string")
@patch(
    "artemis.fast_grid_scan_plan.StoreInIspyb3D.update_grid_scan_with_end_time_and_status"
)
def test_run_gridscan_zocalo_calls(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    wait_for_result,
    run_end,
    run_start,
    dummy_3d_gridscan_args,
):
    dc_ids = [1, 2]
    dcg_id = 4

    mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
    mock_ispyb_get_time.return_value = DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    print(run_start)

    with patch("artemis.fgs_communicator.NexusWriter"):
        list(run_gridscan(*dummy_3d_gridscan_args))

    run_start.assert_has_calls(call(x) for x in dc_ids)
    assert run_start.call_count == len(dc_ids)

    run_end.assert_has_calls(call(x) for x in dc_ids)
    assert run_end.call_count == len(dc_ids)

    wait_for_result.assert_called_once_with(dcg_id)


# @patch("artemis.fast_grid_scan_plan.run_start")
# @patch("artemis.fast_grid_scan_plan.run_end")
# @patch("artemis.fast_grid_scan_plan.wait_for_result")
# @patch("artemis.fast_grid_scan_plan.StoreInIspyb3D.store_grid_scan")
# @patch("artemis.fast_grid_scan_plan.StoreInIspyb3D.get_current_time_string")
# @patch(
#     "artemis.fast_grid_scan_plan.StoreInIspyb3D.update_grid_scan_with_end_time_and_status"
# )
# def test_fgs_raising_exception_results_in_bad_run_status_in_ispyb(
#     mock_ispyb_update_time_and_status: MagicMock,
#     mock_ispyb_get_time: MagicMock,
#     mock_ispyb_store_grid_scan: MagicMock,
#     wait_for_result: MagicMock,
#     run_end: MagicMock,
#     run_start: MagicMock,
#     dummy_3d_gridscan_args,
# ):
#     dc_ids = [1, 2]
#     dcg_id = 4
#
#     mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
#     mock_ispyb_get_time.return_value = DUMMY_TIME_STRING
#     mock_ispyb_update_time_and_status.return_value = None
#
#     with pytest.raises(Exception) as excinfo:
#         with patch(
#             "artemis.fgs_communicator.NexusWriter",
#             side_effect=Exception("mocked error"),
#         ):
#             list(run_gridscan(*dummy_3d_gridscan_args))
#
#     expected_error_message = "mocked error"
#     assert str(excinfo.value) == expected_error_message
#
#     mock_ispyb_update_time_and_status.assert_has_calls(
#         [call(DUMMY_TIME_STRING, BAD_ISPYB_RUN_STATUS, id, dcg_id) for id in dc_ids]
#     )
#     assert mock_ispyb_update_time_and_status.call_count == len(dc_ids)


@patch("artemis.fgs_communicator.run_start")
@patch("artemis.fgs_communicator.run_end")
@patch("artemis.fast_grid_scan_plan.wait_for_result")
@patch("artemis.fast_grid_scan_plan.StoreInIspyb3D.store_grid_scan")
@patch("artemis.fast_grid_scan_plan.StoreInIspyb3D.get_current_time_string")
@patch(
    "artemis.fast_grid_scan_plan.StoreInIspyb3D.update_grid_scan_with_end_time_and_status"
)
def test_fgs_raising_no_exception_results_in_good_run_status_in_ispyb(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    wait_for_result: MagicMock,
    run_end: MagicMock,
    run_start: MagicMock,
    dummy_3d_gridscan_args,
):
    dc_ids = [1, 2]
    dcg_id = 4

    mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
    mock_ispyb_get_time.return_value = DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    with patch("artemis.fgs_communicator.NexusWriter"):
        list(run_gridscan(*dummy_3d_gridscan_args))

    mock_ispyb_update_time_and_status.assert_has_calls(
        [call(DUMMY_TIME_STRING, GOOD_ISPYB_RUN_STATUS, id, dcg_id) for id in dc_ids]
    )
    assert mock_ispyb_update_time_and_status.call_count == len(dc_ids)
