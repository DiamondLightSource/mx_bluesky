"""
Fixed target data collection
"""

import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Dict, List

import numpy as np
from bluesky.run_engine import RunEngine
from dodal.beamlines import i24
from dodal.devices.i24.pmac import PMAC
from dodal.devices.zebra import Zebra

from mx_bluesky.I24.serial import log
from mx_bluesky.I24.serial.dcid import DCID
from mx_bluesky.I24.serial.fixed_target.ft_utils import (
    ChipType,
    MappingType,
    PumpProbeSetting,
)
from mx_bluesky.I24.serial.fixed_target.i24ssx_Chip_StartUp_py3v1 import (
    get_format,
)
from mx_bluesky.I24.serial.parameters import FixedTargetParameters, SSXType
from mx_bluesky.I24.serial.parameters.constants import (
    LITEMAP_PATH,
    PARAM_FILE_NAME,
    PARAM_FILE_PATH_FT,
)
from mx_bluesky.I24.serial.setup_beamline import caget, cagetstring, caput, pv
from mx_bluesky.I24.serial.setup_beamline import setup_beamline as sup
from mx_bluesky.I24.serial.setup_beamline.setup_zebra_plans import (
    arm_zebra,
    close_fast_shutter,
    open_fast_shutter,
    reset_zebra_when_collection_done_plan,
    setup_zebra_for_fastchip_plan,
)
from mx_bluesky.I24.serial.write_nexus import call_nexgen

logger = logging.getLogger("I24ssx.fixed_target")

usage = "%(prog)s [options]"


def setup_logging():
    # Log should now change name daily.
    logfile = time.strftime("i24fixedtarget_%d%B%y.log").lower()
    log.config(logfile)


def flush_print(text):
    sys.stdout.write(str(text))
    sys.stdout.flush()


def copy_files_to_data_location(
    dest_dir: Path | str,
    param_path: Path = PARAM_FILE_PATH_FT,
    map_file: Path = LITEMAP_PATH,
    map_type: MappingType = MappingType.Lite,
):
    if not isinstance(dest_dir, Path):
        dest_dir = Path(dest_dir)
    shutil.copy2(param_path / "parameters.txt", dest_dir / "parameters.txt")
    if map_type == MappingType.Lite:
        shutil.copy2(map_file / "currentchip.map", dest_dir / "currentchip.map")


