import pytest
from fastapi.testclient import TestClient

from app.main import app, urls

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_urls():
    urls.clear()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_shorten_creates_link():
    response = client.post("/shorten", json={"url": "https://example.com"})
    assert response.status_code == 200
    short_url = response.json()["short_url"]
    code = short_url.rsplit("/", 1)[-1]
    assert len(code) == 6
    assert urls[code] == "https://example.com"


def test_shorten_rejects_wrong_input():
    response = client.post("/shorten", json={"link": "https://example.com"})
    assert response.status_code == 422
    assert urls == {}


def test_redirect_known_code():
    create_response = client.post("/shorten", json={"url": "https://example.com"})
    short_url = create_response.json()["short_url"]
    code = short_url.rsplit("/", 1)[-1]

    redirect_response = client.get(f"/{code}", follow_redirects=False)

    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"] == "https://example.com"


def test_redirect_unknown_code():
    response = client.get("/abc123")
    assert response.status_code == 404
    assert response.json() == {"detail": "Code not found"}
