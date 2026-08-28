import app.routers.manual_fetch as manual_fetch_router


def test_manual_fetch_run_returns_200(client, mock_scraper_single):
    response = client.post(
        "/manual-fetch/run",
        json={"url": "https://www.linkedin.com/jobs/view/1234567890"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_manual_fetch_run_returns_400_with_invalid_url(client, mock_scraper_single):
    response = client.post(
        "/manual-fetch/run",
        json={"url": "https://example.com/not-linkedin"},
    )
    assert response.status_code == 400
    assert "Invalid LinkedIn job URL" in response.json()["error"]


def test_manual_fetch_run_returns_409_when_already_running(client, mock_scraper_single):
    manual_fetch_router._manual_state["running"] = True
    try:
        response = client.post(
            "/manual-fetch/run",
            json={"url": "https://www.linkedin.com/jobs/view/1234567890"},
        )
        assert response.status_code == 409
        assert response.json() == {"error": "Manual fetch already running"}
    finally:
        manual_fetch_router._manual_state["running"] = False


def test_manual_fetch_progress_returns_state(client):
    response = client.get("/manual-fetch/progress")
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert "total" in data
    assert "current" in data
    assert "errors" in data
    assert "message" in data
