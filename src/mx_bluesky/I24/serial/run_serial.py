import logging
import subprocess
from os import environ
from pathlib import Path

from mx_bluesky.I24.serial.log import _read_visit_directory_from_file

logger = logging.getLogger("I24ssx.run")


def get_location(default: str = "dev") -> str:
    return environ.get("BEAMLINE") or default


def get_edm_path() -> Path:
    return Path(__file__).parents[4] / "edm_serial"


def _get_file_path() -> Path:
    return Path(__file__).parent


def _create_params_file_dir(expt: str = "extruder"):
    """Create the directories to save parameters/map files on start-up."""
    beamline: str = get_location()
    filepath: Path

    if beamline == "dev":
        filepath = _get_file_path() / "parameters"
    else:
        filepath = _read_visit_directory_from_file() / "tmp/serial/parameters"
    logger.debug(f"Creating parameter files directory in {filepath}.")
    filepath.mkdir(parents=True, exist_ok=True)
    if expt == "fixed_target":
        filepath_ft = filepath / "fixed_target"
        dirs_to_create = [
            filepath_ft,
            filepath_ft / "litemaps",
            filepath_ft / "fullmaps",
        ]
        for p in dirs_to_create:
            p.mkdir(parents=True, exist_ok=True)


def run_extruder():
    loc = get_location()
    logger.debug(f"Running on {loc}.")
    edm_path = get_edm_path()
    filepath = _get_file_path()
    _create_params_file_dir("extruder")
    logger.debug(f"Running {filepath}/run_extruder.sh")
    subprocess.run(["sh", filepath / "run_extruder.sh", edm_path.as_posix()])


def run_fixed_target():
    loc = get_location()
    logger.info(f"Running on {loc}.")
    edm_path = get_edm_path()
    filepath = _get_file_path()
    _create_params_file_dir("fixed_target")
    logger.debug(f"Running {filepath}/run_fixed_target.sh")
    subprocess.run(["sh", filepath / "run_fixed_target.sh", edm_path.as_posix()])
