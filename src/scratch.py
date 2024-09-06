from enum import IntEnum

from pydantic import BaseModel

from mx_bluesky.beamlines.i24.serial.fixed_target.ft_utils import MappingType


class MyEnum(IntEnum):
    ZERO = 0
    ONE = 1


class MyModel(BaseModel):
    my_enum: MappingType


data = {"my_enum": 1}
model = MyModel(**data)
pass
