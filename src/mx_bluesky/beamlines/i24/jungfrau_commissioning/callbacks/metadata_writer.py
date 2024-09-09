from __future__ import annotations

import json
from pathlib import Path

from bluesky.callbacks import CallbackBase

from mx_bluesky.beamlines.i24.jungfrau_commissioning.utils.log import LOGGER
from mx_bluesky.beamlines.i24.jungfrau_commissioning.utils.params import (
    RotationScanParameters,
)


class JsonMetadataWriter(CallbackBase):
    """Callback class to handle the creation of metadata json files for commissioning.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        metadata_writer_callback = JsonMetadataWriter(parameters)
        RE.subscribe(metadata_writer_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    """

    descriptors: dict[str, dict] = {}
    parameters: RotationScanParameters
    wavelength: float | None = None
    flux: float | None = None
    transmission: float | None = None

    def start(self, doc: dict):
        if doc.get("subplan_name") == "rotation_scan_with_cleanup":
            LOGGER.info(
                "Nexus writer recieved start document with experiment parameters."
            )
            json_params = doc.get("rotation_scan_params")
            assert json_params is not None
            self.parameters = RotationScanParameters(**json.loads(json_params))
            self.run_start_uid = doc.get("uid")

    def descriptor(self, doc: dict):
        self.descriptors[doc["uid"]] = doc

    def event(self, doc: dict):
        LOGGER.info("Nexus handler received event document.")
        event_descriptor = self.descriptors[doc["descriptor"]]

        if event_descriptor.get("name") == "gonio xyz":
            assert self.parameters is not None
            data: dict | None = doc.get("data")
            assert data is not None
            self.parameters.x = data.get("vgonio_x")
            self.parameters.y = data.get("vgonio_yh")
            self.parameters.z = data.get("vgonio_z")
            LOGGER.info(
                f"Nexus handler received x, y, z: {self.parameters.x ,self.parameters.y ,self.parameters.z}."  # noqa
            )
        if event_descriptor.get("name") == "beam params":
            assert self.parameters is not None
            data = doc.get("data")
            assert data is not None
            self.transmission = data.get("beam_params_transmission")
            self.flux = data.get("beam_params_intensity")
            self.flux_xbpm2 = data.get("beam_params_flux_xbpm2")
            self.flux_xbpm3 = data.get("beam_params_flux_xbpm3")
            self.wavelength = data.get("beam_params_wavelength")
            LOGGER.info(
                f"Nexus handler received beam parameters, transmission: {self.transmission}, flux: {self.flux}, wavelength: {self.wavelength}."  # noqa
            )

    def stop(self, doc: dict):
        if (
            self.run_start_uid is not None
            and doc.get("run_start") == self.run_start_uid
        ):
            with open(
                Path(self.parameters.storage_directory) / "collection_info.json", "w"
            ) as f:
                f.write(
                    json.dumps(
                        {
                            "intensity": self.flux,
                            "flux_xbpm2": self.flux_xbpm2,
                            "flux_xbpm3": self.flux_xbpm3,
                            "wavelength": self.wavelength,
                            "x": self.parameters.x,
                            "y": self.parameters.y,
                            "z": self.parameters.z,
                        }
                    )
                )
