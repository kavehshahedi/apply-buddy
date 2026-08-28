import app.routers.scrape as scrape_router


def test_scrape_run_returns_200(client, sample_query, mock_scraper):
    response = client.post("/scrape/run")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_scrape_run_returns_400_when_no_queries(client):
    response = client.post("/scrape/run")
    assert response.status_code == 400
    assert response.json() == {"error": "No enabled search queries"}


def test_scrape_run_returns_409_when_already_running(client, sample_query, mock_scraper):
    scrape_router._scrape_state["running"] = True
    try:
        response = client.post("/scrape/run")
        assert response.status_code == 409
        assert response.json() == {"error": "Scrape already running"}
    finally:
        scrape_router._scrape_state["running"] = False


def test_scrape_progress_returns_state(client, sample_query, mock_scraper):
    client.post("/scrape/run")
    response = client.get("/scrape/progress")
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert "total" in data
    assert "current" in data
    assert "errors" in data
    assert "message" in data
