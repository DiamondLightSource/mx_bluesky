"""
Chip manager for fixed target
This version changed to python3 March2020 by RLO
"""

import argparse
import json
import logging
import re
import shutil
import sys
import time
from pathlib import Path
from pprint import pformat
from time import sleep

import bluesky.plan_stubs as bps
import numpy as np
from blueapi.core import MsgGenerator
from dodal.beamlines import i24
from dodal.devices.i24.pmac import PMAC

from mx_bluesky.I24.serial import log
from mx_bluesky.I24.serial.fixed_target import i24ssx_Chip_Mapping_py3v1 as mapping
from mx_bluesky.I24.serial.fixed_target import i24ssx_Chip_StartUp_py3v1 as startup
from mx_bluesky.I24.serial.fixed_target.ft_utils import ChipType, Fiducials, MappingType
from mx_bluesky.I24.serial.parameters.constants import (
    CS_FILES_PATH,
    FULLMAP_PATH,
    LITEMAP_PATH,
    PARAM_FILE_NAME,
    PARAM_FILE_PATH_FT,
    PVAR_FILE_PATH,
)
from mx_bluesky.I24.serial.setup_beamline import Pilatus, caget, caput, pv
from mx_bluesky.I24.serial.setup_beamline.setup_detector import get_detector_type

logger = logging.getLogger("I24ssx.chip_manager")


def _coerce_to_path(path: Path | str) -> Path:
    if not isinstance(path, Path):
        return Path(path)
    return path


def setup_logging():
    # Log should now change name daily.
    logfile = time.strftime("i24fixedtarget_%d%B%y.log").lower()
    log.config(logfile)


@log.log_on_entry
def initialise_stages() -> MsgGenerator:
    # commented out filter lines 230719 as this stage not connected
    logger.info("Setting VMAX VELO ACCL HHL LLM pvs for stages")

    caput(pv.me14e_stage_x + ".VMAX", 20)
    caput(pv.me14e_stage_y + ".VMAX", 20)
    caput(pv.me14e_stage_z + ".VMAX", 20)
    # caput(pv.me14e_filter  + '.VMAX', 20)
    caput(pv.me14e_stage_x + ".VELO", 20)
    caput(pv.me14e_stage_y + ".VELO", 20)
    caput(pv.me14e_stage_z + ".VELO", 20)
    # caput(pv.me14e_filter  + '.VELO', 20)
    caput(pv.me14e_stage_x + ".ACCL", 0.01)
    caput(pv.me14e_stage_y + ".ACCL", 0.01)
    caput(pv.me14e_stage_z + ".ACCL", 0.01)
    # caput(pv.me14e_filter  + '.ACCL', 0.01)
    caput(pv.me14e_stage_x + ".HLM", 30)
    caput(pv.me14e_stage_x + ".LLM", -29)
    caput(pv.me14e_stage_y + ".HLM", 30)
    caput(pv.me14e_stage_y + ".LLM", -30)
    # caput(pv.me14e_stage_x + '.LLM', -30)
    caput(pv.me14e_stage_z + ".HLM", 5.1)
    caput(pv.me14e_stage_z + ".LLM", -4.1)
    # caput(pv.me14e_filter  + '.HLM', 45.0)
    # caput(pv.me14e_filter  + '.LLM', -45.0)
    caput(pv.me14e_gp1, 1)
    caput(pv.me14e_gp2, 0)
    caput(pv.me14e_gp3, 1)
    caput(pv.me14e_gp4, 0)
    caput(pv.me14e_filepath, "test")
    caput(pv.me14e_chip_name, "albion")
    caput(pv.me14e_dcdetdist, 1480)
    caput(pv.me14e_exptime, 0.01)
    caput(pv.me14e_pmac_str, "m508=100 m509=150")
    caput(pv.me14e_pmac_str, "m608=100 m609=150")
    caput(pv.me14e_pmac_str, "m708=100 m709=150")
    caput(pv.me14e_pmac_str, "m808=100 m809=150")

    # Define detector in use
    logger.debug("Define detector in use.")
    det_type = get_detector_type()

    caput(pv.pilat_cbftemplate, 0)

    sleep(0.1)
    logger.info("Clearing General Purpose PVs 1-120")
    for i in range(4, 120):
        pvar = "ME14E-MO-IOC-01:GP" + str(i)
        caput(pvar, 0)
        sys.stdout.write(".")
        sys.stdout.flush()

    caput(pv.me14e_gp100, "press set params to read visit")
    caput(pv.me14e_gp101, det_type.name)

    logger.info("Initialisation Complete")
    yield from bps.null()


