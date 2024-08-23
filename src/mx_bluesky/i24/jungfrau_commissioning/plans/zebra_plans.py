import bluesky.plan_stubs as bps
from dodal.devices.zebra import (
    DISCONNECT,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_SHUTTER,
    TTL_XSPRESS3,
    ArmDemand,
    EncEnum,
    I24Axes,
    RotationDirection,
    TrigSource,
    Zebra,
)

from mx_bluesky.i24.jungfrau_commissioning.utils.log import LOGGER

ZEBRA_STATUS_TIMEOUT = 30


TTL_SHUTTER = 4


def arm_zebra(zebra: Zebra):
    yield from bps.abs_set(zebra.pc.arm, ArmDemand.ARM, wait=True)
    LOGGER.info("Zebra armed.")


def disarm_zebra(zebra: Zebra):
    yield from bps.abs_set(zebra.pc.arm, ArmDemand.DISARM, wait=True)
    LOGGER.info("Zebra disarmed.")


def _gate_from_position(zebra: Zebra, group: str):
    LOGGER.info("ZEBRA SETUP: Enable PC")
    yield from bps.abs_set(zebra.pc.gate_source, TrigSource.POSITION, group=group)
    yield from bps.abs_set(zebra.pc.pulse_source, TrigSource.POSITION, group=group)


def setup_zebra_for_rotation(
    zebra: Zebra,
    axis: EncEnum = I24Axes.OMEGA,
    start_angle: float = 0,
    scan_width: float = 360,
    shutter_opening_deg: float = 2.5,
    shutter_opening_s: float = 0.04,
    direction: RotationDirection = RotationDirection.POSITIVE,
    group: str = "setup_zebra_for_rotation",
    wait: bool = True,
):
    """Set up the Zebra to collect a rotation dataset. Any plan using this is
    responsible for setting the smargon velocity appropriately so that the desired
    image width is achieved with the exposure time given here.

    Parameters:
        axis:               I03 axes enum representing which axis to use for position
                            compare. Currently always omega.
        start_angle:        Position at which the scan should begin, in degrees.
        scan_width:         Total angle through which to collect, in degrees.
        direction:          RotationDirection enum for representing the direction of
                            rotation of the axis. Used for adjusting the start angle
                            based on shutter time.
        shutter_opening_deg How many degrees of movement to delay the pulse to
                            trigger the detector after the shutter opening signal
                            has been sent, and increase the gate width by to ensure
                            rotation through the full scan.
    """

    LOGGER.info("ZEBRA SETUP: START")
    yield from bps.abs_set(zebra.pc.dir, direction.value, group=group)
    yield from _gate_from_position(zebra, group)
    # must be on for shutter trigger to be enabled
    yield from bps.abs_set(zebra.inputs.soft_in_1, 1, group=group)

    # Set gate start, adjust for shutter opening time if necessary
    LOGGER.info(f"ZEBRA SETUP: shutter_opening_deg = {shutter_opening_deg}")
    LOGGER.info(f"ZEBRA SETUP: start angle start: {start_angle}")
    LOGGER.info(f"ZEBRA SETUP: start angle adjusted, gate start set to: {start_angle}")
    yield from bps.abs_set(
        zebra.pc.gate_start,
        start_angle,
        group=group,
    )
    # adjust pulse start for shutter time
    yield from bps.abs_set(zebra.pc.pulse_start, abs(shutter_opening_s), group=group)
    # set gate width to total width
    yield from bps.abs_set(
        zebra.pc.gate_width, scan_width + abs(shutter_opening_deg), group=group
    )
    # Set gate position to be angle of interest
    yield from bps.abs_set(zebra.pc.gate_trigger, axis.value, group=group)
    # Set pulse width lower than exposure time
    yield from bps.abs_set(zebra.pc.pulse_width, 0.0005, group=group)
    # Trigger the shutter with the gate (from PC_GATE & SOFTIN1 -> OR1)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], OR1, group=group)
    # Trigger the detector with a pulse
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], PC_PULSE, group=group)
    # Don't use the fluorescence detector
    yield from bps.abs_set(zebra.output.out_pvs[TTL_XSPRESS3], DISCONNECT, group=group)
    yield from bps.abs_set(zebra.output.pulse_1.input, DISCONNECT, group=group)
    LOGGER.info(f"ZEBRA SETUP: END - {'' if wait else 'not'} waiting for completion")
    if wait:
        yield from bps.wait(group)


def set_zebra_shutter_to_manual(
    zebra: Zebra, group="set_zebra_shutter_to_manual", wait=False
):
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], PC_PULSE, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], OR1, group=group)

    if wait:
        yield from bps.wait(group)


def setup_zebra_for_darks(
    zebra: Zebra,
    axis: EncEnum = I24Axes.OMEGA,
    group: str = "setup_zebra_for_darks",
    wait: bool = False,
):
    """Set up the Zebra to collect a rotation dataset. Move omega from 0 to 1 to start
    the detector with a single pulse.
    """
    LOGGER.info("ZEBRA SETUP: START")
    yield from _gate_from_position(zebra, group)
    # must be on for triggers to be enabled
    yield from bps.abs_set(zebra.inputs.soft_in_1, 1, group=group)
    yield from bps.abs_set(zebra.pc.gate_start, 0.5, group=group)
    # set rotation direction
    yield from bps.abs_set(zebra.pc.dir, RotationDirection.POSITIVE.value, group=group)
    # set gate width to total width
    yield from bps.abs_set(zebra.pc.gate_width, 1, group=group)
    # Set gate position to be angle of interest
    yield from bps.abs_set(zebra.pc.gate_trigger, axis.value, group=group)
    # Don't trigger the shutter
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], DISCONNECT, group=group)
    # Trigger the detector with a pulse
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], PC_PULSE, group=group)
    # Don't use the fluorescence detector
    yield from bps.abs_set(zebra.output.out_pvs[TTL_XSPRESS3], DISCONNECT, group=group)
    yield from bps.abs_set(zebra.output.pulse_1.input, DISCONNECT, group=group)
    LOGGER.info(f"ZEBRA SETUP: END - {'' if wait else 'not'} waiting for completion")
    if wait:
        yield from bps.wait(group)