@log.log_on_entry
def get_chip_prog_values(
    chip_type: int,
    pump_repeat: int,
    pumpexptime: float,
    pumpdelay: float,
    prepumpexptime: float,
    exptime: float = 16,
    n_exposures: int = 1,
):
    if chip_type in [ChipType.Oxford, ChipType.OxfordInner, ChipType.Minichip]:
        logger.info("This is an Oxford chip")
        # '1' = 'Oxford ' = [8, 8, 20, 20, 0.125, 3.175, 3.175]
        (
            xblocks,
            yblocks,
            x_num_steps,
            y_num_steps,
            w2w,
            b2b_horz,
            b2b_vert,
        ) = get_format(chip_type)
        x_step_size = w2w
        y_step_size = w2w
        x_block_size = ((x_num_steps - 1) * w2w) + b2b_horz
        y_block_size = ((y_num_steps - 1) * w2w) + b2b_vert

    elif chip_type == ChipType.Custom:
        # This is set by the user in the edm screen
        # The chip format might change every time and is read from PVs.
        logger.info("This is a Custom Chip")
        x_num_steps = caget(pv.me14e_gp6)
        y_num_steps = caget(pv.me14e_gp7)
        x_step_size = caget(pv.me14e_gp8)
        y_step_size = caget(pv.me14e_gp99)
        xblocks = 1
        yblocks = 1
        x_block_size = 0  # placeholder
        y_block_size = 0  # placeholder
    else:
        logger.warning(f"Unknown chip_type, chip_type = {chip_type}")

    # this is where p variables for fast laser expts will be set
    if pump_repeat in [
        PumpProbeSetting.NoPP,
        PumpProbeSetting.Short1,
        PumpProbeSetting.Short2,
    ]:
        pump_repeat_pvar = 0
    elif pump_repeat == PumpProbeSetting.Repeat1:
        pump_repeat_pvar = 1
    elif pump_repeat == PumpProbeSetting.Repeat2:
        pump_repeat_pvar = 2
    elif pump_repeat == PumpProbeSetting.Repeat3:
        pump_repeat_pvar = 3
    elif pump_repeat == PumpProbeSetting.Repeat5:
        pump_repeat_pvar = 5
    elif pump_repeat == PumpProbeSetting.Repeat10:
        pump_repeat_pvar = 10
    else:
        logger.warning(f"Unknown pump_repeat, pump_repeat = {pump_repeat}")

    logger.info(f"Pump repeat is {pump_repeat}, PVAR set to {pump_repeat_pvar}")

    if pump_repeat == PumpProbeSetting.Short2:
        pump_in_probe = 1
    else:
        pump_in_probe = 0

    logger.info(f"pump_in_probe set to {pump_in_probe}")

    chip_dict = {
        "X_NUM_STEPS": [11, x_num_steps],
        "Y_NUM_STEPS": [12, y_num_steps],
        "X_STEP_SIZE": [13, x_step_size],
        "Y_STEP_SIZE": [14, y_step_size],
        "DWELL_TIME": [15, exptime],
        "X_START": [16, 0],
        "Y_START": [17, 0],
        "Z_START": [18, 0],
        "X_NUM_BLOCKS": [20, xblocks],
        "Y_NUM_BLOCKS": [21, yblocks],
        "X_BLOCK_SIZE": [24, x_block_size],
        "Y_BLOCK_SIZE": [25, y_block_size],
        "COLTYPE": [26, 41],
        "N_EXPOSURES": [30, n_exposures],
        "PUMP_REPEAT": [32, pump_repeat_pvar],
        "LASER_DWELL": [34, pumpexptime],
        "LASERTWO_DWELL": [35, prepumpexptime],
        "LASER_DELAY": [37, pumpdelay],
        "PUMP_IN_PROBE": [38, pump_in_probe],
    }

    chip_dict["DWELL_TIME"][1] = 1000 * float(exptime)
    chip_dict["LASER_DWELL"][1] = 1000 * float(pumpexptime)
    chip_dict["LASERTWO_DWELL"][1] = 1000 * float(prepumpexptime)
    chip_dict["LASER_DELAY"][1] = 1000 * float(pumpdelay)

    return chip_dict


@log.log_on_entry
def load_motion_program_data(
    pmac: PMAC, motion_program_dict: Dict[str, List], map_type: int, pump_repeat: int
):
    logger.info("Loading motion program data for chip.")
    logger.info(f"Pump_repeat is {PumpProbeSetting(pump_repeat)}")
    if pump_repeat == PumpProbeSetting.NoPP:
        if map_type == MappingType.NoMap:
            prefix = 11
            logger.info(f"Map type is None, setting program prefix to {prefix}")
        elif map_type == MappingType.Lite:
            prefix = 12
        elif map_type == MappingType.Full:
            prefix = 13
        else:
            logger.warning(f"Unknown Map Type, map_type = {map_type}")
            return
    elif pump_repeat in [pp.value for pp in PumpProbeSetting if pp != 0]:
        # Pump setting chosen
        prefix = 14
        logger.info(f"Setting program prefix to {prefix}")
        pmac.pmac_string.set("P1439=0").wait()
        if bool(caget(pv.me14e_gp111)) is True:
            logger.info("Checker pattern setting enabled.")
            pmac.pmac_string.set("P1439=1").wait()
    else:
        logger.warning(f"Unknown Pump repeat, pump_repeat = {pump_repeat}")
        return

    logger.info("Set PMAC_STRING pv.")
    for key in sorted(motion_program_dict.keys()):
        v = motion_program_dict[key]
        pvar_base = prefix * 100
        pvar = pvar_base + v[0]
        value = str(v[1])
        s = f"P{pvar}={value}"
        logger.info("%s \t %s" % (key, s))
        pmac.pmac_string.set(s).wait()
        sleep(0.02)
    sleep(0.2)


