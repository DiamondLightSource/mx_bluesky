"""
Startup utilities for chip
"""

import logging
import os
import string
import time
from pathlib import Path
from typing import List

import numpy as np

from mx_bluesky.I24.serial import log
from mx_bluesky.I24.serial.fixed_target.ft_utils import ChipType
from mx_bluesky.I24.serial.parameters import FixedTargetParameters
from mx_bluesky.I24.serial.parameters.constants import (
    HEADER_FILES_PATH,
    PARAM_FILE_NAME,
    PARAM_FILE_PATH_FT,
)

logger = logging.getLogger("I24ssx.chip_startup")


def setup_logging():
    # Log should now change name daily.
    logfile = time.strftime("i24fixedtarget_%d%B%y.log").lower()
    log.config(logfile)


def read_parameter_file(param_path: Path | str = PARAM_FILE_PATH_FT):
    if not isinstance(param_path, Path):
        param_path = Path(param_path)
    params_file = param_path / PARAM_FILE_NAME
    params = FixedTargetParameters.from_file(params_file)
    return params


@log.log_on_entry
def fiducials(chip_type: int):
    if chip_type in [ChipType.Oxford, ChipType.OxfordInner, ChipType.Minichip]:
        fiducial_list: list = []
        # No fiducial for custom
    elif chip_type == ChipType.Custom:
        logger.warning("No fiducials for custom chip")
    else:
        logger.warning(f"Unknown chip_type, {chip_type}, in fiducials")
    return fiducial_list


@log.log_on_entry
def get_format(chip_type: ChipType):
    if chip_type == ChipType.Oxford:
        w2w = 0.125
        b2b_horz = 0.800
        b2b_vert = 0.800
        chip_format = [8, 8, 20, 20]
    elif chip_type == ChipType.OxfordInner:
        w2w = 0.600
        b2b_horz = 0.0
        b2b_vert = 0.0
        chip_format = [1, 1, 25, 25]
    elif chip_type == ChipType.Minichip:
        w2w = 0.125
        b2b_horz = 0
        b2b_vert = 0
        chip_format = [1, 1, 20, 20]
    else:
        msg = f"Unknown chip_type, {chip_type}"
        logger.error(msg)
        raise ValueError(msg)
    cell_format = chip_format + [w2w, b2b_horz, b2b_vert]
    logger.info(f"Cell format for chip type {str(chip_type)}: {cell_format}")
    return cell_format


def get_xy(addr: str, chip_type: ChipType):
    entry = addr.split("_")[-2:]
    R, C = entry[0][0], entry[0][1]
    r2, c2 = entry[1][0], entry[1][1]
    blockR = string.ascii_uppercase.index(R)
    blockC = int(C) - 1
    lowercase_list = list(string.ascii_lowercase + string.ascii_uppercase + "0")
    windowR = lowercase_list.index(r2)
    windowC = lowercase_list.index(c2)

    (
        x_block_num,
        y_block_num,
        x_window_num,
        y_window_num,
        w2w,
        b2b_horz,
        b2b_vert,
    ) = get_format(chip_type)

    x = (blockC * b2b_horz) + (blockC * (x_window_num - 1) * w2w) + (windowC * w2w)
    y = (blockR * b2b_vert) + (blockR * (y_window_num - 1) * w2w) + (windowR * w2w)
    return x, y


def pathli(l_in=[], way="typewriter", reverse=False):
    if reverse is True:
        li = list(reversed(l_in))
    else:
        li = list(l_in)
    long_list = []
    if li:
        if way == "typewriter":
            for i in range(len(li) ** 2):
                long_list.append(li[i % len(li)])
        elif way == "snake":
            lr = list(reversed(li))
            for rep in range(len(li)):
                if rep % 2 == 0:
                    long_list += li
                else:
                    long_list += lr
        elif way == "snake53":
            lr = list(reversed(li))
            for rep in range(53):
                if rep % 2 == 0:
                    long_list += li
                else:
                    long_list += lr
        elif way == "expand":
            for entry in li:
                for rep in range(len(li)):
                    long_list.append(entry)
        elif way == "expand28":
            for entry in li:
                for rep in range(28):
                    long_list.append(entry)
        elif way == "expand25":
            for entry in li:
                for rep in range(25):
                    long_list.append(entry)
        else:
            logger.warning("No known path, way =  %s" % way)
    else:
        logger.warning("No list written")
    return long_list


