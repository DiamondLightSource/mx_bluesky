import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.preprocessors import subs_decorator
from dls_bluesky_core.core import MsgGenerator
from dodal.common import inject
from dodal.devices.oav.ophyd_async_oav import OAV, ZoomLevel
from dodal.devices.robot import BartRobot
from dodal.devices.smargon import Smargon
from dodal.devices.thawer import Thawer, ThawerStates

from mx_bluesky.i04.callbacks.murko_callback import MurkoCallback


def thaw_and_center(
    time_to_thaw: float,
    rotation: float = 360,
    robot: BartRobot = inject("robot"),
    thawer: Thawer = inject("thawer"),  # type: ignore
    smargon: Smargon = inject("smargon"),  # type: ignore
    oav: OAV = inject("ophyd_async_oav"),
) -> MsgGenerator:
    zoom_level = yield from bps.rd(oav.zoom_controller.level)
    zoom_percentage = yield from bps.rd(oav.zoom_controller.percentage)
    x_size = yield from bps.rd(oav.x_size)
    y_size = yield from bps.rd(oav.y_size)
    initial_omega = yield from bps.rd(smargon.omega.user_readback)
    oav.parameters.update_on_zoom(zoom_level.value, x_size, y_size)
    sample_id = yield from bps.rd(robot.sample_id)

    @subs_decorator(MurkoCallback())
    def _thaw_and_center():
        yield from bps.abs_set(oav.zoom_controller.level, ZoomLevel.ONE, wait=True)

        yield from bps.open_run(
            {
                "microns_per_x_pixel": oav.parameters.micronsPerXPixel,
                "microns_per_y_pixel": oav.parameters.micronsPerYPixel,
                "beam_centre_i": oav.parameters.beam_centre_i,
                "beam_centre_j": oav.parameters.beam_centre_j,
                "initial_omega": initial_omega,
                "zoom_percentage": zoom_percentage,
                "sample_id": sample_id,
            }
        )
        yield from bps.kickoff(oav, wait=True)
        yield from bps.monitor(smargon.omega.user_readback, name="smargon")
        yield from bps.monitor(oav.uuid, name="oav")
        yield from thaw(time_to_thaw, rotation, thawer, smargon)
        yield from bps.complete(oav)
        yield from bps.close_run()

    yield from _thaw_and_center()


def thaw(
    time_to_thaw: float,
    rotation: float = 360,
    thawer: Thawer = inject("thawer"),  # type: ignore
    smargon: Smargon = inject("smargon"),  # type: ignore
) -> MsgGenerator:
    """Rotates the sample and thaws it at the same time.

    Args:
        time_to_thaw (float): Time to thaw for, in seconds.
        rotation (float, optional): How much to rotate by whilst thawing, in degrees.
                                    Defaults to 360.
        thawer (Thawer, optional): The thawing device. Defaults to inject("thawer").
        smargon (Smargon, optional): The smargon used to rotate.
                                     Defaults to inject("smargon")
    """
    inital_velocity = yield from bps.rd(smargon.omega.velocity)
    new_velocity = abs(rotation / time_to_thaw) * 2.0

    def do_thaw():
        yield from bps.abs_set(smargon.omega.velocity, new_velocity, wait=True)
        yield from bps.abs_set(thawer.control, ThawerStates.ON, wait=True)
        yield from bps.rel_set(smargon.omega, rotation, wait=True)
        yield from bps.rel_set(smargon.omega, -rotation, wait=True)

    def cleanup():
        yield from bps.abs_set(smargon.omega.velocity, inital_velocity, wait=True)
        yield from bps.abs_set(thawer.control, ThawerStates.OFF, wait=True)

    # Always cleanup even if there is a failure
    yield from bpp.contingency_wrapper(
        do_thaw(),
        final_plan=cleanup,
    )
