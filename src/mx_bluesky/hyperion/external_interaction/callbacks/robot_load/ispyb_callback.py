from __future__ import annotations

from typing import TYPE_CHECKING

from event_model.documents import EventDescriptor

from mx_bluesky.hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    get_proposal_and_session_from_visit_string,
)
from mx_bluesky.hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from mx_bluesky.hyperion.external_interaction.ispyb.exp_eye_store import (
    ExpeyeInteraction,
    RobotActionID,
)
from mx_bluesky.hyperion.log import ISPYB_LOGGER
from mx_bluesky.hyperion.parameters.constants import CONST

if TYPE_CHECKING:
    from event_model.documents import Event, EventDescriptor, RunStart, RunStop


class RobotLoadISPyBCallback(PlanReactiveCallback):
    def __init__(self) -> None:
        ISPYB_LOGGER.debug("Initialising ISPyB Robot Load Callback")
        super().__init__(log=ISPYB_LOGGER)
        self.run_uid: str | None = None
        self.descriptors: dict[str, EventDescriptor] = {}
        self.action_id: RobotActionID | None = None
        self.expeye = ExpeyeInteraction()

    def activity_gated_start(self, doc: RunStart):
        ISPYB_LOGGER.debug("ISPyB robot load callback received start document.")
        if doc.get("subplan_name") == CONST.PLAN.ROBOT_LOAD:
            ISPYB_LOGGER.debug(f"ISPyB robot load callback received: {doc}")
            self.run_uid = doc.get("uid")
            assert isinstance(metadata := doc.get("metadata"), dict)
            proposal, session = get_proposal_and_session_from_visit_string(
                metadata["visit"]
            )
            self.action_id = self.expeye.start_load(
                proposal,
                session,
                metadata["sample_id"],
                metadata["sample_puck"],
                metadata["sample_pin"],
            )
        return super().activity_gated_start(doc)

    def activity_gated_descriptor(self, doc: EventDescriptor) -> EventDescriptor | None:
        self.descriptors[doc["uid"]] = doc
        return super().activity_gated_descriptor(doc)

    def activity_gated_event(self, doc: Event) -> Event | None:
        event_descriptor = self.descriptors.get(doc["descriptor"])
        if (
            event_descriptor
            and event_descriptor.get("name") == CONST.DESCRIPTORS.ROBOT_LOAD
        ):
            assert (
                self.action_id is not None
            ), "ISPyB Robot load callback event called unexpectedly"
            barcode = doc["data"]["robot-barcode"]
            oav_snapshot = doc["data"]["oav_snapshot_last_saved_path"]
            webcam_snapshot = doc["data"]["webcam-last_saved_path"]
            # I03 uses webcam/oav snapshots in place of before/after snapshots
            self.expeye.update_barcode_and_snapshots(
                self.action_id, barcode, webcam_snapshot, oav_snapshot
            )

        return super().activity_gated_event(doc)

    def activity_gated_stop(self, doc: RunStop) -> RunStop | None:
        ISPYB_LOGGER.debug("ISPyB robot load callback received stop document.")
        if doc.get("run_start") == self.run_uid:
            assert (
                self.action_id is not None
            ), "ISPyB Robot load callback stop called unexpectedly"
            exit_status = (
                doc.get("exit_status") or "Exit status not available in stop document!"
            )
            reason = doc.get("reason") or "OK"
            self.expeye.end_load(self.action_id, exit_status, reason)
            self.action_id = None
        return super().activity_gated_stop(doc)
