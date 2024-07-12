import json
from pathlib import Path
from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, validator

from mx_bluesky.I24.serial.fixed_target.ft_utils import (
    ChipType,
    MappingType,
    PumpProbeSetting,
)
from mx_bluesky.I24.serial.setup_beamline import caget, pv


class SerialExperiment(BaseModel):
    """Generic parameters common to all serial experiments."""

    visit: Path
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


class FixedTargetParameters(SerialExperiment, LaserExperiment):
    """Fixed target parameter model."""

    model_config = ConfigDict(use_enum_values=True)

    num_exposures: int
    chip: ChipDescription
    map_type: MappingType
    pump_repeat: PumpProbeSetting
    checker_pattern: bool = False
    total_num_images: int = 0  # Calculated in the code for now

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


def get_chip_format(chip_type: ChipType) -> ChipDescription:
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
    chip_params = {"chip_type": chip_type.value, **defaults}
    return ChipDescription(**chip_params)
