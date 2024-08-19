from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import SupportsInt, TypeVar

from dodal.devices.aperturescatterguard import AperturePositionGDANames
from dodal.devices.detector import (
    DetectorParams,
    TriggerMode,
)
from pydantic import BaseModel, Field, root_validator
from scanspec.core import AxesPoints
from semver import Version

T = TypeVar("T")


class ParameterVersion(Version):
    @classmethod
    def _parse(cls, version):
        if isinstance(version, cls):
            return version
        return cls.parse(version)

    @classmethod
    def __get_validators__(cls):
        """Return a list of validator methods for pydantic models."""
        yield cls._parse

    @classmethod
    def __modify_schema__(cls, field_schema):
        """Inject/mutate the pydantic field schema in-place."""
        field_schema.update(examples=["1.0.2", "2.15.3-alpha", "21.3.15-beta+12345"])


class RotationAxis(str, Enum):
    OMEGA = "omega"
    PHI = "phi"
    CHI = "chi"
    KAPPA = "kappa"


class XyzAxis(str, Enum):
    X = "sam_x"
    Y = "sam_y"
    Z = "sam_z"


class IspybExperimentType(str, Enum):
    # Enum values from ispyb column data type
    SAD = "SAD"  # at or slightly above the peak
    SAD_INVERSE_BEAM = "SAD - Inverse Beam"
    OSC = "OSC"  # "native" (in the absence of a heavy atom)
    COLLECT_MULTIWEDGE = (
        "Collect - Multiwedge"  # "poorly determined" ~ EDNA complex strategy???
    )
    MAD = "MAD"
    HELICAL = "Helical"
    MULTI_POSITIONAL = "Multi-positional"
    MESH = "Mesh"
    BURN = "Burn"
    MAD_INVERSE_BEAM = "MAD - Inverse Beam"
    CHARACTERIZATION = "Characterization"
    DEHYDRATION = "Dehydration"
    TOMO = "tomo"
    EXPERIMENT = "experiment"
    EM = "EM"
    PDF = "PDF"
    PDF_BRAGG = "PDF+Bragg"
    BRAGG = "Bragg"
    SINGLE_PARTICLE = "single particle"
    SERIAL_FIXED = "Serial Fixed"
    SERIAL_JET = "Serial Jet"
    STANDARD = "Standard"  # Routine structure determination experiment
    TIME_RESOLVED = "Time Resolved"  # Investigate the change of a system over time
    DLS_ANVIL_HP = "Diamond Anvil High Pressure"  # HP sample environment pressure cell
    CUSTOM = "Custom"  # Special or non-standard data collection
    XRF_MAP = "XRF map"
    ENERGY_SCAN = "Energy scan"
    XRF_SPECTRUM = "XRF spectrum"
    XRF_MAP_XAS = "XRF map xas"
    MESH_3D = "Mesh3D"
    SCREENING = "Screening"
    STILL = "Still"
    SSX_CHIP = "SSX-Chip"
    SSX_JET = "SSX-Jet"

    # Aliases for historic hyperion experiment type mapping
    ROTATION = "SAD"
    GRIDSCAN_2D = "mesh"
    GRIDSCAN_3D = "Mesh3D"


class WithSnapshot(BaseModel):
    snapshot_directory: Path
    snapshot_omegas_deg: list[float] | None

    @property
    def take_snapshots(self) -> bool:
        return bool(self.snapshot_omegas_deg)


class DiffractionExperiment(WithSnapshot):
    """For all experiments which use beam"""

    visit: str = Field(min_length=1)
    file_name: str = Field(pattern=r"[\w]{2}[\d]+-[\d]+")
    exposure_time_s: float = Field(gt=0)
    comment: str = Field(default="")
    beamline: str = Field(pattern=r"BL\d{2}[BIJS]")
    insertion_prefix: str = Field(pattern=r"SR\d{2}[BIJS]")
    det_dist_to_beam_converter_path: str
    zocalo_environment: str
    trigger_mode: TriggerMode = Field(default=TriggerMode.FREE_RUN)
    detector_distance_mm: float | None = Field(default=None, gt=0)
    demand_energy_ev: float | None = Field(default=None, gt=0)
    run_number: int | None = Field(default=None, ge=0)
    selected_aperture: AperturePositionGDANames | None = Field(default=None)
    transmission_frac: float = Field(default=0.1)
    ispyb_experiment_type: IspybExperimentType
    storage_directory: str

    @root_validator(pre=True)
    def validate_snapshot_directory(cls, values):
        snapshot_dir = values.get(
            "snapshot_directory", Path(values["storage_directory"], "snapshots")
        )
        values["snapshot_directory"] = (
            snapshot_dir if isinstance(snapshot_dir, Path) else Path(snapshot_dir)
        )
        return values

    @property
    def num_images(self) -> int:
        return 0

    @property
    @abstractmethod
    def detector_params(self) -> DetectorParams: ...


class WithScan(BaseModel):
    """For experiments where the scan is known"""

    @property
    @abstractmethod
    def scan_points(self) -> AxesPoints: ...

    @property
    @abstractmethod
    def num_images(self) -> int: ...


class SplitScan(BaseModel):
    @property
    @abstractmethod
    def scan_indices(self) -> Sequence[SupportsInt]:
        """Should return the first index of each scan (i.e. for each nexus file)"""
        ...


class WithSample(BaseModel):
    sample_id: int
    sample_puck: int | None = None
    sample_pin: int | None = None


class WithOavCentring(BaseModel):
    oav_centring_file: str


class OptionalXyzStarts(BaseModel):
    x_start_um: float | None = None
    y_start_um: float | None = None
    z_start_um: float | None = None


class XyzStarts(BaseModel):
    x_start_um: float
    y_start_um: float
    z_start_um: float

    def _start_for_axis(self, axis: XyzAxis) -> float:
        match axis:
            case XyzAxis.X:
                return self.x_start_um
            case XyzAxis.Y:
                return self.y_start_um
            case XyzAxis.Z:
                return self.z_start_um


class OptionalGonioAngleStarts(BaseModel):
    omega_start_deg: float | None = None
    phi_start_deg: float | None = None
    chi_start_deg: float | None = None
    kappa_start_deg: float | None = None
