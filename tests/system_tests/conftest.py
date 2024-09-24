from unittest.mock import MagicMock, patch

import pytest
from dodal.beamlines import i03
from dodal.devices.oav.oav_parameters import OAVConfigParams
from ophyd_async.core import AsyncStatus, set_mock_value
from requests import Response


@pytest.fixture
def undulator_for_system_test(undulator):
    set_mock_value(undulator.current_gap, 1.11)
    return undulator


@pytest.fixture
def oav_for_system_test(test_config_files):
    parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    oav = i03.oav(fake_with_ophyd_sim=True, params=parameters)
    oav.zoom_controller.zrst.set("1.0x")
    oav.zoom_controller.onst.set("7.5x")
    oav.cam.array_size.array_size_x.sim_put(1024)
    oav.cam.array_size.array_size_y.sim_put(768)

    unpatched_method = oav.parameters.load_microns_per_pixel

    def patch_lmpp(zoom, xsize, ysize):
        unpatched_method(zoom, 1024, 768)

    # Grid snapshots
    oav.grid_snapshot.x_size.sim_put(1024)
    oav.grid_snapshot.y_size.sim_put(768)
    oav.grid_snapshot.top_left_x.set(50)
    oav.grid_snapshot.top_left_y.set(100)
    oav.grid_snapshot.box_width.set(0.1 * 1000 / 1.25)  # size in pixels
    unpatched_snapshot_trigger = oav.grid_snapshot.trigger

    def mock_grid_snapshot_trigger():
        oav.grid_snapshot.last_path_full_overlay.set("test_1_y")
        oav.grid_snapshot.last_path_outer.set("test_2_y")
        oav.grid_snapshot.last_saved_path.set("test_3_y")
        return unpatched_snapshot_trigger()

    # Plain snapshots
    def next_snapshot():
        next_snapshot_idx = 1
        while True:
            yield f"/tmp/snapshot{next_snapshot_idx}.png"
            next_snapshot_idx += 1

    empty_response = MagicMock(spec=Response)
    empty_response.content = b""
    with (
        patch(
            "dodal.devices.areadetector.plugins.MJPG.requests.get",
            return_value=empty_response,
        ),
        patch("dodal.devices.areadetector.plugins.MJPG.Image.open"),
        patch.object(oav.grid_snapshot, "post_processing"),
        patch.object(
            oav.grid_snapshot, "trigger", side_effect=mock_grid_snapshot_trigger
        ),
        patch.object(
            oav.parameters,
            "load_microns_per_pixel",
            new=MagicMock(side_effect=patch_lmpp),
        ),
        patch.object(oav.snapshot.last_saved_path, "get") as mock_last_saved_path,
    ):
        it_next_snapshot = next_snapshot()

        @AsyncStatus.wrap
        async def mock_rotation_snapshot_trigger():
            mock_last_saved_path.side_effect = lambda: next(it_next_snapshot)

        with patch.object(
            oav.snapshot,
            "trigger",
            side_effect=mock_rotation_snapshot_trigger,
        ):
            oav.parameters.load_microns_per_pixel(1.0, 1024, 768)
            yield oav
