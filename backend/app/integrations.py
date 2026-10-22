"""Clients for the external services: registry, 'Transparent business', credit bureau, scoring.

The contracts are in docs/scenarios.md and the spec (section 12). The pipeline depends
only on the `Integrations` protocol, so tests and a local fallback can swap the transport.
"""

import logging
from typing import Any, Protocol

import httpx

log = logging.getLogger(__name__)

JSON = dict[str, Any]


class ExternalUnavailableError(Exception):
    """The service did not answer or answered 5xx: retry later."""

    def __init__(self, service: str, detail: str) -> None:
        super().__init__(f"{service} unavailable: {detail}")
        self.service = service


class Integrations(Protocol):
    def egrul(self, inn: str) -> JSON | None:
        """Registry record, or None if the company is not found."""

    def transparent_business(self, inn: str) -> JSON | None:
        """Financials, or None if the source has no data."""

    def bki(self, inn: str) -> JSON | None:
        """Credit history, or None if the bureau has no record."""

    def score(self, payload: JSON) -> JSON:
        """Risk assessment for the application."""


class HttpIntegrations:
    def __init__(
        self,
        mocks_url: str,
        scoring_url: str,
        timeout: float = 3.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._mocks = httpx.Client(base_url=mocks_url, timeout=timeout, transport=transport)
        self._scoring = httpx.Client(base_url=scoring_url, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._mocks.close()
        self._scoring.close()

    @staticmethod
    def _call(service: str, client: httpx.Client, method: str, url: str, **kw: Any) -> JSON | None:
        try:
            response = client.request(method, url, **kw)
        except httpx.HTTPError as exc:
            raise ExternalUnavailableError(service, type(exc).__name__) from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 500:
            raise ExternalUnavailableError(service, f"HTTP {response.status_code}")
        response.raise_for_status()
        body: JSON = response.json()
        return body

    def egrul(self, inn: str) -> JSON | None:
        return self._call("egrul", self._mocks, "GET", f"/mock/egrul/{inn}")

    def transparent_business(self, inn: str) -> JSON | None:
        return self._call(
            "transparent_business", self._mocks, "GET", f"/mock/transparent-business/{inn}"
        )

    def bki(self, inn: str) -> JSON | None:
        return self._call("bki", self._mocks, "GET", f"/mock/bki/{inn}")

    def score(self, payload: JSON) -> JSON:
        result = self._call("scoring", self._scoring, "POST", "/score", json=payload)
        if result is None:
            raise ExternalUnavailableError("scoring", "HTTP 404")
        return result
