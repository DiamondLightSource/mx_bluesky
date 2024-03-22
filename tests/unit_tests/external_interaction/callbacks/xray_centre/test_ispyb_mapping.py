from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from hyperion.external_interaction.callbacks.common.ispyb_mapping import GridScanInfo
from hyperion.external_interaction.callbacks.xray_centre.ispyb_mapping import (
    construct_comment_for_gridscan,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

from ...conftest import (
    TEST_SAMPLE_ID,
    default_raw_params,
)


@pytest.fixture
def dummy_params():
    dummy_params = GridscanInternalParameters(**default_raw_params())
    dummy_params.hyperion_params.ispyb_params.sample_id = TEST_SAMPLE_ID
    dummy_params.hyperion_params.ispyb_params.upper_left = np.array([100, 100, 50])
    dummy_params.hyperion_params.ispyb_params.microns_per_pixel_x = 1.25
    dummy_params.hyperion_params.ispyb_params.microns_per_pixel_y = 1.25
    dummy_params.hyperion_params.detector_params.run_number = 0
    return dummy_params


@patch("ispyb.open", autospec=True)
def test_ispyb_deposition_rounds_position_to_int(
    mock_ispyb_conn: MagicMock,
    dummy_params,
):
    dummy_params.hyperion_params.ispyb_params.upper_left = np.array([0.01, 100, 50])

    assert construct_comment_for_gridscan(
        dummy_params.hyperion_params.ispyb_params,
        GridScanInfo(
            dummy_params.hyperion_params.ispyb_params.upper_left, 40, 20, 0.1, 0.1
        ),
    ) == (
        "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images "
        "in 100.0 um by 100.0 um steps. Top left (px): [0,100], bottom right (px): [3200,1700]."
    )


@pytest.mark.parametrize(
    ["raw", "rounded"],
    [
        (0.0012345, "1.2"),
        (0.020000000, "20.0"),
        (0.01999999, "20.0"),
        (0.015257, "15.3"),
        (0.0001234, "0.1"),
        (0.0017345, "1.7"),
        (0.0019945, "2.0"),
    ],
)
@patch(
    "hyperion.external_interaction.callbacks.xray_centre.ispyb_mapping.oav_utils.bottom_right_from_top_left",
    autospec=True,
)
def test_ispyb_deposition_rounds_box_size_int(
    bottom_right_from_top_left: MagicMock,
    dummy_params: GridscanInternalParameters,
    raw,
    rounded,
):
    grid_scan_info = GridScanInfo(
        [
            0,
            0,
            0,
        ],
        0,
        0,
        raw,
        raw,
    )
    bottom_right_from_top_left.return_value = grid_scan_info.upper_left_px

    assert construct_comment_for_gridscan(MagicMock(), grid_scan_info) == (
        "Hyperion: Xray centring - Diffraction grid scan of 0 by 0 images in "
        f"{rounded} um by {rounded} um steps. Top left (px): [0,0], bottom right (px): [0,0]."
    )
