import pytest

from mx_bluesky.i24.jungfrau_commissioning.utils.params import RotationScan


def test_params_load_from_file():
    minimal_params = RotationScan.from_file(
        "tests/i24/jungfrau_commissioning/test_data/example_params.json"
    )
    assert minimal_params.x_start_um is None
    assert minimal_params.y_start_um is None
    assert minimal_params.z_start_um is None

    complete_params = RotationScan.from_file(
        "tests/i24/jungfrau_commissioning/test_data/complete_example_params.json"
    )
    assert complete_params.x_start_um is not None
    assert complete_params.y_start_um is not None
    assert complete_params.z_start_um is not None

    assert complete_params.num_images == 3600


def test_params_validation():
    with pytest.raises(ValueError) as exc:
        params = RotationScan.from_file(  # noqa
            "tests/i24/jungfrau_commissioning/test_data/bad_params_acq_time_too_short.json"
        )
    assert (
        exc.value.errors()[0]["msg"]
        == "Acquisition time must not be shorter than exposure time!"
    )
