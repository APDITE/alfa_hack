import httpx
import pytest

from app.integrations import ExternalUnavailableError, HttpIntegrations


def make(handler: httpx.MockTransport) -> HttpIntegrations:
    return HttpIntegrations("http://mocks", "http://scoring", transport=handler)


def test_found_and_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/mock/egrul/7700000001":
            return httpx.Response(200, json={"inn": "7700000001", "status": "active"})
        return httpx.Response(404)

    client = make(httpx.MockTransport(handler))
    assert client.egrul("7700000001") == {"inn": "7700000001", "status": "active"}
    assert client.transparent_business("7700000001") is None
    assert client.bki("7700000001") is None


def test_503_means_unavailable() -> None:
    client = make(httpx.MockTransport(lambda request: httpx.Response(503)))
    with pytest.raises(ExternalUnavailableError) as err:
        client.bki("7700000001")
    assert err.value.service == "bki"


def test_connection_error_means_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = make(httpx.MockTransport(handler))
    with pytest.raises(ExternalUnavailableError) as err:
        client.score({"application": {}})
    assert err.value.service == "scoring"


def test_score_posts_payload() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"score": 0.05, "risk_class": "low"})

    client = make(httpx.MockTransport(handler))
    assert client.score({"x": 1})["risk_class"] == "low"
    assert seen[0].method == "POST" and seen[0].url.path == "/score"
