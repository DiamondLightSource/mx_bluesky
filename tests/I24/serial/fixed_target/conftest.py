import pytest

from mx_bluesky.I24.serial.parameters import FixedTargetParameters


@pytest.fixture
def dummy_params_without_pp():
    params = {
        "visit": "foo",
        "directory": "bar",
        "filename": "chip",
        "exposure_time_s": 0.01,
        "detector_distance_mm": 100,
        "detector_name": "eiger",
        "num_exposures": 1,
        "chip_type": 0,
        "map_type": 1,
        "pump_repeat": 0,
        "checker_pattern": False,
    }
    return FixedTargetParameters(**params)
