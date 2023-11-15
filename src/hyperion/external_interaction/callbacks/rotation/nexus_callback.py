from __future__ import annotations

from bluesky.callbacks import CallbackBase

from hyperion.external_interaction.nexus.write_nexus import NexusWriter
from hyperion.log import NEXUS_LOGGER
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


class RotationNexusFileCallback(CallbackBase):
    """Callback class to handle the creation of Nexus files based on experiment
    parameters for rotation scans

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of a RotationCallbackCollection.
    """

    def __init__(self) -> None:
        self.run_uid: str | None = None
        self.parameters: RotationInternalParameters | None = None
        self.writer: NexusWriter | None = None

    def start(self, doc: dict):
        if doc.get("subplan_name") == "rotation_scan_with_cleanup":
            self.run_uid = doc.get("uid")
            NEXUS_LOGGER.info(
                "Nexus writer recieved start document with experiment parameters."
            )
            json_params = doc.get("hyperion_internal_parameters")
            self.parameters = RotationInternalParameters.from_json(json_params)
            NEXUS_LOGGER.info("Setting up nexus file.")
            self.writer = NexusWriter(
                self.parameters,
                self.parameters.get_scan_points(),
                self.parameters.get_data_shape(),
            )
            self.writer.create_nexus_file()