def zippum(list_1_args, list_2_args):
    list_1, type_1, reverse_1 = list_1_args
    list_2, type_2, reverse_2 = list_2_args
    A_path = pathli(list_1, type_1, reverse_1)
    B_path = pathli(list_2, type_2, reverse_2)
    zipped_list = []
    for a, b in zip(A_path, B_path):
        zipped_list.append(a + b)
    return zipped_list


def get_alphanumeric(chip_type: ChipType):
    cell_format = get_format(chip_type)
    blk_num = cell_format[0]
    wnd_num = cell_format[2]
    uppercase_list = list(string.ascii_uppercase)[:blk_num]
    lowercase_list = list(string.ascii_lowercase + string.ascii_uppercase + "0")[
        :wnd_num
    ]
    number_list = [str(x) for x in range(1, blk_num + 1)]

    block_list = zippum([uppercase_list, "expand", 0], [number_list, "typewriter", 0])
    window_list = zippum(
        [lowercase_list, "expand", 0], [lowercase_list, "typewriter", 0]
    )

    alphanumeric_list = []
    for block in block_list:
        for window in window_list:
            alphanumeric_list.append(block + "_" + window)
    logger.info("Length of alphanumeric list = %s" % len(alphanumeric_list))
    return alphanumeric_list


@log.log_on_entry
def get_shot_order(chip_type: ChipType):
    cell_format = get_format(chip_type)
    blk_num = cell_format[0]
    wnd_num = cell_format[2]
    uppercase_list = list(string.ascii_uppercase)[:blk_num]
    number_list = [str(x) for x in range(1, blk_num + 1)]
    lowercase_list = list(string.ascii_lowercase + string.ascii_uppercase + "0")[
        :wnd_num
    ]

    block_list = zippum([uppercase_list, "snake", 0], [number_list, "expand", 0])
    window_dn = zippum([lowercase_list, "expand", 0], [lowercase_list, "snake", 0])
    window_up = zippum([lowercase_list, "expand", 1], [lowercase_list, "snake", 0])

    switch = 0
    count = 0
    collect_list = []
    for block in block_list:
        if switch == 0:
            for window in window_dn:
                collect_list.append(block + "_" + window)
            count += 1
            if count == blk_num:
                count = 0
                switch = 1
        else:
            for window in window_up:
                collect_list.append(block + "_" + window)
            count += 1
            if count == blk_num:
                count = 0
                switch = 0

    logger.info("Length of collect list = %s" % len(collect_list))
    return collect_list


@log.log_on_entry
def write_file(
    location: str = "i24",
    suffix: str = ".addr",
    order: str = "alphanumeric",
    param_file_path: Path = PARAM_FILE_PATH_FT,
    save_path: Path = HEADER_FILES_PATH,
):
    if location == "i24":
        params = read_parameter_file(param_file_path)
    else:
        msg = f"Unknown location, {location}"
        logger.error(msg)
        raise ValueError(msg)
    chip_file_path = save_path / f"chips/{params.directory}/{params.filename}{suffix}"

    fiducial_list = fiducials(params.chip_type.value)
    if order == "alphanumeric":
        addr_list = get_alphanumeric(params.chip_type)

    elif order == "shot":
        addr_list = get_shot_order(params.chip_type)

    with open(chip_file_path, "a") as g:
        for addr in addr_list:
            xtal_name = "_".join([params.filename, addr])
            (x, y) = get_xy(xtal_name, params.chip_type)
            if addr in fiducial_list:
                pres = "0"
            else:
                if "rand" in suffix:
                    pres = str(np.random.randint(2))
                else:
                    pres = "-1"
            line = "\t".join([xtal_name, str(x), str(y), "0.0", pres]) + "\n"
            g.write(line)

    logger.info("Write %s completed" % chip_file_path)


