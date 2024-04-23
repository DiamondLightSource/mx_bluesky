"""
Define a mapping between the edm screens/IOC enum inputs for the general purpose PVs and
the map/chip/pump settings.
The enum values should not be changed unless they are also modified in the drop down
menu in the edm screen, as their order should always match.
New ones may be added if needed in the future.
"""

from enum import Enum, IntEnum


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

    def get_approx_chip_size(self) -> float:
        """Returns an approximation of the chip size for the move during alignment \
            of the fiducials
        """
        if self.name == "OxfordInner":
            return 24.60
        else:
            return 25.40


class PumpProbeSetting(IntEnum):
    NoPP = 0
    Short1 = 1
    Short2 = 2
    Repeat1 = 3
    Repeat2 = 4
    Repeat3 = 5
    Repeat5 = 6
    Repeat10 = 7


class Fiducials(str, Enum):
    origin = "origin"
    zero = "zero"
    fid1 = "f1"
    fid2 = "f2"