@log.log_on_entry
def write_parameter_file(param_path: Path | str = PARAM_FILE_PATH_FT) -> MsgGenerator:
    param_path = _coerce_to_path(param_path)
    param_path.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Writing Parameter File: %s" % (param_path / PARAM_FILE_NAME).as_posix()
    )

    filename = caget(pv.me14e_chip_name)
    det_type = get_detector_type()
    map_type = caget(pv.me14e_gp2)

    # If file name ends in a digit this causes processing/pilatus pain.
    # Append an underscore
    if isinstance(det_type, Pilatus):
        caput(pv.pilat_cbftemplate, 0)
        m = re.search(r"\d+$", filename)
        if m is not None:
            # Note for future reference. Appending underscore causes more hassle and
            # high probability of users accidentally overwriting data. Use a dash
            filename = filename + "-"
            logger.debug(
                "Requested filename ends in a number. Appended dash: %s" % filename
            )

    params_dict = {
        "visit": caget(pv.me14e_gp100),
        "directory": caget(pv.me14e_filepath),
        "filename": filename,
        "exposure_time_s": caget(pv.me14e_exptime),
        "detector_distance_mm": caget(pv.me14e_dcdetdist),
        "detector_name": str(det_type),
        "num_exposures": caget(pv.me14e_gp3),
        "chip_type": caget(pv.me14e_gp1),
        "map_type": map_type,
        "pump_repeat": caget(pv.me14e_gp4),
        "checker_pattern": bool(caget(pv.me14e_gp111)),
        "laser_dwell_s": caget(pv.me14e_gp103),
        "laser_delay_s": caget(pv.me14e_gp110),
        "pre_pump_exposure_s": caget(pv.me14e_gp109),
    }

    with open(param_path / PARAM_FILE_NAME, "w") as f:
        json.dump(params_dict, f, indent=4)

    logger.info("Information written to file \n")
    logger.info(pformat(params_dict))

    if map_type == MappingType.Full:
        # This step creates some header files (.addr, .spec), containing the parameters,
        # that are only needed when full mapping is in use.
        logger.info("Full mapping in use. Running start up now.")
        startup.run()
    yield from bps.null()


def scrape_pvar_file(fid: str, pvar_dir: Path | str = PVAR_FILE_PATH):
    block_start_list = []
    pvar_dir = _coerce_to_path(pvar_dir)

    with open(pvar_dir / fid, "r") as f:
        lines = f.readlines()
    for line in lines:
        line = line.rstrip()
        if line.startswith("#"):
            continue
        elif line.startswith("P3000"):
            continue
        elif line.startswith("P3011"):
            continue
        elif not len(line.split(" ")) == 2:
            continue
        else:
            entry = line.split(" ")
            block_num = entry[0][2:4]
            x = entry[0].split("=")[1]
            y = entry[1].split("=")[1]
            block_start_list.append([block_num, x, y])
    return block_start_list


@log.log_on_entry
def define_current_chip(
    chipid: str = "oxford",
    param_path: Path | str = PVAR_FILE_PATH,
) -> MsgGenerator:
    logger.debug("Run load stock map for just the first block")
    yield from load_stock_map("Just The First Block")
    """
    Not sure what this is for:
    print 'Setting Mapping Type to Lite'
    caput(pv.me14e_gp2, 1)
    """
    chip_type = int(caget(pv.me14e_gp1))
    logger.info("Chip type:%s Chipid:%s" % (chip_type, chipid))
    if chipid == "oxford":
        caput(pv.me14e_gp1, 1)

    param_path = _coerce_to_path(param_path)

    with open(param_path / f"{chipid}.pvar", "r") as f:
        logger.info("Opening %s.pvar" % chipid)
        for line in f.readlines():
            if line.startswith("#"):
                continue
            line_from_file = line.rstrip("\n")
            logger.info("%s" % line_from_file)
            caput(pv.me14e_pmac_str, line_from_file)
    yield from bps.null()


@log.log_on_entry
def save_screen_map(litemap_path: Path | str = LITEMAP_PATH) -> MsgGenerator:
    litemap_path = _coerce_to_path(litemap_path)
    litemap_path.mkdir(parents=True, exist_ok=True)

    logger.info("Saving %s currentchip.map" % litemap_path.as_posix())
    with open(litemap_path / "currentchip.map", "w") as f:
        logger.debug("Printing only blocks with block_val == 1")
        for x in range(1, 82):
            block_str = "ME14E-MO-IOC-01:GP%i" % (x + 10)
            block_val = int(caget(block_str))
            if block_val == 1:
                logger.info("%s %d" % (block_str, block_val))
            line = "%02dstatus    P3%02d1 \t%s\n" % (x, x, block_val)
            f.write(line)
    yield from bps.null()


@log.log_on_entry
def upload_parameters(
    chipid: str = "oxford",
    litemap_path: Path | str = LITEMAP_PATH,
) -> MsgGenerator:
    logger.info("Uploading Parameters to the GeoBrick")
    if chipid == "oxford":
        caput(pv.me14e_gp1, 0)
        width = 8
    litemap_path = _coerce_to_path(litemap_path)

    with open(litemap_path / "currentchip.map", "r") as f:
        logger.info("Chipid %s" % chipid)
        logger.info("width %d" % width)
        x = 1
        for line in f.readlines()[: width**2]:
            cols = line.split()
            pvar = cols[1]
            value = cols[2]
            s = pvar + "=" + value
            if value != "1":
                s2 = pvar + "   "
                sys.stdout.write(s2)
            else:
                sys.stdout.write(s + " ")
            sys.stdout.flush()
            if x == width:
                print()
                x = 1
            else:
                x += 1
            caput(pv.me14e_pmac_str, s)
            sleep(0.02)

    logger.warning("Automatic Setting Mapping Type to Lite has been disabled")
    logger.debug("Upload parameters done.")
    yield from bps.null()