@log.log_on_entry
def check_files(
    location: str,
    suffix_list: List[str],
    param_file_path: Path | str = PARAM_FILE_PATH_FT,
    save_path: Path = HEADER_FILES_PATH,
):
    if location == "i24":
        params = read_parameter_file(param_file_path)
    else:
        msg = f"Unknown location, {location}"
        logger.error(msg)
        raise ValueError(msg)
    chip_file_path = save_path / f"chips/{params.directory}/{params.filename}"

    try:
        os.stat(chip_file_path)
    except Exception:
        os.makedirs(chip_file_path)
    for suffix in suffix_list:
        full_fid = chip_file_path.with_suffix(suffix)
        if full_fid.is_file():
            time_str = time.strftime("%Y%m%d_%H%M%S_")
            timestamp_fid = (  # noqa: F841
                full_fid.parent / f"{time_str}_{params.filename}{full_fid.suffix}"
            )
            # FIXME hack / fix. Actually move the file
            logger.info(f"File {full_fid} Already Exists")
    logger.debug("Check files done")
    return 1


@log.log_on_entry
def write_headers(
    location: str,
    suffix_list: List[str],
    param_file_path: Path = PARAM_FILE_PATH_FT,
    save_path: Path = HEADER_FILES_PATH,
):
    if location == "i24":
        params = read_parameter_file(param_file_path)
        chip_file_path = save_path / f"chips/{params.directory}/{params.filename}"

        for suffix in suffix_list:
            full_fid = chip_file_path.with_suffix(suffix)
            with open(full_fid, "w") as g:
                g.write(
                    "#23456789012345678901234567890123456789012345678901234567890123456789012345678901234567890\n#\n"
                )
                g.write(f"#&i24\tchip_name    = {params.filename}\n")
                g.write(f"#&i24\tvisit        = {params.visit}\n")
                g.write(f"#&i24\tsub_dir      = {params.directory}\n")
                g.write(f"#&i24\tn_exposures  = {params.num_exposures}\n")
                g.write(f"#&i24\tchip_type    = {params.chip_type.value}\n")
                g.write(f"#&i24\tmap_type     = {params.map_type.value}\n")
                g.write(f"#&i24\tpump_repeat  = {params.pump_repeat.value}\n")
                g.write(f"#&i24\tpumpexptime  = {params.laser_dwell_s}\n")
                g.write(f"#&i24\texptime      = {params.laser_delay_s}\n")
                g.write(f"#&i24\tdcdetdist    = {params.detector_distance_mm}\n")
                g.write(f"#&i24\tprepumpexptime  = {params.pre_pump_exposure_s}\n")
                g.write(f"#&i24\tdet_Type     = {params.detector_name}\n")
                g.write("#\n")
                g.write(
                    "#XtalAddr      XCoord  YCoord  ZCoord  Present Shot  Spare04 Spare03 Spare02 Spare01\n"
                )
    else:
        msg = "Unknown location, %s" % location
        logger.error(msg)
        raise ValueError(msg)
    logger.debug("Write headers done")


def run():
    logger.debug("Run Startup")
    check_files("i24", [".addr", ".shot"])
    logger.info("Checked Files")
    write_headers("i24", [".addr", ".shot"])
    logger.info("Written Headers")
    logger.info("Writing to Files has been disabled. Headers Only")
    # Makes a file with random crystal positions
    check_files("i24", ["rando.spec"])
    write_headers("i24", ["rando.spec"])
    logger.debug("StartUp Done")


if __name__ == "__main__":
    setup_logging()
    run()
