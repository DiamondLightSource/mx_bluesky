"""
Define a mapping between the edm screens/IOC enum inputs for the general purpose PVs and
the map/chip/pump settings.
The enum values should not be changed unless they are also modified in the drop down
menu in the edm screen, as their order should always match.
New ones may be added if needed in the future.
"""

from enum import Enum, IntEnum
from typing import Dict, Mapping

import mx_bluesky.I24.serial.setup_beamline.pv as pv
from mx_bluesky.I24.serial.setup_beamline import caget


class MappingType(IntEnum):
    NoMap = 0
    Lite = 1
    Full = 2

    def __str__(self) -> str:
        """Returns the mapping."""
        return self.name


# FIXME See https://github.com/DiamondLightSource/mx_bluesky/issues/77
class ChipType(IntEnum):
    Oxford = 0
    OxfordInner = 1
    Custom = 2
    Minichip = 3  # Mini oxford, 1 city block only

    def __str__(self) -> str:
        """Returns the chip name."""
        return self.name


class PumpProbeSetting(IntEnum):
    NoPP = 0
    Short1 = 1
    Short2 = 2
    Repeat1 = 3
    Repeat2 = 4
    Repeat3 = 5
    Repeat5 = 6
    Repeat10 = 7
    Medium1 = 8

    def __str__(self) -> str:
        """Returns the pump-probe setting name."""
        return self.name


class Fiducials(str, Enum):
    origin = "origin"
    zero = "zero"
    fid1 = "f1"
    fid2 = "f2"


def get_chip_format(chip_type: ChipType) -> Mapping:
    """Default parameter values."""
    defaults: Dict[str, int | float] = {}
    match chip_type:
        case ChipType.Oxford:
            defaults["x_num_steps"] = defaults["y_num_steps"] = 20
            defaults["x_step_size"] = defaults["y_step_size"] = 0.125
            defaults["x_blocks"] = defaults["y_blocks"] = 8
            defaults["b2b_horz"] = defaults["b2b_vert"] = 0.800
        case ChipType.OxfordInner:
            defaults["x_num_steps"] = defaults["y_num_steps"] = 25
            defaults["x_step_size"] = defaults["y_step_size"] = 0.600
            defaults["x_blocks"] = defaults["y_blocks"] = 1
            defaults["b2b_horz"] = defaults["b2b_vert"] = 0.0
        case ChipType.Minichip:
            defaults["x_num_steps"] = defaults["y_num_steps"] = 20
            defaults["x_step_size"] = defaults["y_step_size"] = 0.125
            defaults["x_blocks"] = defaults["y_blocks"] = 1
            defaults["b2b_horz"] = defaults["b2b_vert"] = 0.0
        case ChipType.Custom:
            defaults["x_num_steps"] = int(caget(pv.me14e_gp6))
            defaults["y_num_steps"] = int(caget(pv.me14e_gp7))
            defaults["x_step_size"] = float(caget(pv.me14e_gp8))
            defaults["y_step_size"] = float(caget(pv.me14e_gp99))
            defaults["x_blocks"] = defaults["y_blocks"] = 1
            defaults["b2b_horz"] = defaults["b2b_vert"] = 0.0
    return defaults
