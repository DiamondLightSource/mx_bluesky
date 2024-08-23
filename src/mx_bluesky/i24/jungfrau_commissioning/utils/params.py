import json
from typing import Any

from dodal.devices.zebra import RotationDirection
from pydantic import BaseModel, validator

DIRECTION = RotationDirection.NEGATIVE
SHUTTER_OPENING_TIME = 0.5
ACCELERATION_MARGIN = 0.1


class RotationScan(BaseModel):
    rotation_direction: RotationDirection = DIRECTION
    shutter_opening_time_s: float = SHUTTER_OPENING_TIME
    scan_width_deg: float = 360.0
    rotation_increment_deg: float = 0.1
    exposure_time_s: float = 0.001
    acquire_time_s: float = 10.0
    omega_start_deg: float = 0
    storage_directory: str = "/tmp/jungfrau_data/"
    nexus_filename: str = "scan"

    class Config:
        json_encoders = {
            RotationDirection: lambda x: x.name,
        }

    @validator("rotation_direction", pre=True)
    def _parse_direction(cls, rotation_direction: str | int):
        if isinstance(rotation_direction, str):
            return RotationDirection[rotation_direction]
        else:
            return RotationDirection(rotation_direction)

    @validator("acquire_time_s", pre=True)
    def _validate_acquision(cls, acquire_time_s: float, values: dict[str, Any]):
        if acquire_time_s < values["exposure_time_s"]:
            raise ValueError("Acquisition time must not be shorter than exposure time!")
        return acquire_time_s

    @classmethod
    def from_file(cls, filename: str):
        with open(filename) as f:
            raw = json.load(f)
        return cls(**raw)

    def print(self):
        print(self.json(indent=2))

    @property
    def num_images(self):
        return int(self.scan_width_deg / self.rotation_increment_deg)
