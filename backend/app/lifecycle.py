"""The only place where an application's status changes.

Every change is validated against the state diagram, written to the history, announced
in the client's feed when it matters to them and, when the next move belongs to the
system, queued for the pipeline worker.
"""

import uuid

from sqlalchemy.orm import Session

from app.feed import record_event
from app.models import Application, JobStatus, PipelineJob, StatusHistory
from app.statuses import TURN_OWNER, Actor, ApplicationStatus, ensure_transition


def record_created(
    session: Session, application: Application, actor_user_id: uuid.UUID | None
) -> None:
    """History entry for a freshly created draft."""
    session.add(
        StatusHistory(
            application_id=application.id,
            from_status=None,
            to_status=application.status,
            actor=Actor.CLIENT,
            actor_user_id=actor_user_id,
        )
    )


def transition(
    session: Session,
    application: Application,
    target: ApplicationStatus,
    actor: Actor,
    *,
    actor_user_id: uuid.UUID | None = None,
    comment: str | None = None,
) -> None:
    """Move the application to `target` or raise a TransitionError. Does not commit."""
    current = application.status
    ensure_transition(current, target, actor)
    application.status = target
    application.waiting_external = False
    session.add(
        StatusHistory(
            application_id=application.id,
            from_status=current,
            to_status=target,
            actor=actor,
            actor_user_id=actor_user_id,
            comment=comment,
        )
    )
    record_event(session, application, target, actor)
    if TURN_OWNER[target] is Actor.SYSTEM:
        session.add(
            PipelineJob(application_id=application.id, stage=target, status=JobStatus.PENDING)
        )
