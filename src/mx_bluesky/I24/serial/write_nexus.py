from __future__ import annotations

import os
import pathlib
import pprint
import time
from datetime import datetime
from typing import Dict, Literal, Optional

import requests

from mx_bluesky.I24.serial.fixed_target.ft_utils import ChipType, MappingType
from mx_bluesky.I24.serial.parameters import ExtruderParameters, FixedTargetParameters
from mx_bluesky.I24.serial.setup_beamline import Eiger, caget, cagetstring, pv


def call_nexgen(
    chip_prog_dict: Dict,
    start_time: datetime,
    parameters: ExtruderParameters | FixedTargetParameters,
    expt_type: Literal["fixed-target", "extruder"] = "fixed-target",
    total_numb_imgs: Optional[int] = None,
):
    det_type = parameters.detector_name
    print(f"det_type: {det_type}")

    if expt_type == "fixed-target":
        if (
            parameters.map_type == MappingType.NoMap
            or parameters.chip_type == ChipType.Custom
        ):
            # NOTE Nexgen server is still on nexgen v0.7.2 (fully working for ssx)
            # Will need to be updated, for correctness sake map needs to be None.
            currentchipmap = None
        else:
            currentchipmap = "/dls_sw/i24/scripts/fastchips/litemaps/currentchip.map"
        pump_status = bool(parameters.pump_repeat)
    elif expt_type == "extruder":
        # chip_prog_dict should be None for extruder (passed as input for now)
        total_numb_imgs = parameters.num_images
        currentchipmap = None
        pump_status = parameters.pump_status

    filename_prefix = cagetstring(pv.eiger_ODfilenameRBV)
    meta_h5 = (
        pathlib.Path(parameters.visit)
        / parameters.directory
        / f"{filename_prefix}_meta.h5"
    )
    t0 = time.time()
    max_wait = 60  # seconds
    print(f"Watching for {meta_h5}")
    while time.time() - t0 < max_wait:
        if meta_h5.exists():
            print(f"Found {meta_h5} after {time.time() - t0:.1f} seconds")
            time.sleep(5)
            break
        print(f"Waiting for {meta_h5}")
        time.sleep(1)
    if not meta_h5.exists():
        print(f"Giving up waiting for {meta_h5} after {max_wait} seconds")
        return False

    transmission = (float(caget(pv.pilat_filtertrasm)),)
    wavelength = float(caget(pv.dcm_lambda))

    if det_type == Eiger.name:
        print("nexgen here")
        print(chip_prog_dict)

        access_token = pathlib.Path("/scratch/ssx_nexgen.key").read_text().strip()
        url = "https://ssx-nexgen.diamond.ac.uk/ssx_eiger/write"
        headers = {"Authorization": f"Bearer {access_token}"}

        payload = {
            "beamline": "i24",
            "beam_center": [caget(pv.eiger_beamx), caget(pv.eiger_beamy)],
            "chipmap": currentchipmap,
            "chip_info": chip_prog_dict,
            "det_dist": parameters.detector_distance_mm,
            "exp_time": parameters.exposure_time_s,
            "expt_type": expt_type,
            "filename": filename_prefix,
            "num_imgs": int(total_numb_imgs),
            "pump_status": pump_status,
            "pump_exp": parameters.laser_dwell_s,
            "pump_delay": parameters.laser_delay_s,
            "transmission": transmission[0],
            "visitpath": os.fspath(meta_h5.parent),
            "wavelength": wavelength,
        }
        print(f"Sending POST request to {url} with payload:")
        pprint.pprint(payload)
        response = requests.post(url, headers=headers, json=payload)
        print(f"Response: {response.text} (status code: {response.status_code})")
        # the following will raise an error if the request was unsuccessful
        return response.status_code == requests.codes.ok
    return False
