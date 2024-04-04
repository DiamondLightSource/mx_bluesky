from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    get_proposal_and_session_from_visit_string,
    get_visit_string_from_path,
)
from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.ispyb.exp_eye_store import (
    RobotActionID,
    end_load,
    start_load,
)
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.constants import CONST

if TYPE_CHECKING:
    from event_model.documents import EventDescriptor, RunStart, RunStop


class RobotLoadISPyBCallback(PlanReactiveCallback):
    def __init__(self) -> None:
        ISPYB_LOGGER.debug("Initialising ISPyB Robot Load Callback")
        super().__init__(log=ISPYB_LOGGER)
        self.run_uid: Optional[str] = None
        self.descriptors: Dict[str, EventDescriptor] = {}
        self.action_id: RobotActionID | None = None

    def activity_gated_start(self, doc: RunStart):
        ISPYB_LOGGER.debug("ISPyB robot load handler received start document.")
        if doc.get("subplan_name") == CONST.PLAN.ROBOT_LOAD:
            self.run_uid = doc.get("uid")
            assert isinstance(metadata := doc.get("metadata"), Dict)
            assert isinstance(
                visit := get_visit_string_from_path(metadata["visit_path"]), str
            )
            proposal, session = get_proposal_and_session_from_visit_string(visit)
            self.action_id = start_load(
                proposal,
                session,
                metadata["sample_id"],
                metadata["sample_puck"],
                metadata["sample_pin"],
            )
        return super().activity_gated_start(doc)

    def activity_gated_stop(self, doc: RunStop) -> RunStop | None:
        ISPYB_LOGGER.debug("ISPyB robot load handler received stop document.")
        if doc.get("run_start") == self.run_uid:
            assert (
                self.action_id is not None
            ), "ISPyB Robot load handler stop called unexpectedly"
            exit_status = (
                doc.get("exit_status") or "Exit status not available in stop document!"
            )
            reason = doc.get("reason") or ""
            end_load(self.action_id, exit_status, reason)
        return super().activity_gated_stop(doc)
