from collections import deque

import pytest
from app.statuses import (
    CLIENT_STAGE,
    FINAL_STATUSES,
    TRANSITIONS,
    TURN_OWNER,
    Actor,
    ApplicationStatus,
    InvalidTransitionError,
    NotYourTurnError,
    ensure_transition,
)

S = ApplicationStatus

ALLOWED = [(src, dst) for src, targets in TRANSITIONS.items() for dst in targets]
FORBIDDEN = [(src, dst) for src in S for dst in S if dst not in TRANSITIONS[src]]


def test_every_status_is_described() -> None:
    assert set(TRANSITIONS) == set(S)
    assert set(TURN_OWNER) == set(S)
    assert set(CLIENT_STAGE) == set(S)


def test_final_statuses() -> None:
    assert FINAL_STATUSES == {S.ISSUED, S.REJECTED, S.WITHDRAWN}
    for status in FINAL_STATUSES:
        assert TURN_OWNER[status] is None


def test_every_status_is_reachable_from_draft() -> None:
    seen = {S.DRAFT}
    queue = deque([S.DRAFT])
    while queue:
        for nxt in TRANSITIONS[queue.popleft()]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    assert seen == set(S)


def test_every_non_final_status_can_reach_a_final_one() -> None:
    for start in set(S) - FINAL_STATUSES:
        seen = {start}
        queue = deque([start])
        while queue:
            for nxt in TRANSITIONS[queue.popleft()]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        assert seen & FINAL_STATUSES, start


@pytest.mark.parametrize(("src", "dst"), ALLOWED)
def test_allowed_transition_by_turn_owner(src: S, dst: S) -> None:
    owner = TURN_OWNER[src]
    assert owner is not None
    ensure_transition(src, dst, owner)


@pytest.mark.parametrize(("src", "dst"), FORBIDDEN)
def test_forbidden_transition(src: S, dst: S) -> None:
    for actor in Actor:
        with pytest.raises(InvalidTransitionError):
            ensure_transition(src, dst, actor)


@pytest.mark.parametrize(("src", "dst"), ALLOWED)
def test_only_turn_owner_can_move(src: S, dst: S) -> None:
    for actor in Actor:
        if actor is not TURN_OWNER[src]:
            with pytest.raises(NotYourTurnError):
                ensure_transition(src, dst, actor)


def test_client_answer_returns_application_to_data_check() -> None:
    ensure_transition(S.CLARIFICATION_REQUIRED, S.DATA_CHECK, Actor.CLIENT)


def test_automatic_decision_can_request_clarification() -> None:
    ensure_transition(S.CREDIT_DECISION, S.CLARIFICATION_REQUIRED, Actor.SYSTEM)


def test_client_cannot_skip_review() -> None:
    with pytest.raises(InvalidTransitionError):
        ensure_transition(S.DRAFT, S.APPROVED, Actor.CLIENT)
