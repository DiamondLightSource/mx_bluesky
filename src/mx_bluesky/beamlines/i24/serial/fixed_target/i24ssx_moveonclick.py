"""
Move on click gui for fixed targets at I24
Robin Owen 12 Jan 2021
"""

import logging

import bluesky.plan_stubs as bps
import cv2 as cv
from bluesky.run_engine import RunEngine
from dodal.beamlines import i24
from dodal.devices.i24.pmac import PMAC
from dodal.devices.oav.oav_detector import OAV

from mx_bluesky.beamlines.i24.serial.fixed_target import (
    i24ssx_Chip_Manager_py3v1 as manager,
)
from mx_bluesky.beamlines.i24.serial.fixed_target.ft_utils import Fiducials
from mx_bluesky.beamlines.i24.serial.parameters.constants import OAV1_CAM

logger = logging.getLogger("I24ssx.moveonclick")

# Set scale.
# TODO See https://github.com/DiamondLightSource/mx_bluesky/issues/44
zoomcalibrator = 6  # 8 seems to work well for zoom 2


def _get_beam_centre(oav: OAV):
    """Extract the beam centre x/y positions from the display.configuration file.

    Args:
        oav (OAV): the OAV device.
    """
    return oav.parameters.beam_centre_i, oav.parameters.beam_centre_j


# Register clicks and move chip stages
def onMouse(event, x, y, flags, param):
    if event == cv.EVENT_LBUTTONUP:
        pmac = param[0]
        oav = param[1]
        beamX, beamY = _get_beam_centre(oav)
        logger.info(f"Clicked X and Y {x} {y}")
        xmove = -1 * (beamX - x) * zoomcalibrator
        ymove = -1 * (beamY - y) * zoomcalibrator
        logger.info(f"Moving X and Y {xmove} {ymove}")
        xmovepmacstring = "#1J:" + str(xmove)
        ymovepmacstring = "#2J:" + str(ymove)
        yield from bps.abs_set(pmac.pmac_string, xmovepmacstring, wait=True)
        yield from bps.abs_set(pmac.pmac_string, ymovepmacstring, wait=True)


def update_ui(oav, frame):
    # Get beam x and y values
    beamX, beamY = _get_beam_centre(oav)

    # Overlay text and beam centre
    cv.ellipse(
        frame, (beamX, beamY), (12, 8), 0.0, 0.0, 360, (0, 255, 255), thickness=2
    )
    # putText(frame,'text',bottomLeftCornerOfText, font, fontScale, fontColor, thickness, lineType)
    cv.putText(
        frame,
        "Key bindings",
        (20, 40),
        cv.FONT_HERSHEY_COMPLEX_SMALL,
        1,
        (0, 255, 255),
        1,
        1,
    )
    cv.putText(
        frame,
        "Q / A : go to / set as f0",
        (25, 70),
        cv.FONT_HERSHEY_COMPLEX_SMALL,
        0.8,
        (0, 255, 255),
        1,
        1,
    )
    cv.putText(
        frame,
        "W / S : go to / set as f1",
        (25, 90),
        cv.FONT_HERSHEY_COMPLEX_SMALL,
        0.8,
        (0, 255, 255),
        1,
        1,
    )
    cv.putText(
        frame,
        "E / D : go to / set as f2",
        (25, 110),
        cv.FONT_HERSHEY_COMPLEX_SMALL,
        0.8,
        (0, 255, 255),
        1,
        1,
    )
    cv.putText(
        frame,
        "I / O : in /out of focus",
        (25, 130),
        cv.FONT_HERSHEY_COMPLEX_SMALL,
        0.8,
        (0, 255, 255),
        1,
        1,
    )
    cv.putText(
        frame,
        "C : Create CS",
        (25, 150),
        cv.FONT_HERSHEY_COMPLEX_SMALL,
        0.8,
        (0, 255, 255),
        1,
        1,
    )
    cv.putText(
        frame,
        "esc : close window",
        (25, 170),
        cv.FONT_HERSHEY_COMPLEX_SMALL,
        0.8,
        (0, 255, 255),
        1,
        1,
    )
    cv.imshow("OAV1view", frame)


def start_viewer(oav: OAV, pmac: PMAC, oav1: str = OAV1_CAM):
    # Create a video caputure from OAV1
    cap = cv.VideoCapture(oav1)

    # Create window named OAV1view and set onmouse to this
    cv.namedWindow("OAV1view")
    cv.setMouseCallback("OAV1view", onMouse, param=[pmac, oav])  # type: ignore

    logger.info("Showing camera feed. Press escape to close")
    # Read captured video and store them in success and frame
    success, frame = cap.read()

    # Loop until escape key is pressed. Keyboard shortcuts here
    while success:
        success, frame = cap.read()

        update_ui(oav, frame)

        k = cv.waitKey(1)
        if k == 113:  # Q
            yield from manager.moveto(Fiducials.zero, pmac)
        if k == 119:  # W
            yield from manager.moveto(Fiducials.fid1, pmac)
        if k == 101:  # E
            yield from manager.moveto(Fiducials.fid2, pmac)
        if k == 97:  # A
            yield from bps.trigger(pmac.home, wait=True)
            print("Current position set as origin")
        if k == 115:  # S
            yield from manager.fiducial(1)
        if k == 100:  # D
            yield from manager.fiducial(2)
        if k == 99:  # C
            yield from manager.cs_maker(pmac)
        if k == 98:  # B
            yield from manager.block_check()  # doesn't work well for blockcheck as image doesn't update
        if k == 104:  # H
            yield from bps.abs_set(pmac.pmac_string, "#2J:-10", wait=True)
        if k == 110:  # N
            yield from bps.abs_set(pmac.pmac_string, "#2J:10", wait=True)
        if k == 109:  # M
            yield from bps.abs_set(pmac.pmac_string, "#1J:-10", wait=True)
        if k == 98:  # B
            yield from bps.abs_set(pmac.pmac_string, "#1J:10", wait=True)
        if k == 105:  # I
            yield from bps.abs_set(pmac.pmac_string, "#3J:-150", wait=True)
        if k == 111:  # O
            yield from bps.abs_set(pmac.pmac_string, "#3J:150", wait=True)
        if k == 117:  # U
            yield from bps.abs_set(pmac.pmac_string, "#3J:-1000", wait=True)
        if k == 112:  # P
            yield from bps.abs_set(pmac.pmac_string, "#3J:1000", wait=True)
        if k == 0x1B:  # esc
            cv.destroyWindow("OAV1view")
            print("Pressed escape. Closing window")
            break

    # Clear cameraCapture instance
    cap.release()


if __name__ == "__main__":
    RE = RunEngine()
    # Get devices out of dodal
    oav: OAV = i24.oav()
    pmac: PMAC = i24.pmac()
    RE(start_viewer(oav, pmac))
