import logging
import subprocess
from os import environ
from pathlib import Path

logger = logging.getLogger("I24ssx.run")


def get_location(default: str = "dev") -> str:
    return environ.get("BEAMLINE") or default


def get_edm_path() -> Path:
    return Path(__file__).parents[4] / "edm_serial"


def run_extruder():
    loc = get_location()
    logger.debug(f"Running on {loc}.")
    edm_path = get_edm_path()
    filepath = Path(__file__).parent
    logger.debug(f"Running {filepath}/run_extruder.sh")
    subprocess.run(["sh", filepath / "run_extruder.sh", edm_path.as_posix()])


def run_fixed_target():
    loc = get_location()
    logger.info(f"Running on {loc}.")
    edm_path = get_edm_path()
    filepath = Path(__file__).parent
    logger.debug(f"Running {filepath}/run_fixed_target.sh")
    subprocess.run(["sh", filepath / "run_fixed_target.sh", edm_path.as_posix()])
