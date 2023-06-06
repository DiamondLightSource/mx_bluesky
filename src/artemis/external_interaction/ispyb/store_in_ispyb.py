from __future__ import annotations

import datetime
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import dodal.devices.oav.utils as oav_utils
import ispyb
import ispyb.sqlalchemy
from dodal.devices.detector import DetectorParams
from ispyb.sp.core import Core
from ispyb.sp.mxacquisition import MXAcquisition
from sqlalchemy.connectors import Connector

from artemis.external_interaction.ispyb.ispyb_dataclass import (
    GridscanIspybParams,
    IspybParams,
    Orientation,
    RotationIspybParams,
)
from artemis.log import LOGGER
from artemis.tracing import TRACER

if TYPE_CHECKING:
    from artemis.parameters.plan_specific.fgs_internal_params import (
        FGSInternalParameters,
    )
    from artemis.parameters.plan_specific.rotation_scan_internal_params import (
        RotationInternalParameters,
    )

I03_EIGER_DETECTOR = 78
EIGER_FILE_SUFFIX = "h5"


class StoreInIspyb(ABC):
    ispyb_params: IspybParams | None = None
    detector_params: DetectorParams | None = None
    run_number: int | None = None
    omega_start: int | None = None
    experiment_type: str | None = None
    xtal_snapshots: list[str] | None = None
    conn: Connector = None
    mx_acquisition: MXAcquisition | None = None
    core: Core | None = None
    datacollection_ids: tuple[int, ...] | None = None
    datacollection_group_id: int | None = None

    def __init__(self, ispyb_config, parameters=None) -> None:
        self.ISPYB_CONFIG_PATH: str = ispyb_config

    @abstractmethod
    def _store_scan_data(self):
        pass

    @abstractmethod
    def _construct_comment(self) -> str:
        pass

    @abstractmethod
    def _mutate_datacollection_params_for_experiment(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def begin_deposition(self, success: str, reason: str):
        pass

    @abstractmethod
    def end_deposition(self, success: str, reason: str):
        pass

    def append_to_comment(
        self, datacollection_id: int, comment: str, delimiter: str = " "
    ) -> None:
        with ispyb.open(self.ISPYB_CONFIG_PATH) as self.conn:
            self.mx_acquisition: MXAcquisition = self.conn.mx_acquisition
            self.mx_acquisition.update_data_collection_append_comments(
                datacollection_id, comment, delimiter
            )

    def get_current_time_string(self):
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")

    def get_visit_string(self):
        visit_path_match = self.get_visit_string_from_path(self.ispyb_params.visit_path)
        if visit_path_match:
            return visit_path_match
        else:
            return self.get_visit_string_from_path(self.detector_params.directory)

    def get_visit_string_from_path(self, path):
        match = re.search(self.VISIT_PATH_REGEX, path) if path else None
        return match.group(1) if match else None

    def _store_data_collection_group_table(self) -> int:
        assert self.core is not None
        assert self.ispyb_params is not None
        assert self.mx_acquisition is not None
        try:
            session_id = self.core.retrieve_visit_id(self.get_visit_string())
        except ispyb.NoResult:
            raise Exception(
                f"Not found - session ID for visit {self.get_visit_string()} where self.ispyb_params.visit_path is {self.ispyb_params.visit_path}"
            )

        params = self.mx_acquisition.get_data_collection_group_params()
        params["parentid"] = session_id
        params["experimenttype"] = self.experiment_type
        params["sampleid"] = self.ispyb_params.sample_id
        params["sample_barcode"] = self.ispyb_params.sample_barcode

        return self.mx_acquisition.upsert_data_collection_group(list(params.values()))

    @TRACER.start_as_current_span("store_ispyb_datacollection_table")
    def _store_data_collection_table(self, data_collection_group_id: int) -> int:
        assert self.ispyb_params is not None
        assert self.detector_params is not None
        assert self.core is not None
        assert self.xtal_snapshots is not None
        assert self.mx_acquisition is not None
        try:
            session_id = self.core.retrieve_visit_id(self.get_visit_string())
        except ispyb.NoResult:
            raise Exception(
                f"Not found - session ID for visit {self.get_visit_string()}"
            )

        params = self.mx_acquisition.get_data_collection_params()

        params = self._mutate_datacollection_params_for_experiment(params)

        params["visitid"] = session_id
        params["parentid"] = data_collection_group_id
        params["sampleid"] = self.ispyb_params.sample_id
        params["detectorid"] = I03_EIGER_DETECTOR
        params["axis_start"] = self.omega_start

        params["axis_range"] = 0
        params["focal_spot_size_at_samplex"] = self.ispyb_params.focal_spot_size_x
        params["focal_spot_size_at_sampley"] = self.ispyb_params.focal_spot_size_y
        params["slitgap_vertical"] = self.ispyb_params.slit_gap_size_y
        params["slitgap_horizontal"] = self.ispyb_params.slit_gap_size_x
        params["beamsize_at_samplex"] = self.ispyb_params.beam_size_x
        params["beamsize_at_sampley"] = self.ispyb_params.beam_size_y
        params["transmission"] = self.ispyb_params.transmission
        params["comments"] = self._construct_comment()
        params["datacollection_number"] = self.run_number
        params["detector_distance"] = self.detector_params.detector_distance
        params["exp_time"] = self.detector_params.exposure_time
        params["imgdir"] = self.detector_params.directory
        params["imgprefix"] = self.detector_params.prefix
        params["imgsuffix"] = EIGER_FILE_SUFFIX

        # Both overlap and n_passes included for backwards compatibility,
        # planned to be removed later
        params["n_passes"] = 1
        params["overlap"] = 0

        params["flux"] = self.ispyb_params.flux
        params["omegastart"] = self.omega_start
        params["start_image_number"] = 1
        params["resolution"] = self.ispyb_params.resolution
        params["wavelength"] = self.ispyb_params.wavelength
        beam_position = self.detector_params.get_beam_position_mm(
            self.detector_params.detector_distance
        )
        params["xbeam"], params["ybeam"] = beam_position
        (
            params["xtal_snapshot1"],
            params["xtal_snapshot2"],
            params["xtal_snapshot3"],
        ) = self.xtal_snapshots
        params["synchrotron_mode"] = self.ispyb_params.synchrotron_mode
        params["undulator_gap1"] = self.ispyb_params.undulator_gap
        params["starttime"] = self.get_current_time_string()

        # temporary file template until nxs filewriting is integrated and we can use
        # that file name
        params[
            "file_template"
        ] = f"{self.detector_params.prefix}_{self.run_number}_master.h5"

        return self.mx_acquisition.upsert_data_collection(list(params.values()))


class StoreRotationInIspyb(StoreInIspyb):
    ispyb_params: RotationIspybParams | None = None

    def __init__(self, ispyb_config, parameters=None) -> None:
        self.full_params: RotationInternalParameters | None = parameters
        self.experiment_type = "SAD"
        super().__init__(ispyb_config, parameters)

    def _mutate_datacollection_params_for_experiment(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        assert self.full_params is not None
        params["axis_end"] = (
            self.omega_start + self.full_params.experiment_params.rotation_angle
        )
        params["n_images"] = self.full_params.experiment_params.get_num_images()
        return params

    def store_rotation_scan(self):
        with ispyb.open(self.ISPYB_CONFIG_PATH) as self.conn:
            self.mx_acquisition = self.conn.mx_acquisition
            self.core = self.conn.core
        return self._store_scan_data()

    def _store_scan_data(self):
        pass

    def begin_deposition(self, success: str, reason: str):
        pass

    def end_deposition(self, success: str, reason: str):
        pass

    def _construct_comment(self) -> str:
        return "Hyperion rotation scan"


class StoreGridscanInIspyb(StoreInIspyb):
    VISIT_PATH_REGEX = r".+/([a-zA-Z]{2}\d{4,5}-\d{1,3})/"
    ispyb_params: GridscanIspybParams | None = None
    supper_left: list[int] | None = None
    y_steps: int | None = None
    y_step_size: int | None = None
    grid_ids: tuple[int, ...] | None = None

    def __init__(self, ispyb_config, parameters=None) -> None:
        self.full_params: FGSInternalParameters | None = parameters
        super().__init__(ispyb_config, parameters)

    def begin_deposition(self):
        (
            self.datacollection_ids,
            self.grid_ids,
            self.datacollection_group_id,
        ) = self.store_grid_scan(self.full_params)
        return self.datacollection_ids, self.grid_ids, self.datacollection_group_id

    def end_deposition(self, success: str, reason: str):
        """Write the end of datacollection data.

        Args:
            success (str): The success of the run, could be fail or abort
            reason (str):If the run failed, the reason why
        """
        LOGGER.info(
            f"End ispyb deposition with status '{success}' and reason '{reason}'."
        )
        if success == "fail":
            run_status = "DataCollection Unsuccessful"
        elif success == "abort":
            run_status = "DataCollection Unsuccessful"
        else:
            run_status = "DataCollection Successful"
        current_time = self.get_current_time_string()
        assert (
            self.datacollection_ids is not None
        ), "Can't end ISPyB deposition, datacollection IDs are missing"
        assert self.datacollection_group_id is not None
        for id in self.datacollection_ids:
            self.update_grid_scan_with_end_time_and_status(
                current_time, run_status, reason, id, self.datacollection_group_id
            )

    def store_grid_scan(self, full_params: FGSInternalParameters):
        self.full_params = full_params
        self.ispyb_params = full_params.artemis_params.ispyb_params
        self.detector_params = full_params.artemis_params.detector_params
        self.run_number = self.detector_params.run_number
        self.omega_start = self.detector_params.omega_start
        self.xtal_snapshots = self.ispyb_params.xtal_snapshots_omega_start
        self.upper_left = [
            int(self.ispyb_params.upper_left[0]),
            int(self.ispyb_params.upper_left[1]),
        ]
        self.y_steps = full_params.experiment_params.y_steps
        self.y_step_size = full_params.experiment_params.y_step_size

        with ispyb.open(self.ISPYB_CONFIG_PATH) as self.conn:
            self.mx_acquisition = self.conn.mx_acquisition
            self.core = self.conn.core

            return self._store_scan_data()

    def _mutate_datacollection_params_for_experiment(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        assert self.full_params is not None
        params["axis_end"] = self.omega_start
        params["n_images"] = self.full_params.experiment_params.x_steps * self.y_steps
        return params

    def update_grid_scan_with_end_time_and_status(
        self,
        end_time: str,
        run_status: str,
        reason: str,
        datacollection_id: int,
        datacollection_group_id: int,
    ) -> None:
        assert self.ispyb_params is not None
        assert self.detector_params is not None
        if reason is not None and reason != "":
            self.append_to_comment(datacollection_id, f"{run_status} reason: {reason}")

        with ispyb.open(self.ISPYB_CONFIG_PATH) as self.conn:
            self.mx_acquisition: MXAcquisition = self.conn.mx_acquisition

            params = self.mx_acquisition.get_data_collection_params()
            params["id"] = datacollection_id
            params["parentid"] = datacollection_group_id
            params["endtime"] = end_time
            params["run_status"] = run_status

            self.mx_acquisition.upsert_data_collection(list(params.values()))

    def _store_grid_info_table(self, ispyb_data_collection_id: int) -> int:
        assert self.ispyb_params is not None
        assert self.full_params is not None
        assert self.upper_left is not None

        params = self.mx_acquisition.get_dc_grid_params()

        params["parentid"] = ispyb_data_collection_id
        params["dxInMm"] = self.full_params.experiment_params.x_step_size
        params["dyInMm"] = self.y_step_size
        params["stepsX"] = self.full_params.experiment_params.x_steps
        params["stepsY"] = self.y_steps
        # Although the stored values is microns per pixel the columns in ISPyB are named
        # pixels per micron. See LIMS-564, which is tasked with fixing this inconsistency
        params["pixelsPerMicronX"] = self.ispyb_params.microns_per_pixel_x
        params["pixelsPerMicronY"] = self.ispyb_params.microns_per_pixel_y
        params["snapshotOffsetXPixel"], params["snapshotOffsetYPixel"] = self.upper_left
        params["orientation"] = Orientation.HORIZONTAL.value
        params["snaked"] = True

        return self.mx_acquisition.upsert_dc_grid(list(params.values()))

    def _construct_comment(self) -> str:
        assert self.ispyb_params is not None
        assert self.full_params is not None
        assert self.upper_left is not None
        assert self.y_step_size is not None

        bottom_right = oav_utils.bottom_right_from_top_left(
            self.upper_left,
            self.full_params.experiment_params.x_steps,
            self.y_steps,
            self.full_params.experiment_params.x_step_size,
            self.y_step_size,
            self.ispyb_params.microns_per_pixel_x,
            self.ispyb_params.microns_per_pixel_y,
        )
        return (
            "Artemis: Xray centring - Diffraction grid scan of "
            f"{self.full_params.experiment_params.x_steps} by "
            f"{self.y_steps} images in "
            f"{self.full_params.experiment_params.x_step_size*1e3} um by "
            f"{self.y_step_size*1e3} um steps. "
            f"Top left (px): [{int(self.upper_left[0])},{int(self.upper_left[1])}], "
            f"bottom right (px): [{bottom_right[0]},{bottom_right[1]}]."
        )

    def _store_position_table(self, dc_id: int) -> int:
        assert self.ispyb_params is not None
        params = self.mx_acquisition.get_dc_position_params()

        params["id"] = dc_id
        (
            params["pos_x"],
            params["pos_y"],
            params["pos_z"],
        ) = self.ispyb_params.position.tolist()

        return self.mx_acquisition.update_dc_position(list(params.values()))


class Store3DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config, parameters=None):
        super().__init__(ispyb_config, parameters)
        self.experiment_type = "Mesh3D"

    def _store_scan_data(self):
        data_collection_group_id = self._store_data_collection_group_table()

        data_collection_id_1 = self._store_data_collection_table(
            data_collection_group_id
        )

        self._store_position_table(data_collection_id_1)

        grid_id_1 = self._store_grid_info_table(data_collection_id_1)

        self.__prepare_second_scan_params()

        data_collection_id_2 = self._store_data_collection_table(
            data_collection_group_id
        )

        self._store_position_table(data_collection_id_2)

        grid_id_2 = self._store_grid_info_table(data_collection_id_2)

        return (
            [data_collection_id_1, data_collection_id_2],
            [grid_id_1, grid_id_2],
            data_collection_group_id,
        )

    def __prepare_second_scan_params(self):
        self.omega_start += 90
        self.run_number += 1
        self.xtal_snapshots = self.ispyb_params.xtal_snapshots_omega_end
        self.upper_left = [
            int(self.ispyb_params.upper_left[0]),
            int(self.ispyb_params.upper_left[2]),
        ]
        self.y_steps = self.full_params.experiment_params.z_steps
        self.y_step_size = self.full_params.experiment_params.z_step_size


class Store2DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config, parameters=None):
        super().__init__(ispyb_config, parameters)
        self.experiment_type = "mesh"

    def _store_scan_data(self):
        data_collection_group_id = self._store_data_collection_group_table()

        data_collection_id = self._store_data_collection_table(data_collection_group_id)

        self._store_position_table(data_collection_id)

        grid_id = self._store_grid_info_table(data_collection_id)

        return [data_collection_id], [grid_id], data_collection_group_id
