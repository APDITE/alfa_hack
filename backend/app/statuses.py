"""Application lifecycle: statuses, allowed transitions, whose turn it is and UI labels.

Single source of truth for the state diagram in the spec (section 7).
Every status change in the system must pass `ensure_transition`.
"""

from enum import StrEnum


class ApplicationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    DATA_CHECK = "data_check"
    CLARIFICATION_REQUIRED = "clarification_required"
    ENRICHMENT = "enrichment"
    SCORING = "scoring"
    CREDIT_DECISION = "credit_decision"
    MANUAL_REVIEW = "manual_review"
    APPROVED = "approved"
    COUNTER_OFFER = "counter_offer"
    REJECTED = "rejected"
    SIGNING = "signing"
    ISSUED = "issued"
    WITHDRAWN = "withdrawn"


class Actor(StrEnum):
    CLIENT = "client"
    SYSTEM = "system"
    EMPLOYEE = "employee"


class ClientStage(StrEnum):
    """Simplified stages shown to the client instead of internal statuses."""

    FILLING = "filling"
    IN_REVIEW = "in_review"
    ACTION_REQUIRED = "action_required"
    DECISION_READY = "decision_ready"
    SIGNING = "signing"
    COMPLETED = "completed"


S = ApplicationStatus

# From every automatic stage the system may hand the application to an employee
# (MANUAL_REVIEW): an external source stayed unavailable after all retries, or the
# stage kept failing with an unexpected error.
TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    S.DRAFT: frozenset({S.SUBMITTED, S.WITHDRAWN}),
    S.SUBMITTED: frozenset({S.DATA_CHECK, S.MANUAL_REVIEW}),
    S.DATA_CHECK: frozenset({S.ENRICHMENT, S.CLARIFICATION_REQUIRED, S.MANUAL_REVIEW}),
    S.CLARIFICATION_REQUIRED: frozenset({S.DATA_CHECK, S.WITHDRAWN}),
    S.ENRICHMENT: frozenset({S.SCORING, S.MANUAL_REVIEW}),
    S.SCORING: frozenset({S.CREDIT_DECISION, S.MANUAL_REVIEW}),
    S.CREDIT_DECISION: frozenset(
        {S.APPROVED, S.COUNTER_OFFER, S.REJECTED, S.CLARIFICATION_REQUIRED, S.MANUAL_REVIEW}
    ),
    S.MANUAL_REVIEW: frozenset({S.APPROVED, S.COUNTER_OFFER, S.REJECTED, S.CLARIFICATION_REQUIRED}),
    S.APPROVED: frozenset({S.SIGNING, S.WITHDRAWN}),
    S.COUNTER_OFFER: frozenset({S.SIGNING, S.WITHDRAWN}),
    S.SIGNING: frozenset({S.ISSUED, S.WITHDRAWN}),
    S.ISSUED: frozenset(),
    S.REJECTED: frozenset(),
    S.WITHDRAWN: frozenset(),
}

# Who moves the application out of each status ("Следующий ход за" in the spec).
TURN_OWNER: dict[ApplicationStatus, Actor | None] = {
    S.DRAFT: Actor.CLIENT,
    S.SUBMITTED: Actor.SYSTEM,
    S.DATA_CHECK: Actor.SYSTEM,
    S.CLARIFICATION_REQUIRED: Actor.CLIENT,
    S.ENRICHMENT: Actor.SYSTEM,
    S.SCORING: Actor.SYSTEM,
    S.CREDIT_DECISION: Actor.SYSTEM,
    S.MANUAL_REVIEW: Actor.EMPLOYEE,
    S.APPROVED: Actor.CLIENT,
    S.COUNTER_OFFER: Actor.CLIENT,
    S.SIGNING: Actor.CLIENT,
    S.ISSUED: None,
    S.REJECTED: None,
    S.WITHDRAWN: None,
}

CLIENT_STAGE: dict[ApplicationStatus, ClientStage] = {
    S.DRAFT: ClientStage.FILLING,
    S.SUBMITTED: ClientStage.IN_REVIEW,
    S.DATA_CHECK: ClientStage.IN_REVIEW,
    S.ENRICHMENT: ClientStage.IN_REVIEW,
    S.SCORING: ClientStage.IN_REVIEW,
    S.CREDIT_DECISION: ClientStage.IN_REVIEW,
    S.MANUAL_REVIEW: ClientStage.IN_REVIEW,
    S.CLARIFICATION_REQUIRED: ClientStage.ACTION_REQUIRED,
    S.APPROVED: ClientStage.DECISION_READY,
    S.COUNTER_OFFER: ClientStage.DECISION_READY,
    S.SIGNING: ClientStage.SIGNING,
    S.ISSUED: ClientStage.COMPLETED,
    S.REJECTED: ClientStage.COMPLETED,
    S.WITHDRAWN: ClientStage.COMPLETED,
}

