import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, validator

from mx_bluesky.I24.serial.fixed_target.ft_utils import (
    ChipType,
    MappingType,
    PumpProbeSetting,
)


class SerialExperiment(BaseModel):
    """Generic parameters common to all serial experiments."""

    visit: str
    directory: str
    filename: str
    exposure_time_s: float
    detector_distance_mm: float
    detector_name: Literal["eiger", "pilatus"]

    @property
    def collection_directory(self) -> Path:
        return Path(self.visit) / self.directory


class LaserExperiment(BaseModel):
    """Laser settings for pump probe serial collections."""

    laser_dwell_s: Optional[float] = None  # pump exposure time
    laser_delay_s: Optional[float] = None  # pump delay
    pre_pump_exposure_s: Optional[float] = None  # Pre illumination, just for chip


class ExtruderParameters(SerialExperiment, LaserExperiment):
    """Extruder parameter model."""

    num_images: int
    pump_status: bool

    @classmethod
    def from_file(cls, filename: str | Path):
        with open(filename, "r") as fh:
            raw_params = json.load(fh)
        return cls(**raw_params)


class ChipDescription(BaseModel):
    """Parameters defining the chip in use for FT collection."""

    model_config = ConfigDict(use_enum_values=True)

    chip_type: ChipType
    x_num_steps: int
    y_num_steps: int
    x_step_size: float
    y_step_size: float
    x_blocks: int
    y_blocks: int
    b2b_horz: float
    b2b_vert: float

    @validator("chip_type", pre=True)
    def _parse_chip(cls, chip_type: str | int):
        if isinstance(chip_type, str):
            return ChipType[chip_type]
        else:
            return ChipType(chip_type)

    @property
    def chip_format(self) -> list[int]:
        return [self.x_blocks, self.y_blocks, self.x_num_steps, self.y_num_steps]

    @property
    def x_block_size(self) -> float:
        if self.chip_type.name == "Custom":
            return 0.0  # placeholder
        else:
            return ((self.x_num_steps - 1) * self.x_step_size) + self.b2b_horz

    @property
    def y_block_size(self) -> float:
        if self.chip_type.name == "Custom":
            return 0.0  # placeholder
        else:
            return ((self.y_num_steps - 1) * self.y_step_size) + self.b2b_vert

    @property
    def approx_chip_size(self) -> float:
        """Returns an approximation of the chip size for the move during alignment \
            of the fiducials
        """
        if self.chip_type.name == "OxfordInner":
            return 24.60
        else:
            return 25.40


class FixedTargetParameters(SerialExperiment, LaserExperiment):
    """Fixed target parameter model."""

    model_config = ConfigDict(use_enum_values=True)

    num_exposures: int
    chip: ChipDescription
    map_type: MappingType
    pump_repeat: PumpProbeSetting
    checker_pattern: bool = False

    @validator("map_type", pre=True)
    def _parse_map(cls, map_type: str | int):
        if isinstance(map_type, str):
            return MappingType[map_type]
        else:
            return MappingType(map_type)

    @validator("pump_repeat", pre=True)
    def _parse_pump(cls, pump_repeat: int):
        return PumpProbeSetting(pump_repeat)

    @classmethod
    def from_file(cls, filename: str | Path):
        with open(filename, "r") as fh:
            raw_params = json.load(fh)
        return cls(**raw_params)

    @property
    def total_num_images(self) -> int:
        # TODO complete
        return 0