@log.log_on_entry
def get_prog_num(
    chip_type: ChipType, map_type: MappingType, pump_repeat: PumpProbeSetting
):
    logger.info("Get Program Number")
    if pump_repeat == PumpProbeSetting.NoPP:
        if chip_type in [ChipType.Oxford, ChipType.OxfordInner]:
            logger.info(
                f"Pump_repeat: {str(pump_repeat)} \tOxford Chip: {str(chip_type)}"
            )
            if map_type == MappingType.NoMap:
                logger.info("Map type 0 = None")
                logger.info("Program number: 11")
                return 11
            elif map_type == MappingType.Lite:
                logger.info("Map type 1 = Mapping Lite")
                logger.info("Program number: 12")
                return 12
            elif map_type == MappingType.Full:
                logger.info("Map type 2 = Full Mapping")
                logger.info("Program number: 13")  # once fixed return 13
                msg = "Mapping Type FULL is broken as of 11.09.17"
                logger.error(msg)
                raise ValueError(msg)
            else:
                logger.debug(f"Unknown Mapping Type; map_type = {map_type}")
                return 0
        elif chip_type == ChipType.Custom:
            logger.info(
                f"Pump_repeat: {str(pump_repeat)} \tCustom Chip: {str(chip_type)}"
            )
            logger.info("Program number: 11")
            return 11
        elif chip_type == ChipType.Minichip:
            logger.info(
                f"Pump_repeat: {str(pump_repeat)} \tMini Oxford Chip: {str(chip_type)}"
            )
            logger.info("Program number: 11")
            return 11
        else:
            logger.debug(f"Unknown chip_type, chip_tpe = {chip_type}")
            return 0
    elif pump_repeat in [
        pp.value for pp in PumpProbeSetting if pp != PumpProbeSetting.NoPP
    ]:
        logger.info(f"Pump_repeat: {str(pump_repeat)} \t Chip Type: {str(chip_type)}")
        logger.info("Map Type = Mapping Lite with Pump Probe")
        logger.info("Program number: 14")
        return 14
    else:
        logger.warning(f"Unknown pump_repeat, pump_repeat = {pump_repeat}")
        return 0


@log.log_on_entry
def datasetsizei24(n_exposures: int, chip_type: ChipType, map_type: MappingType) -> int:
    # Calculates how many images will be collected based on map type and N repeats
    logger.info("Calculate total number of images expected in data collection.")

    if map_type == MappingType.NoMap:
        if chip_type == ChipType.Custom:
            total_numb_imgs = int(int(caget(pv.me14e_gp6)) * int(caget(pv.me14e_gp7)))
            logger.info(
                f"Map type: None \tCustom chip \tNumber of images {total_numb_imgs}"
            )
        else:
            chip_format = get_format(chip_type)[:4]
            total_numb_imgs = np.prod(chip_format)
            logger.info(
                f"Map type: None \tOxford chip {str(chip_type)} \tNumber of images {total_numb_imgs}"
            )

    elif map_type == MappingType.Lite:
        logger.info(f"Using Mapping Lite on chip type {str(chip_type)}")
        chip_format = get_format(chip_type)[2:4]
        block_count = 0
        with open(LITEMAP_PATH / "currentchip.map", "r") as f:
            for line in f.readlines():
                entry = line.split()
                if entry[2] == "1":
                    block_count += 1

        logger.info(f"Block count={block_count}")
        logger.info(f"Chip format={chip_format}")

        logger.info(f"Number of exposures={n_exposures}")

        total_numb_imgs = np.prod(chip_format) * block_count * n_exposures
        logger.info(f"Calculated number of images: {total_numb_imgs}")

    elif map_type == MappingType.Full:
        logger.error("Not Set Up For Full Mapping")
        raise ValueError("The beamline is currently not set for Full Mapping.")

    else:
        logger.warning(f"Unknown Map Type, map_type = {str(map_type)}")
        raise ValueError("Unknown map type")

    logger.info("Set PV to calculated number of images.")
    caput(pv.me14e_gp10, int(total_numb_imgs))

    return int(total_numb_imgs)


