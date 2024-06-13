from enum import Enum
from os import environ
from pathlib import Path
from typing import Optional, Tuple

from mx_bluesky.I24.serial.log import _read_visit_directory_from_file


class SSXType(Enum):
    FIXED = "Serial Fixed"
    EXTRUDER = "Serial Jet"


OAV_CONFIG_FILES = {
    "zoom_params_file": "/dls_sw/i24/software/gda_versions/gda_9_34/config/xml/jCameraManZoomLevels.xml",
    "oav_config_json": "/dls_sw/i24/software/daq_configuration/json/OAVCentring.json",
    "display_config": "/dls_sw/i24/software/gda_versions/var/display.configuration",
}
OAV1_CAM = "http://bl24i-di-serv-01.diamond.ac.uk:8080/OAV1.mjpg.mjpg"

HEADER_FILES_PATH = Path("/dls_sw/i24/scripts/fastchips/").expanduser().resolve()

INTERNAL_FILES_PATH = Path(__file__).absolute().parent


def _params_file_location() -> Tuple[Path, Path]:
    beamline: Optional[str] = environ.get("BEAMLINE")
    filepath: Path

    if beamline:
        filepath = _read_visit_directory_from_file() / "tmp/serial/parameters"
    else:
        filepath = INTERNAL_FILES_PATH
    filepath_ft = filepath / "fixed_target"

    return filepath, filepath_ft


PARAM_FILE_NAME = "parameters.json"
# Paths for rw - these need to be created on startup if not existing
PARAM_FILE_PATH, PARAM_FILE_PATH_FT = _params_file_location()
LITEMAP_PATH = PARAM_FILE_PATH_FT / "litemaps"
FULLMAP_PATH = PARAM_FILE_PATH_FT / "fullmaps"
# Paths for r only
PVAR_FILE_PATH = INTERNAL_FILES_PATH / "fixed_target/pvar_files"
CS_FILES_PATH = INTERNAL_FILES_PATH / "fixed_target/cs"
