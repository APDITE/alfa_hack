from fastapi import APIRouter

from app.domain.application_status import (
    CLIENT_STAGE,
    TRANSITIONS,
    TURN_OWNER,
    ApplicationStatus,
    ClientStage,
)
from app.presentation.labels import STAGE_LABELS, STATUS_LABELS
from app.presentation.schemas import LifecycleMeta, StageMeta, StatusMeta

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/lifecycle", response_model=LifecycleMeta)
def lifecycle() -> LifecycleMeta:
    """Statuses, labels and transitions straight from the domain model, for the frontend."""
    return LifecycleMeta(
        statuses=[
            StatusMeta(
                status=s,
                label=STATUS_LABELS[s],
                client_stage=CLIENT_STAGE[s],
                turn_owner=TURN_OWNER[s],
                allowed_next=sorted(TRANSITIONS[s]),
            )
            for s in ApplicationStatus
        ],
        stages=[StageMeta(stage=st, label=STAGE_LABELS[st]) for st in ClientStage],
    )