@log.log_on_entry
def start_i24(zebra: Zebra, parameters: FixedTargetParameters):
    """Returns a tuple of (start_time, dcid)"""
    logger.info("Start I24 data collection.")
    start_time = datetime.now()
    logger.info("Collection start time %s" % start_time.ctime())

    logger.debug("Set up beamline")
    sup.beamline("collect")
    sup.beamline("quickshot", [parameters.detector_distance_mm])
    logger.debug("Set up beamline DONE")

    total_numb_imgs = datasetsizei24(
        parameters.num_exposures, parameters.chip_type, parameters.map_type
    )

    filepath = parameters.visit + parameters.directory
    filename = parameters.filename

    logger.debug("Acquire Region")

    num_gates = total_numb_imgs // parameters.num_exposures

    logger.info(f"Total number of images: {total_numb_imgs}")
    logger.info(f"Number of exposures: {parameters.num_exposures}")
    logger.info(f"Number of gates (=Total images/N exposures): {num_gates:.4f}")

    if parameters.detector_name == "pilatus":
        logger.info("Using Pilatus detector")
        logger.info(f"Fastchip Pilatus setup: filepath {filepath}")
        logger.info(f"Fastchip Pilatus setup: filename {filename}")
        logger.info(f"Fastchip Pilatus setup: number of images {total_numb_imgs}")
        logger.info(
            f"Fastchip Pilatus setup: exposure time {parameters.exposure_time_s}"
        )

        sup.pilatus(
            "fastchip",
            [filepath, filename, total_numb_imgs, parameters.exposure_time_s],
        )

        # DCID process depends on detector PVs being set up already
        logger.debug("Start DCID process")
        dcid = DCID(
            emit_errors=False,
            ssx_type=SSXType.FIXED,
            visit=Path(parameters.visit).name,
            image_dir=filepath,
            start_time=start_time,
            num_images=total_numb_imgs,
            exposure_time=parameters.exposure_time_s,
            detector=parameters.detector_name,
            shots_per_position=parameters.num_exposures,
            pump_exposure_time=parameters.laser_dwell_s,
            pump_delay=parameters.laser_delay_s,
            pump_status=parameters.pump_repeat.value,
        )

        logger.debug("Arm Pilatus. Arm Zebra.")
        yield from setup_zebra_for_fastchip_plan(
            zebra,
            parameters.detector_name,
            num_gates,
            parameters.num_exposures,
            parameters.exposure_time_s,
            wait=True,
        )
        caput(pv.pilat_acquire, "1")  # Arm pilatus
        yield from arm_zebra(zebra)
        caput(pv.pilat_filename, filename)
        time.sleep(1.5)

    elif parameters.detector_name == "eiger":
        logger.info("Using Eiger detector")

        logger.warning(
            """TEMPORARY HACK!
            Running a Single image pilatus data collection to create directory."""
        )
        num_imgs = 1
        sup.pilatus(
            "quickshot-internaltrig",
            [filepath, filename, num_imgs, parameters.exposure_time_s],
        )
        logger.debug("Sleep 2s waiting for pilatus to arm")
        sleep(2)
        sleep(0.5)
        caput(pv.pilat_acquire, "0")  # Disarm pilatus
        sleep(0.5)
        caput(pv.pilat_acquire, "1")  # Arm pilatus
        logger.debug("Pilatus data collection DONE")
        sup.pilatus("return to normal")
        logger.info("Pilatus back to normal. Single image pilatus data collection DONE")

        logger.info(f"Triggered Eiger setup: filepath {filepath}")
        logger.info(f"Triggered Eiger setup: filename {filename}")
        logger.info(f"Triggered Eiger setup: number of images {total_numb_imgs}")
        logger.info(
            f"Triggered Eiger setup: exposure time {parameters.exposure_time_s}"
        )

        sup.eiger(
            "triggered",
            [filepath, filename, total_numb_imgs, parameters.exposure_time_s],
        )

        # DCID process depends on detector PVs being set up already
        logger.debug("Start DCID process")
        dcid = DCID(
            emit_errors=False,
            ssx_type=SSXType.FIXED,
            visit=Path(parameters.visit).name,
            image_dir=filepath,
            start_time=start_time,
            num_images=total_numb_imgs,
            exposure_time=parameters.exposure_time_s,
            detector=parameters.detector_name,
        )

        logger.debug("Arm Zebra.")
        yield from setup_zebra_for_fastchip_plan(
            zebra,
            parameters.detector_name,
            num_gates,
            parameters.num_exposures,
            parameters.exposure_time_s,
            wait=True,
        )
        yield from arm_zebra(zebra)

        time.sleep(1.5)

    else:
        msg = f"Unknown Detector Type, det_type = {parameters.detector_name}"
        logger.error(msg)
        raise ValueError(msg)

    # Open the hutch shutter

    caput("BL24I-PS-SHTR-01:CON", "Reset")
    logger.debug("Reset, then sleep for 1s")
    sleep(1.0)
    caput("BL24I-PS-SHTR-01:CON", "Open")
    logger.debug(" Open, then sleep for 2s")
    sleep(2.0)

    return start_time.ctime(), dcid


