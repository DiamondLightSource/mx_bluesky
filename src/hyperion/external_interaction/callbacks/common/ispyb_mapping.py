from __future__ import annotations

import re
from typing import Optional

from dodal.devices.detector import DetectorParams

from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGroupInfo,
    DataCollectionInfo,
    DataCollectionPositionInfo,
)
from hyperion.external_interaction.ispyb.ispyb_dataclass import IspybParams
from hyperion.external_interaction.ispyb.ispyb_store import (
    EIGER_FILE_SUFFIX,
    I03_EIGER_DETECTOR,
)
from hyperion.external_interaction.ispyb.ispyb_utils import (
    VISIT_PATH_REGEX,
    get_current_time_string,
)
from hyperion.log import ISPYB_LOGGER


def populate_data_collection_group(
    experiment_type: str, detector_params: DetectorParams, ispyb_params: IspybParams
):
    dcg_info = DataCollectionGroupInfo(
        visit_string=get_visit_string(ispyb_params, detector_params),
        experiment_type=experiment_type,
        sample_id=ispyb_params.sample_id,
    )
    return dcg_info


def populate_data_collection_position_info(ispyb_params):
    # explicit cast to float because numpy int64, grrr...
    dc_pos_info = DataCollectionPositionInfo(
        float(ispyb_params.position[0]),
        float(ispyb_params.position[1]),
        float(ispyb_params.position[2]),
    )
    return dc_pos_info


def populate_remaining_data_collection_info(
    comment,
    data_collection_group_id,
    data_collection_info: DataCollectionInfo,
    detector_params,
    ispyb_params,
):
    data_collection_info.visit_string = get_visit_string(ispyb_params, detector_params)
    data_collection_info.parent_id = data_collection_group_id
    data_collection_info.sample_id = ispyb_params.sample_id
    data_collection_info.detector_id = I03_EIGER_DETECTOR
    data_collection_info.axis_start = data_collection_info.omega_start
    data_collection_info.comments = comment
    data_collection_info.detector_distance = detector_params.detector_distance
    data_collection_info.exp_time = detector_params.exposure_time
    data_collection_info.imgdir = detector_params.directory
    data_collection_info.imgprefix = detector_params.prefix
    data_collection_info.imgsuffix = EIGER_FILE_SUFFIX
    # Both overlap and n_passes included for backwards compatibility,
    # planned to be removed later
    data_collection_info.n_passes = 1
    data_collection_info.overlap = 0
    data_collection_info.start_image_number = 1
    beam_position = detector_params.get_beam_position_mm(
        detector_params.detector_distance
    )
    data_collection_info.xbeam = beam_position[0]
    data_collection_info.ybeam = beam_position[1]
    data_collection_info.start_time = get_current_time_string()
    # temporary file template until nxs filewriting is integrated and we can use
    # that file name
    data_collection_info.file_template = f"{detector_params.prefix}_{data_collection_info.data_collection_number}_master.h5"
    return data_collection_info


def get_proposal_and_session_from_visit_string(visit_string: str) -> tuple[str, int]:
    visit_parts = visit_string.split("-")
    assert len(visit_parts) == 2, f"Unexpected visit string {visit_string}"
    return visit_parts[0], int(visit_parts[1])


def get_visit_string_from_path(path: Optional[str]) -> Optional[str]:
    match = re.search(VISIT_PATH_REGEX, path) if path else None
    return str(match.group(1)) if match else None


def get_visit_string(ispyb_params: IspybParams, detector_params: DetectorParams) -> str:
    assert ispyb_params and detector_params, "StoreInISPyB didn't acquire params"
    visit_path_match = get_visit_string_from_path(ispyb_params.visit_path)
    if visit_path_match:
        return visit_path_match
    visit_path_match = get_visit_string_from_path(detector_params.directory)
    if not visit_path_match:
        raise ValueError(
            f"Visit not found from {ispyb_params.visit_path} or {detector_params.directory}"
        )
    return visit_path_match


def get_xtal_snapshots(ispyb_params):
    if ispyb_params.xtal_snapshots_omega_start:
        xtal_snapshots = ispyb_params.xtal_snapshots_omega_start[:3]
        ISPYB_LOGGER.info(
            f"Using rotation scan snapshots {xtal_snapshots} for ISPyB deposition"
        )
    else:
        ISPYB_LOGGER.warning("No xtal snapshot paths sent to ISPyB!")
        xtal_snapshots = []
    return xtal_snapshots + [None] * (3 - len(xtal_snapshots))