@log.log_on_entry
def upload_full(fullmap_path: Path | str = FULLMAP_PATH):
    fullmap_path = _coerce_to_path(fullmap_path)
    fullmap_path.mkdir(parents=True, exist_ok=True)

    with open(fullmap_path / "currentchip.full", "r") as fh:
        f = fh.readlines()

    for i in range(len(f) // 2):
        pmac_list = []
        for j in range(2):
            pmac_list.append(f.pop(0).rstrip("\n"))
        writeline = " ".join(pmac_list)
        logger.info("%s" % writeline)
        caput(pv.me14e_pmac_str, writeline)
        sleep(0.02)
    logger.debug("Upload fullmap done")


@log.log_on_entry
def load_stock_map(map_choice: str = "clear") -> MsgGenerator:
    logger.info("Adjusting Lite Map EDM Screen")
    logger.debug("Please wait, adjusting lite map")
    #
    r33 = [19, 18, 17, 26, 31, 32, 33, 24, 25]
    r55 = [9, 10, 11, 12, 13, 16, 27, 30, 41, 40, 39, 38, 37, 34, 23, 20] + r33
    r77 = [
        7,
        6,
        5,
        4,
        3,
        2,
        1,
        14,
        15,
        28,
        29,
        42,
        43,
        44,
        45,
        46,
        47,
        48,
        49,
        36,
        35,
        22,
        21,
        8,
    ] + r55
    #
    h33 = [3, 2, 1, 6, 7, 8, 9, 4, 5]
    x33 = [31, 32, 33, 40, 51, 50, 49, 42, 41]
    x55 = [25, 24, 23, 22, 21, 34, 39, 52, 57, 58, 59, 60, 61, 48, 43, 30] + x33
    x77 = [
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        20,
        35,
        38,
        53,
        56,
        71,
        70,
        69,
        68,
        67,
        66,
        65,
        62,
        47,
        44,
        29,
        26,
    ] + x55
    x99 = [
        9,
        8,
        7,
        6,
        5,
        4,
        3,
        2,
        1,
        18,
        19,
        36,
        37,
        54,
        55,
        72,
        73,
        74,
        75,
        76,
        77,
        78,
        79,
        80,
        81,
        64,
        63,
        46,
        45,
        28,
        27,
        10,
    ] + x77
    x44 = [22, 21, 20, 19, 30, 35, 46, 45, 44, 43, 38, 27, 28, 29, 36, 37]
    x49 = [x + 1 for x in range(49)]
    x66 = [
        10,
        11,
        12,
        13,
        14,
        15,
        18,
        31,
        34,
        47,
        50,
        51,
        52,
        53,
        54,
        55,
        42,
        39,
        26,
        23,
    ] + x44
    x88 = [
        8,
        7,
        6,
        5,
        4,
        3,
        2,
        1,
        16,
        17,
        32,
        33,
        48,
        49,
        64,
        63,
        62,
        61,
        60,
        59,
        58,
        57,
        56,
        41,
        40,
        25,
        24,
        9,
    ] + x66
    #
    # Columns for doing half chips
    c1 = [1, 2, 3, 4, 5, 6, 7, 8]
    c2 = [9, 10, 11, 12, 13, 14, 15, 16]
    c3 = [17, 18, 19, 20, 21, 22, 23, 24]
    c4 = [25, 26, 27, 28, 29, 30, 31, 32]
    c5 = [33, 34, 35, 36, 37, 38, 39, 40]
    c6 = [41, 42, 43, 44, 45, 46, 47, 48]
    c7 = [49, 50, 51, 52, 53, 54, 55, 56]
    c8 = [57, 58, 59, 60, 61, 62, 63, 64]
    half1 = c1 + c2 + c3 + c4
    half2 = c5 + c6 + c7 + c8

    map_dict = {}
    map_dict["Just The First Block"] = [1]
    map_dict["clear"] = []
    #
    map_dict["r33"] = r33
    map_dict["r55"] = r55
    map_dict["r77"] = r77
    #
    map_dict["h33"] = h33
    #
    map_dict["x33"] = x33
    map_dict["x44"] = x44
    map_dict["x49"] = x49
    map_dict["x55"] = x55
    map_dict["x66"] = x66
    map_dict["x77"] = x77
    map_dict["x88"] = x88
    map_dict["x99"] = x99

    map_dict["half1"] = half1
    map_dict["half2"] = half2

    logger.info("Clearing GP 10-74")
    for i in range(1, 65):
        pvar = "ME14E-MO-IOC-01:GP" + str(i + 10)
        caput(pvar, 0)
        sys.stdout.write(".")
        sys.stdout.flush()
    logger.info("Map cleared")
    logger.info("Loading Map Choice %s" % map_choice)
    for i in map_dict[map_choice]:
        pvar = "ME14E-MO-IOC-01:GP" + str(i + 10)
        caput(pvar, 1)
    logger.debug("Load stock map done.")
    yield from bps.null()


@log.log_on_entry
def load_lite_map(litemap_path: Path | str = LITEMAP_PATH) -> MsgGenerator:
    logger.debug("Run load stock map with 'clear' setting.")
    yield from load_stock_map("clear")
    # fmt: off
    # Oxford_block_dict is wrong (columns and rows need to flip) added in script below to generate it automatically however kept this for backwards compatiability/reference
    oxford_block_dict = {   # noqa: F841
        'A1': '01', 'A2': '02', 'A3': '03', 'A4': '04', 'A5': '05', 'A6': '06', 'A7': '07', 'A8': '08',
        'B1': '16', 'B2': '15', 'B3': '14', 'B4': '13', 'B5': '12', 'B6': '11', 'B7': '10', 'B8': '09',
        'C1': '17', 'C2': '18', 'C3': '19', 'C4': '20', 'C5': '21', 'C6': '22', 'C7': '23', 'C8': '24',
        'D1': '32', 'D2': '31', 'D3': '30', 'D4': '29', 'D5': '28', 'D6': '27', 'D7': '26', 'D8': '25',
        'E1': '33', 'E2': '34', 'E3': '35', 'E4': '36', 'E5': '37', 'E6': '38', 'E7': '39', 'E8': '40',
        'F1': '48', 'F2': '47', 'F3': '46', 'F4': '45', 'F5': '44', 'F6': '43', 'F7': '42', 'F8': '41',
        'G1': '49', 'G2': '50', 'G3': '51', 'G4': '52', 'G5': '53', 'G6': '54', 'G7': '55', 'G8': '56',
        'H1': '64', 'H2': '63', 'H3': '62', 'H4': '61', 'H5': '60', 'H6': '59', 'H7': '58', 'H8': '57',
    }
    # fmt: on
    chip_type = int(caget(pv.me14e_gp1))
    if chip_type in [ChipType.Oxford, ChipType.OxfordInner]:
        logger.info("Oxford Block Order")
        rows = ["A", "B", "C", "D", "E", "F", "G", "H"]
        columns = list(range(1, 10))
        btn_names = {}
        flip = True
        for x, column in enumerate(columns):
            for y, row in enumerate(rows):
                i = x * 8 + y
                if i % 8 == 0 and flip is False:
                    flip = True
                    z = 8 - (y + 1)
                elif i % 8 == 0 and flip is True:
                    flip = False
                    z = y
                elif flip is False:
                    z = y
                elif flip is True:
                    z = 8 - (y + 1)
                else:
                    logger.warning("Problem in Chip Grid Creation")
                    break
                button_name = str(row) + str(column)
                lab_num = x * 8 + z
                label = "%02.d" % (lab_num + 1)
                btn_names[button_name] = label
        block_dict = btn_names

    litemap_path = _coerce_to_path(litemap_path)

    litemap_fid = str(caget(pv.me14e_gp5)) + ".lite"
    logger.info("Please wait, loading LITE map")
    logger.debug("Loading Lite Map")
    logger.info("Opening %s" % (litemap_path / litemap_fid))
    with open(litemap_path / litemap_fid, "r") as fh:
        f = fh.readlines()
    for line in f:
        entry = line.split()
        block_name = entry[0]
        yesno = entry[1]
        block_num = block_dict[block_name]
        pvar = "ME14E-MO-IOC-01:GP" + str(int(block_num) + 10)
        logger.info("Block: %s \tScanned: %s \tPVAR: %s" % (block_name, yesno, pvar))
    logger.debug("Load lite map done")
    yield from bps.null()


@log.log_on_entry
def load_full_map(fullmap_path: Path | str = FULLMAP_PATH):
    params = startup.read_parameter_file()
    fullmap_path = _coerce_to_path(fullmap_path)

    fullmap_fid = fullmap_path / f"{str(caget(pv.me14e_gp5))}.spec"
    logger.info("Opening %s" % fullmap_fid)
    mapping.plot_file(fullmap_fid, params.chip_type.value)
    mapping.convert_chip_to_hex(fullmap_fid, params.chip_type.value)
    shutil.copy2(fullmap_fid.with_suffix(".full"), fullmap_path / "currentchip.full")
    logger.info(
        "Copying %s to %s"
        % (fullmap_fid.with_suffix(".full"), fullmap_path / "currentchip.full")
    )
    logger.debug("Load full map done")


@log.log_on_entry
def moveto(place: str = "origin", pmac: PMAC = None) -> MsgGenerator:
    if not pmac:
        pmac = i24.pmac()
    logger.info(f"Move to: {place}")
    if place == Fiducials.zero:
        logger.info("Chip aspecific move.")
        pmac.pmac_string.set("!x0y0z0").wait()
        return

    chip_type = int(caget(pv.me14e_gp1))
    logger.info(f"Chip type is {ChipType(chip_type)}")
    if chip_type not in list(ChipType):
        logger.warning("Unknown chip_type move")
        return

    logger.info(f"{str(ChipType(chip_type))} Move")
    chip_move = ChipType(chip_type).get_approx_chip_size()

    def move_xy(x, y):
        move_status = pmac.x.move(x, wait=False)
        move_status &= pmac.y.move(y, wait=False)
        move_status.wait()

    if place == Fiducials.origin:
        move_xy(0.0, 0.0)
    if place == Fiducials.fid1:
        move_xy(chip_move, 0.0)
    if place == Fiducials.fid2:
        move_xy(0.0, chip_move)
    yield from bps.null()


@log.log_on_entry
def moveto_preset(place: str, pmac: PMAC = None) -> MsgGenerator:
    if not PMAC:
        pmac = i24.pmac()

    def move_xyz(x, y, z):
        move_status = pmac.x.move(x, wait=False)
        move_status &= pmac.y.move(y, wait=False)
        move_status &= pmac.z.move(z, wait=False)
        move_status.wait()

    # Non Chip Specific Move
    if place == "zero":
        logger.info("Moving to %s" % place)
        pmac.pmac_string.set("!x0y0z0").wait()

    elif place == "load_position":
        logger.info("load position")
        caput(pv.bs_mp_select, "Robot")
        caput(pv.bl_mp_select, "Out")
        caput(pv.det_z, 1300)

    elif place == "collect_position":
        logger.info("collect position")
        caput(pv.me14e_filter, 20)
        move_xyz(0.0, 0.0, 0.0)
        caput(pv.bs_mp_select, "Data Collection")
        caput(pv.bl_mp_select, "In")

    elif place == "microdrop_position":
        logger.info("microdrop align position")
        move_xyz(6.0, -7.8, 0.0)
    yield from bps.null()


@log.log_on_entry
def laser_control(laser_setting: str, pmac: PMAC = None) -> MsgGenerator:
    logger.info("Move to: %s" % laser_setting)
    if not pmac:
        pmac = i24.pmac()
    if laser_setting == "laser1on":  # these are in laser edm
        logger.info("Laser 1 /BNC2 shutter is open")
        # Use M712 = 0 if triggering on falling edge. M712 =1 if on rising edge
        # Be sure to also change laser1off
        # caput(pv.me14e_pmac_str, ' M712=0 M711=1')
        pmac.pmac_string.set(" M712=1 M711=1").wait()

    elif laser_setting == "laser1off":
        logger.info("Laser 1 shutter is closed")
        pmac.pmac_string.set(" M712=0 M711=1").wait()

    elif laser_setting == "laser2on":
        logger.info("Laser 2 / BNC3 shutter is open")
        pmac.pmac_string.set(" M812=1 M811=1").wait()

    elif laser_setting == "laser2off":
        logger.info("Laser 2 shutter is closed")
        pmac.pmac_string.set(" M812=0 M811=1").wait()

    elif laser_setting == "laser1burn":
        led_burn_time = caget(pv.me14e_gp103)
        logger.info("Laser 1  on")
        logger.info("Burn time is %s s" % led_burn_time)
        pmac.pmac_string.set(" M712=1 M711=1").wait()
        sleep(int(float(led_burn_time)))
        logger.info("Laser 1 off")
        pmac.pmac_string.set(" M712=0 M711=1").wait()

    elif laser_setting == "laser2burn":
        led_burn_time = caget(pv.me14e_gp109)
        logger.info("Laser 2 on")
        logger.info("burntime %s s" % led_burn_time)
        pmac.pmac_string.set(" M812=1 M811=1").wait()
        sleep(int(float(led_burn_time)))
        logger.info("Laser 2 off")
        pmac.pmac_string.set(" M812=0 M811=1").wait()
    yield from bps.null()


@log.log_on_entry
def scrape_mtr_directions(param_path: Path | str = CS_FILES_PATH):
    param_path = _coerce_to_path(param_path)

    with open(param_path / "motor_direction.txt", "r") as f:
        lines = f.readlines()
    mtr1_dir, mtr2_dir, mtr3_dir = 1.0, 1.0, 1.0
    for line in lines:
        if line.startswith("mtr1"):
            mtr1_dir = float(line.split("=")[1])
        elif line.startswith("mtr2"):
            mtr2_dir = float(line.split("=")[1])
        elif line.startswith("mtr3"):
            mtr3_dir = float(line.split("=")[1])
        else:
            continue
    logger.debug("mt1_dir %s mtr2_dir %s mtr3_dir %s" % (mtr1_dir, mtr2_dir, mtr3_dir))
    return mtr1_dir, mtr2_dir, mtr3_dir


@log.log_on_entry
def fiducial(point: int = 1, param_path: Path | str = CS_FILES_PATH) -> MsgGenerator:
    scale = 10000.0  # noqa: F841
    param_path = _coerce_to_path(param_path)

    mtr1_dir, mtr2_dir, mtr3_dir = scrape_mtr_directions(param_path)

    rbv_1 = float(caget(pv.me14e_stage_x + ".RBV"))
    rbv_2 = float(caget(pv.me14e_stage_y + ".RBV"))
    rbv_3 = float(caget(pv.me14e_stage_z + ".RBV"))

    raw_1 = float(caget(pv.me14e_stage_x + ".RRBV"))
    raw_2 = float(caget(pv.me14e_stage_y + ".RRBV"))
    raw_3 = float(caget(pv.me14e_stage_z + ".RRBV"))

    f_x = rbv_1
    f_y = rbv_2
    f_z = rbv_3

    logger.info("Writing Fiducial File %s/fiducial_%s.txt" % (param_path, point))
    logger.info("MTR\tRBV\tRAW\tCorr\tf_value")
    logger.info("MTR1\t%1.4f\t%i\t%i\t%1.4f" % (rbv_1, raw_1, mtr1_dir, f_x))
    logger.info("MTR2\t%1.4f\t%i\t%i\t%1.4f" % (rbv_2, raw_2, mtr2_dir, f_y))
    logger.info("MTR3\t%1.4f\t%i\t%i\t%1.4f" % (rbv_3, raw_3, mtr3_dir, f_z))

    with open(param_path / f"fiducial_{point}.txt", "w") as f:
        f.write("MTR\tRBV\tRAW\tCorr\tf_value\n")
        f.write("MTR1\t%1.4f\t%i\t%i\t%1.4f\n" % (rbv_1, raw_1, mtr1_dir, f_x))
        f.write("MTR2\t%1.4f\t%i\t%i\t%1.4f\n" % (rbv_2, raw_2, mtr2_dir, f_y))
        f.write("MTR3\t%1.4f\t%i\t%i\t%1.4f" % (rbv_3, raw_3, mtr3_dir, f_z))
    logger.info(f"Fiducial {point} set.")
    yield from bps.null()


def scrape_mtr_fiducials(point: int, param_path: Path | str = CS_FILES_PATH):
    param_path = _coerce_to_path(param_path)

    with open(param_path / f"fiducial_{point}.txt", "r") as f:
        f_lines = f.readlines()[1:]
    f_x = float(f_lines[0].rsplit()[4])
    f_y = float(f_lines[1].rsplit()[4])
    f_z = float(f_lines[2].rsplit()[4])
    return f_x, f_y, f_z


@log.log_on_entry
def cs_maker(pmac: PMAC = None) -> MsgGenerator:
    """
    Coordinate system.

    Values for scalex, scaley, scalez, and skew, as well as the sign of
    Sx, Sy, Sz are stored in a .json file and should be modified there.
    Location of file: src/mx_bluesky/I24/serial/parameters/cs_maker.json

    Theory
    Rx: rotation about X-axis, pitch
    Ry: rotation about Y-axis, yaw
    Rz: rotation about Z-axis, roll
    The order of rotation is Roll->Yaw->Pitch (Rx*Ry*Rz)
    Rx           Ry          Rz
    |1  0   0| | Cy  0 Sy| |Cz -Sz 0|   | CyCz        -CxSz         Sy  |
    |0 Cx -Sx|*|  0  1  0|*|Sz  Cz 0| = | SxSyCz+CxSz -SxSySz+CxCz -SxCy|
    |0 Sx  Cx| |-Sy  0 Cy| | 0   0 1|   |-CxSyCz+SxSz  CxSySz+SxCz  CxCy|

    BELOW iS TEST TEST (CLOCKWISE)
    Rx           Ry          Rz
    |1  0   0| | Cy 0 -Sy| |Cz  Sz 0|   | CyCz         CxSz         -Sy |
    |0 Cx  Sx|*|  0  1  0|*|-Sz Cz 0| = | SxSyCz-CxSz  SxSySz+CxCz  SxCy|
    |0 -Sx Cx| | Sy  0 Cy| | 0   0 1|   | CxSyCz+SxSz  CxSySz-SxCz  CxCy|


    Skew:
    Skew is the difference between the Sz1 and Sz2 after rotation is taken out.
    This should be measured in situ prior to expriment, ie. measure by hand using
    opposite and adjacent RBV after calibration of scale factors.
    """
    if not pmac:
        pmac = i24.pmac()

    chip_type = int(caget(pv.me14e_gp1))
    fiducial_dict = {}
    fiducial_dict[0] = [25.400, 25.400]
    fiducial_dict[1] = [24.600, 24.600]
    fiducial_dict[2] = [25.400, 25.400]
    fiducial_dict[3] = [18.25, 18.25]
    logger.info("Chip type is %s with size %s" % (chip_type, fiducial_dict[chip_type]))

    mtr1_dir, mtr2_dir, mtr3_dir = scrape_mtr_directions()
    f1_x, f1_y, f1_z = scrape_mtr_fiducials(1)
    f2_x, f2_y, f2_z = scrape_mtr_fiducials(2)
    logger.info("mtr1 direction: %s" % mtr1_dir)
    logger.info("mtr2 direction: %s" % mtr2_dir)
    logger.info("mtr3 direction: %s" % mtr3_dir)

    # Scale parameters saved in json file
    try:
        with open(CS_FILES_PATH / "cs_maker.json", "r") as fh:
            cs_info = json.load(fh)
    except json.JSONDecodeError:
        logger.error("Invalid JSON file.")
        raise

    try:
        scalex, scaley, scalez = (
            float(cs_info["scalex"]),
            float(cs_info["scaley"]),
            float(cs_info["scalez"]),
        )
        skew = float(cs_info["skew"])
        Sx_dir, Sy_dir, Sz_dir = (
            int(cs_info["Sx_dir"]),
            int(cs_info["Sy_dir"]),
            int(cs_info["Sz_dir"]),
        )
    except KeyError:
        logger.error("Wrong or missing key in the cs json file.")
        raise

    def check_dir(val):
        if val not in [1, -1]:
            raise ValueError("Wrong value for direction. Please set to either -1 or 1.")

    check_dir(Sx_dir)
    check_dir(Sy_dir)
    check_dir(Sz_dir)

    # Rotation Around Z
    # If stages upsidedown (I24) change sign of Sz
    Sz1 = -1 * f1_y / fiducial_dict[chip_type][0]
    Sz2 = f2_x / fiducial_dict[chip_type][1]
    Sz = Sz_dir * ((Sz1 + Sz2) / 2)
    Cz = np.sqrt((1 - Sz**2))
    logger.info("Sz1 , %1.4f, %1.4f" % (Sz1, np.degrees(np.arcsin(Sz1))))
    logger.info("Sz2 , %1.4f, %1.4f" % (Sz2, np.degrees(np.arcsin(Sz2))))
    logger.info("Sz , %1.4f, %1.4f" % (Sz, np.degrees(np.arcsin(Sz))))
    logger.info("Cz , %1.4f, %1.4f" % (Cz, np.degrees(np.arcsin(Cz))))
    # Rotation Around Y
    Sy = Sy_dir * f1_z / fiducial_dict[chip_type][0]
    Cy = np.sqrt((1 - Sy**2))
    logger.info("Sy , %1.4f, %1.4f" % (Sy, np.degrees(np.arcsin(Sy))))
    logger.info("Cy , %1.4f, %1.4f" % (Cy, np.degrees(np.arcsin(Cy))))
    # Rotation Around X
    # If stages upsidedown (I24) change sign of Sx
    Sx = Sx_dir * f2_z / fiducial_dict[chip_type][1]
    Cx = np.sqrt((1 - Sx**2))
    logger.info("Sx , %1.4f, %1.4f" % (Sx, np.degrees(np.arcsin(Sx))))
    logger.info("Cx , %1.4f, %1.4f" % (Cx, np.degrees(np.arcsin(Cx))))

    x1factor = mtr1_dir * scalex * (Cy * Cz)
    y1factor = mtr2_dir * scaley * (-1.0 * Cx * Sz)
    z1factor = mtr3_dir * scalez * Sy

    x2factor = mtr1_dir * scalex * ((Sx * Sy * Cz) + (Cx * Sz))
    y2factor = mtr2_dir * scaley * ((Cx * Cz) - (Sx * Sy * Sz))
    z2factor = mtr3_dir * scalez * (-1.0 * Sx * Cy)

    x3factor = mtr1_dir * scalex * ((Sx * Sz) - (Cx * Sy * Cz))
    y3factor = mtr2_dir * scaley * ((Cx * Sy * Sz) + (Sx * Cz))
    z3factor = mtr3_dir * scalez * (Cx * Cy)

    logger.info("Skew being used is: %1.4f" % skew)
    s1 = np.degrees(np.arcsin(Sz1))
    s2 = np.degrees(np.arcsin(Sz2))
    rot = np.degrees(np.arcsin((Sz1 + Sz2) / 2))
    calc_skew = (s1 - rot) - (s2 - rot)
    logger.info("s1:%1.4f s2:%1.4f rot:%1.4f" % (s1, s2, rot))
    logger.info("Calculated rotation from current fiducials is: %1.4f" % rot)
    logger.info("Calculated Skew from current fiducials is: %1.4f" % calc_skew)
    logger.info("Calculated Skew has been known to have the wrong sign")

    sinD = np.sin((skew / 2) * (np.pi / 180))
    cosD = np.cos((skew / 2) * (np.pi / 180))
    new_x1factor = (x1factor * cosD) + (y1factor * sinD)
    new_y1factor = (x1factor * sinD) + (y1factor * cosD)
    new_x2factor = (x2factor * cosD) + (y2factor * sinD)
    new_y2factor = (x2factor * sinD) + (y2factor * cosD)

    cs1 = "#1->%+1.3fX%+1.3fY%+1.3fZ" % (new_x1factor, new_y1factor, z1factor)
    cs2 = "#2->%+1.3fX%+1.3fY%+1.3fZ" % (new_x2factor, new_y2factor, z2factor)
    cs3 = "#3->%+1.3fX%+1.3fY%+1.3fZ" % (x3factor, y3factor, z3factor)
    logger.info("PMAC strings. \ncs1: %s \ncs2: %scs3: %s" % (cs1, cs2, cs3))
    logger.info(
        """These next values should be 1.
        This is the sum of the squares of the factors divided by their scale."""
    )
    sqfact1 = np.sqrt(x1factor**2 + y1factor**2 + z1factor**2) / scalex
    sqfact2 = np.sqrt(x2factor**2 + y2factor**2 + z2factor**2) / scaley
    sqfact3 = np.sqrt(x3factor**2 + y3factor**2 + z3factor**2) / scalez
    logger.info("%1.4f \n %1.4f \n %1.4f" % (sqfact1, sqfact2, sqfact3))
    logger.debug("Long wait, please be patient")
    pmac.pmac_string.set("!x0y0z0").wait()
    sleep(2.5)
    pmac.pmac_string.set("&2").wait()
    pmac.pmac_string.set(cs1).wait()
    pmac.pmac_string.set(cs2).wait()
    pmac.pmac_string.set(cs3).wait()
    pmac.pmac_string.set("!x0y0z0").wait()
    sleep(0.1)
    pmac.home_stages()
    sleep(0.1)
    logger.debug("Chip_type is %s" % chip_type)
    if chip_type == 0:
        pmac.pmac_string.set("!x0.4y0.4").wait()
        sleep(0.1)
        pmac.home_stages()
    else:
        pmac.home_stages()
    logger.debug("CSmaker done.")
    yield from bps.null()


def cs_reset(pmac: PMAC = None) -> MsgGenerator:
    """Used to clear CS when using Custom Chip"""
    if not pmac:
        pmac = i24.pmac()
    cs1 = "#1->-10000X+0Y+0Z"
    cs2 = "#2->+0X+10000Y+0Z"
    cs3 = "#3->0X+0Y+10000Z"
    strg = "\n".join([cs1, cs2, cs3])
    print(strg)
    pmac.pmac_string.set("&2").wait()
    pmac.pmac_string.set(cs1).wait()
    pmac.pmac_string.set(cs2).wait()
    pmac.pmac_string.set(cs3).wait()
    logger.debug("CSreset Done")
    yield from bps.null()


@log.log_on_entry
def pumpprobe_calc() -> MsgGenerator:
    logger.info("Calculate and show exposure and dwell time for each option.")
    exptime = float(caget(pv.me14e_exptime))
    pumpexptime = float(caget(pv.me14e_gp103))
    movetime = 0.008
    logger.info("X-ray exposure time %s" % exptime)
    logger.info("Laser dwell time %s" % pumpexptime)
    repeat1 = 2 * 20 * (movetime + (pumpexptime + exptime) / 2)
    repeat2 = 4 * 20 * (movetime + (pumpexptime + exptime) / 2)
    repeat3 = 6 * 20 * (movetime + (pumpexptime + exptime) / 2)
    repeat5 = 10 * 20 * (movetime + (pumpexptime + exptime) / 2)
    repeat10 = 20 * 20 * (movetime + (pumpexptime + exptime) / 2)
    for pv_name, repeat in (
        (pv.me14e_gp104, repeat1),
        (pv.me14e_gp105, repeat2),
        (pv.me14e_gp106, repeat3),
        (pv.me14e_gp107, repeat5),
        (pv.me14e_gp108, repeat10),
    ):
        rounded = round(repeat, 4)
        caput(pv_name, rounded)
        logger.info("Repeat (%s): %s s" % (pv_name, rounded))
    # logger.info("repeat10 (%s): %s s" % (pv.me14e_gp108, round(repeat10, 4)))
    logger.debug("PP calculations done")
    yield from bps.null()


@log.log_on_entry
def block_check() -> MsgGenerator:
    caput(pv.me14e_gp9, 0)
    while True:
        if int(caget(pv.me14e_gp9)) == 0:
            chip_type = int(caget(pv.me14e_gp1))
            if chip_type == ChipType.Minichip:
                logger.info("Oxford mini chip in use.")
                block_start_list = scrape_pvar_file("minichip_oxford.pvar")
            elif chip_type == ChipType.Custom:
                logger.error("This is a custom chip, no block check available!")
                raise ValueError(
                    "Chip type set to 'custom', which has no block check."
                    "If not using a custom chip, please double check chip in the GUI."
                )
            else:
                logger.warning("Default is Oxford chip block start list.")
                block_start_list = scrape_pvar_file("oxford.pvar")
            for entry in block_start_list:
                if int(caget(pv.me14e_gp9)) != 0:
                    logger.warning("Block Check Aborted")
                    sleep(1.0)
                    break
                block, x, y = entry
                logger.debug("Block: %s -> (x=%s y=%s)" % (block, x, y))
                caput(pv.me14e_pmac_str, "!x%sy%s" % (x, y))
                time.sleep(0.4)
        else:
            logger.warning("Block Check Aborted due to GP 9 not equalling 0")
            break
        break
    logger.debug("Block check done")
    yield from bps.null()


def parse_args_and_run_parsed_function(args):
    print(f"Run with {args}")
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        help="Choose command.",
        required=True,
        dest="sub-command",
    )
    parser_fullmap = subparsers.add_parser("load_full_map")
    parser_fullmap.set_defaults(func=load_full_map)
    parser_upld = subparsers.add_parser("upload_full")
    parser_upld.set_defaults(func=upload_full)

    args = parser.parse_args(args)

    args_dict = vars(args)
    args_dict.pop("sub-command")
    args_dict.pop("func")(**args_dict)


if __name__ == "__main__":
    setup_logging()
    # TODO have this in each function
    # Really tempted to make a wrapper ...

    parse_args_and_run_parsed_function(sys.argv[1:])
