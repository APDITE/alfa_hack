from fastapi import APIRouter, Response, status

from app import feed
from app.applications import require_client
from app.db import SessionDep
from app.schemas import FeedResponse
from app.security import CurrentUserDep

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("", response_model=FeedResponse)
def get_feed(session: SessionDep, user: CurrentUserDep) -> FeedResponse:
    """Client notifications: events of the client's applications, newest first."""
    require_client(user)
    return feed.build_feed(session, user.id)


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(session: SessionDep, user: CurrentUserDep) -> Response:
    """Mark all notifications of the client as read."""
    require_client(user)
    feed.mark_all_read(session, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