FINAL_STATUSES: frozenset[ApplicationStatus] = frozenset(
    status for status, targets in TRANSITIONS.items() if not targets
)


class TransitionError(Exception):
    """Base class for rejected status changes."""


class InvalidTransitionError(TransitionError):
    def __init__(self, current: ApplicationStatus, target: ApplicationStatus) -> None:
        super().__init__(f"Transition {current} -> {target} is not allowed")
        self.current = current
        self.target = target


class NotYourTurnError(TransitionError):
    def __init__(self, current: ApplicationStatus, actor: Actor) -> None:
        owner = TURN_OWNER[current]
        super().__init__(f"{actor} cannot move an application in {current}; turn owner: {owner}")
        self.current = current
        self.actor = actor


def can_transition(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    return target in TRANSITIONS[current]


def ensure_transition(current: ApplicationStatus, target: ApplicationStatus, actor: Actor) -> None:
    """Raise if `actor` may not move an application from `current` to `target`."""
    if not can_transition(current, target):
        raise InvalidTransitionError(current, target)
    if TURN_OWNER[current] is not actor:
        raise NotYourTurnError(current, actor)


# --- Russian texts for the UI -------------------------------------------------

STATUS_LABELS: dict[ApplicationStatus, str] = {
    S.DRAFT: "Черновик",
    S.SUBMITTED: "Отправлена",
    S.DATA_CHECK: "Проверка данных",
    S.CLARIFICATION_REQUIRED: "Нужны уточнения",
    S.ENRICHMENT: "Обогащение данных",
    S.SCORING: "Скоринг",
    S.CREDIT_DECISION: "Кредитное решение",
    S.MANUAL_REVIEW: "Ручная проверка",
    S.APPROVED: "Одобрена",
    S.COUNTER_OFFER: "Одобрена на других условиях",
    S.REJECTED: "Отказ",
    S.SIGNING: "Подписание",
    S.ISSUED: "Выдана",
    S.WITHDRAWN: "Отозвана клиентом",
}

STAGE_LABELS: dict[ClientStage, str] = {
    ClientStage.FILLING: "Заполняете заявку",
    ClientStage.IN_REVIEW: "Проверяем заявку",
    ClientStage.ACTION_REQUIRED: "Нужно ваше действие",
    ClientStage.DECISION_READY: "Решение готово",
    ClientStage.SIGNING: "Оформление",
    ClientStage.COMPLETED: "Готово",
}

NEXT_STEPS: dict[ApplicationStatus, str] = {
    S.DRAFT: "Заполните сумму, срок и цель и отправьте заявку. Черновик сохраняется сам.",
    S.SUBMITTED: "Заявка принята. Мы проверим данные — от вас ничего не требуется.",
    S.DATA_CHECK: "Проверяем, что все данные заполнены. От вас ничего не требуется.",
    S.CLARIFICATION_REQUIRED: "Нам не хватает данных. Ответьте на вопрос ниже — "
    "после этого проверка продолжится.",
    S.ENRICHMENT: "Сверяем данные о компании с государственными реестрами и кредитной историей.",
    S.SCORING: "Оцениваем финансовое положение компании.",
    S.CREDIT_DECISION: "Готовим решение по заявке.",
    S.MANUAL_REVIEW: "Заявку смотрит кредитный специалист. Обычно это занимает до одного дня.",
    S.APPROVED: "Банк готов выдать кредит на запрошенных условиях. Примите или отклоните их.",
    S.COUNTER_OFFER: "Банк готов выдать кредит на других условиях. "
    "Посмотрите их и примите или отклоните.",
    S.REJECTED: "К сожалению, банк не может выдать кредит. Причина указана ниже.",
    S.SIGNING: "Подпишите документы, после этого деньги поступят на счёт.",
    S.ISSUED: "Кредит выдан, деньги поступили на счёт компании.",
    S.WITHDRAWN: "Заявка отозвана.",
}

WAITING_EXTERNAL_STEP = "Ждём ответ от внешней службы. Это не требует ваших действий."
