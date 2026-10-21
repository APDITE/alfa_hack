from fastapi import APIRouter

from app import stubs
from app.schemas import FeedItem

router = APIRouter(tags=["feed"])


@router.get("/feed", response_model=list[FeedItem])
def get_feed() -> list[FeedItem]:
    """Client feed: application events and personalised bank news, newest first."""
    return stubs.SAMPLE_FEED
