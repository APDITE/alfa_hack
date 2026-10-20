"""User-facing Russian texts for statuses and client stages."""

from app.domain.application_status import ApplicationStatus, ClientStage

S = ApplicationStatus

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
