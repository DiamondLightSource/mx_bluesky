from __future__ import annotations

import numpy as np
from dodal.devices.detector import DetectorParams
from dodal.devices.detector.det_dist_to_beam_converter import (
    DetectorDistanceToBeamXYConverter,
)
from dodal.devices.zebra import (
    RotationDirection,
)
from pydantic import Field
from scanspec.core import AxesPoints
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from hyperion.external_interaction.ispyb.ispyb_dataclass import RotationIspybParams
from hyperion.parameters.components import (
    DiffractionExperiment,
    OptionalGonioAngleStarts,
    OptionalXyzStarts,
    RotationAxis,
    TemporaryIspybExtras,
    WithSample,
    WithScan,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationHyperionParameters,
    RotationInternalParameters,
    RotationScanParams,
)


class RotationScan(
    DiffractionExperiment,
    WithScan,
    OptionalGonioAngleStarts,
    OptionalXyzStarts,
    WithSample,
):
    omega_start_deg: float = 0  # type: ignore
    rotation_axis: RotationAxis = RotationAxis.OMEGA
    rotation_angle_deg: float
    rotation_increment_deg: float
    rotation_direction: RotationDirection
    shutter_opening_time_s: float = Field(default=CONST.I03.SHUTTER_TIME_S)
    transmission_frac: float
    ispyb_extras: TemporaryIspybExtras

    @property
    def detector_params(self):
        self.det_dist_to_beam_converter_path = (
            self.det_dist_to_beam_converter_path
            or CONST.PARAM.DETECTOR.BEAM_XY_LUT_PATH
        )
        optional_args = {}
        if self.run_number:
            optional_args["run_number"] = self.run_number
        assert self.detector_distance_mm is not None
        return DetectorParams(
            expected_energy_ev=self.demand_energy_ev,
            exposure_time=self.exposure_time_s,
            directory=str(self.visit_directory / "auto" / str(self.sample_id)),
            prefix=self.file_name,
            detector_distance=self.detector_distance_mm,
            omega_start=self.omega_start_deg,
            omega_increment=self.rotation_increment_deg,
            num_images_per_trigger=self.num_images,
            num_triggers=1,
            use_roi_mode=False,
            det_dist_to_beam_converter_path=self.det_dist_to_beam_converter_path,
            beam_xy_converter=DetectorDistanceToBeamXYConverter(
                self.det_dist_to_beam_converter_path
            ),
            **optional_args,
        )

    @property
    def ispyb_params(self):  # pyright: ignore
        return RotationIspybParams(
            visit_path=str(self.visit_directory),
            microns_per_pixel_x=self.ispyb_extras.microns_per_pixel_x,
            microns_per_pixel_y=self.ispyb_extras.microns_per_pixel_y,
            position=np.array(self.ispyb_extras.position),
            transmission_fraction=self.transmission_frac,
            current_energy_ev=self.demand_energy_ev,
            beam_size_x=self.ispyb_extras.beam_size_x,
            beam_size_y=self.ispyb_extras.beam_size_y,
            focal_spot_size_x=self.ispyb_extras.focal_spot_size_x,
            focal_spot_size_y=self.ispyb_extras.focal_spot_size_y,
            comment=self.comment,
            resolution=self.ispyb_extras.resolution,
            sample_id=str(self.sample_id),
            sample_barcode=self.ispyb_extras.sample_barcode,
            undulator_gap=self.ispyb_extras.undulator_gap,
            synchrotron_mode=self.ispyb_extras.synchrotron_mode,
            slit_gap_size_x=self.ispyb_extras.slit_gap_size_x,
            slit_gap_size_y=self.ispyb_extras.slit_gap_size_y,
            xtal_snapshots_omega_start=self.ispyb_extras.xtal_snapshots_omega_start,
            xtal_snapshots_omega_end=self.ispyb_extras.xtal_snapshots_omega_end,
            ispyb_experiment_type="SAD",
        )

    @property
    def scan_points(self) -> AxesPoints:
        scan_spec = Line(
            axis="omega",
            start=self.omega_start_deg,
            stop=(self.rotation_angle_deg + self.omega_start_deg),
            num=self.num_images,
        )
        scan_path = ScanPath(scan_spec.calculate())
        return scan_path.consume().midpoints

    @property
    def num_images(self) -> int:
        return int(self.rotation_angle_deg / self.rotation_increment_deg)

    def old_parameters(self) -> RotationInternalParameters:
        return RotationInternalParameters(
            params_version=str(self.parameter_model_version),  # type: ignore
            experiment_params=RotationScanParams(
                rotation_axis=self.rotation_axis,
                rotation_angle=self.rotation_angle_deg,
                image_width=self.rotation_increment_deg,
                omega_start=self.omega_start_deg,
                phi_start=self.phi_start_deg,
                chi_start=self.chi_start_deg,
                kappa_start=self.kappa_start_deg,
                x=self.x_start_um,
                y=self.y_start_um,
                z=self.z_start_um,
                rotation_direction=self.rotation_direction,
                shutter_opening_time_s=self.shutter_opening_time_s,
            ),
            hyperion_params=RotationHyperionParameters(
                zocalo_environment=self.zocalo_environment,
                beamline=self.beamline,
                insertion_prefix=self.insertion_prefix,
                experiment_type="rotation_scan",
                detector_params=self.detector_params,
                ispyb_params=self.ispyb_params,
            ),
        )
