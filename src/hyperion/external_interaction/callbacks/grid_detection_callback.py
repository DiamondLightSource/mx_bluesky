from typing import TypedDict

import numpy as np
from bluesky.callbacks import CallbackBase
from dodal.devices.oav.oav_detector import OAVConfigParams
from event_model.documents import Event

from hyperion.device_setup_plans.setup_oav import calculate_x_y_z_of_pixel
from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST


class GridParamUpdate(TypedDict):
    transmission_frac: float
    exposure_time_s: float
    x_start_um: float
    y_start_um: float
    y2_start_um: float
    z_start_um: float
    z2_start_um: float
    x_steps: int
    y_steps: int
    z_steps: int
    x_step_size_um: float
    y_step_size_um: float
    z_step_size_um: float
    set_stub_offsets: bool


class GridDetectionCallback(CallbackBase):
    def __init__(
        self,
        oav_params: OAVConfigParams,
        exposure_time: float,
        set_stub_offsets: bool,
        run_up_distance_mm: float = CONST.HARDWARE.PANDA_FGS_RUN_UP_DEFAULT,
        *args,
    ) -> None:
        super().__init__(*args)
        self.exposure_time = exposure_time
        self.set_stub_offsets = set_stub_offsets
        self.oav_params = oav_params
        self.run_up_distance_mm: float = run_up_distance_mm
        self.start_positions: list = []
        self.box_numbers: list = []

    def event(self, doc: Event):
        data = doc.get("data")
        top_left_x_px = data["oav_grid_snapshot_top_left_x"]
        box_width_px = data["oav_grid_snapshot_box_width"]
        x_of_centre_of_first_box_px = top_left_x_px + box_width_px / 2

        top_left_y_px = data["oav_grid_snapshot_top_left_y"]
        y_of_centre_of_first_box_px = top_left_y_px + box_width_px / 2

        smargon_omega = data["smargon_omega"]
        current_xyz = np.array(
            [data["smargon_x"], data["smargon_y"], data["smargon_z"]]
        )

        centre_of_first_box = (
            x_of_centre_of_first_box_px,
            y_of_centre_of_first_box_px,
        )

        position_grid_start = calculate_x_y_z_of_pixel(
            current_xyz, smargon_omega, centre_of_first_box, self.oav_params
        )

        LOGGER.info(f"Calculated start position {position_grid_start}")

        self.start_positions.append(position_grid_start)
        self.box_numbers.append(
            (
                data["oav_grid_snapshot_num_boxes_x"],
                data["oav_grid_snapshot_num_boxes_y"],
            )
        )

        self.x_step_size_mm = box_width_px * self.oav_params.micronsPerXPixel / 1000
        self.y_step_size_mm = box_width_px * self.oav_params.micronsPerYPixel / 1000
        self.z_step_size_mm = box_width_px * self.oav_params.micronsPerYPixel / 1000
        return doc

    def get_grid_parameters(self) -> GridParamUpdate:
        return {
            "transmission_frac": 1.0,
            "exposure_time_s": self.exposure_time,
            "x_start_um": self.start_positions[0][0],
            "y_start_um": self.start_positions[0][1],
            "y2_start_um": self.start_positions[0][1],
            "z_start_um": self.start_positions[1][2],
            "z2_start_um": self.start_positions[1][2],
            "x_steps": self.box_numbers[0][0],
            "y_steps": self.box_numbers[0][1],
            "z_steps": self.box_numbers[1][1],
            "x_step_size_um": self.x_step_size_mm,
            "y_step_size_um": self.y_step_size_mm,
            "z_step_size_um": self.z_step_size_mm,
            "set_stub_offsets": self.set_stub_offsets,
        }