@log.log_on_entry
def finish_i24(
    zebra: Zebra,
    parameters: FixedTargetParameters,
):
    logger.info(f"Finish I24 data collection with {parameters.detector_name} detector.")

    total_numb_imgs = datasetsizei24(
        parameters.num_exposures, parameters.chip_type, parameters.map_type
    )
    filepath = parameters.visit + parameters.directory
    filename = parameters.filename
    transmission = (float(caget(pv.pilat_filtertrasm)),)
    wavelength = float(caget(pv.dcm_lambda))

    if parameters.detector_name == "pilatus":
        logger.debug("Finish I24 Pilatus")
        filename = filename + "_" + caget(pv.pilat_filenum)
        yield from reset_zebra_when_collection_done_plan(zebra)
        sup.pilatus("return-to-normal")
        sleep(0.2)
    elif parameters.detector_name == "eiger":
        logger.debug("Finish I24 Eiger")
        yield from reset_zebra_when_collection_done_plan(zebra)
        sup.eiger("return-to-normal")
        filename = cagetstring(pv.eiger_ODfilenameRBV)

    # Detector independent moves
    logger.info("Move chip back to home position by setting PMAC_STRING pv.")
    caput(pv.me14e_pmac_str, "!x0y0z0")
    logger.info("Closing shutter")
    caput("BL24I-PS-SHTR-01:CON", "Close")

    end_time = time.ctime()
    logger.debug("Collection end time %s" % end_time)

    # Copy parameter file and eventual chip map to collection directory
    copy_files_to_data_location(Path(filepath), map_type=parameters.map_type)

    # Write a record of what was collected to the processing directory
    userlog_path = parameters.visit + "processing/" + parameters.directory + "/"
    userlog_fid = filename + "_parameters.txt"
    logger.debug("Write a user log in %s" % userlog_path)

    os.makedirs(userlog_path, exist_ok=True)

    with open(userlog_path + userlog_fid, "w") as f:
        f.write("Fixed Target Data Collection Parameters\n")
        f.write(f"Data directory \t{filepath}\n")
        f.write(f"Filename \t{filename}\n")
        f.write(f"Shots per pos \t{parameters.num_exposures}\n")
        f.write(f"Total N images \t{total_numb_imgs}\n")
        f.write(f"Exposure time \t{parameters.exposure_time_s}\n")
        f.write(f"Det distance \t{parameters.detector_distance_mm}\n")
        f.write(f"Transmission \t{transmission}\n")
        f.write(f"Wavelength \t{wavelength}\n")
        f.write(f"Detector type \t{parameters.detector_name}\n")
        f.write(f"Pump status \t{parameters.pump_repeat}\n")
        f.write(f"Pump exp time \t{parameters.laser_dwell_s}\n")
        f.write(f"Pump delay \t{parameters.laser_delay_s}\n")

    sleep(0.5)

    return end_time


def main():
    # Dodal devices
    pmac = i24.pmac()
    zebra = i24.zebra()
    # ABORT BUTTON
    logger.info("Running a chip collection on I24")
    caput(pv.me14e_gp9, 0)

    logger.info("Getting parameters from file.")
    parameters = FixedTargetParameters.from_file(PARAM_FILE_PATH_FT / PARAM_FILE_NAME)

    log_msg = f"""
            Parameters for I24 serial collection: \n
                Chip name is {parameters.filename}
                visit = {parameters.visit}
                sub_dir = {parameters.directory}
                n_exposures = {parameters.num_exposures}
                chip_type = {str(parameters.chip_type)}
                map_type = {str(parameters.map_type)}
                dcdetdist = {parameters.detector_distance_mm}
                exptime = {parameters.exposure_time_s}
                det_type = {parameters.detector_name}
                pump_repeat = {str(parameters.pump_repeat)}
                pumpexptime = {parameters.laser_dwell_s}
                pumpdelay = {parameters.laser_delay_s}
                prepumpexptime = {parameters.pre_pump_exposure_s}
        """
    logger.info(log_msg)
    logger.info("Getting Program Dictionary")

    # If alignment type is Oxford inner it is still an Oxford type chip
    if parameters.chip_type == ChipType.OxfordInner:
        logger.debug("Change chip type Oxford Inner to Oxford.")
        parameters.chip_type = ChipType.Oxford

    chip_prog_dict = get_chip_prog_values(
        parameters.chip_type.value,
        parameters.pump_repeat.value,
        parameters.laser_dwell_s,
        parameters.laser_delay_s,
        parameters.pre_pump_exposure_s,
        exptime=parameters.exposure_time_s,
        n_exposures=parameters.num_exposures,
    )
    logger.info("Loading Motion Program Data")
    load_motion_program_data(
        pmac, chip_prog_dict, parameters.map_type, parameters.pump_repeat
    )

    start_time, dcid = yield from start_i24(zebra, parameters)

    logger.info("Moving to Start")
    caput(pv.me14e_pmac_str, "!x0y0z0")
    sleep(2.0)

    prog_num = get_prog_num(
        parameters.chip_type, parameters.map_type, parameters.pump_repeat
    )

    # Now ready for data collection. Open fast shutter (zebra gate)
    logger.info("Opening fast shutter.")
    yield from open_fast_shutter(zebra)

    logger.info(f"Run PMAC with program number {prog_num}")
    logger.debug(f"pmac str = &2b{prog_num}r")
    caput(pv.me14e_pmac_str, f"&2b{prog_num}r")
    sleep(1.0)

    # Kick off the StartOfCollect script
    logger.debug("Notify DCID of the start of the collection.")
    dcid.notify_start()

    tot_num_imgs = datasetsizei24(
        parameters.num_exposures, parameters.chip_type, parameters.map_type
    )
    if parameters.detector_name == "eiger":
        logger.debug("Start nexus writing service.")
        call_nexgen(
            chip_prog_dict,
            start_time,
            parameters,
            total_numb_imgs=tot_num_imgs,
        )

    logger.info("Data Collection running")

    aborted = False
    timeout_time = time.time() + tot_num_imgs * parameters.exposure_time_s + 60

    # me14e_gp9 is the ABORT button
    if int(caget(pv.me14e_gp9)) == 0:
        i = 0
        text_list = ["|", "/", "-", "\\"]
        while True:
            line_of_text = "\r\t\t\t Waiting   " + 30 * ("%s" % text_list[i % 4])
            flush_print(line_of_text)
            sleep(0.5)
            i += 1
            if int(caget(pv.me14e_gp9)) != 0:
                aborted = True
                logger.warning("Data Collection Aborted")
                caput(pv.me14e_pmac_str, "A")
                sleep(1.0)
                caput(pv.me14e_pmac_str, "P2401=0")
                break
            elif int(caget(pv.me14e_scanstatus)) == 0:
                # As soon as me14e_scanstatus is set to 0, exit.
                # Epics checks the geobrick and updates this PV every s or so.
                # Once the collection is done, it will be set to 0.
                print(caget(pv.me14e_scanstatus))
                logger.warning("Data Collection Finished")
                break
            elif time.time() >= timeout_time:
                aborted = True
                logger.warning(
                    """
                    Something went wrong and data collection timed out. Aborting.
                    """
                )
                caput(pv.me14e_pmac_str, "A")
                sleep(1.0)
                caput(pv.me14e_pmac_str, "P2401=0")
                break
    else:
        aborted = True
        logger.warning("Data Collection ended due to GP 9 not equalling 0")

    logger.info("Closing fast shutter")
    yield from close_fast_shutter(zebra)
    sleep(2.0)

    if parameters.detector_name == "pilatus":
        logger.debug("Pilatus Acquire STOP")
        sleep(0.5)
        caput(pv.pilat_acquire, 0)
    elif parameters.detector_name == "eiger":
        logger.debug("Eiger Acquire STOP")
        sleep(0.5)
        caput(pv.eiger_acquire, 0)
        caput(pv.eiger_ODcapture, "Done")

    end_time = yield from finish_i24(zebra, parameters)
    dcid.collection_complete(end_time, aborted=aborted)
    logger.debug("Notify DCID of end of collection.")
    dcid.notify_end()

    logger.debug("Quick summary of settings")
    logger.debug(f"Chip name = {parameters.filename} sub_dir = {parameters.directory}")
    logger.debug(f"Start Time = {start_time}")
    logger.debug(f"End Time = {end_time}")


if __name__ == "__main__":
    setup_logging()
    RE = RunEngine()

    RE(main())
