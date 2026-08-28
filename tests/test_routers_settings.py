from sqlmodel import select

from app.models import SearchQuery, Setting


def test_settings_page_returns_200(client, sample_query):
    response = client.get("/settings/")
    assert response.status_code == 200
    assert "software engineer" in response.text


def test_tool_check_returns_json(client, mock_shutil_which):
    response = client.get("/settings/tool-check")
    assert response.status_code == 200
    data = response.json()
    assert "chrome" in data
    assert "latex" in data
    assert "pandoc" in data


def test_tool_check_returns_false_when_tools_missing(client, mock_shutil_which_none):
    response = client.get("/settings/tool-check")
    assert response.status_code == 200
    data = response.json()
    assert "chrome" in data
    assert "latex" in data
    assert "pandoc" in data


def test_create_query(client, db_session):
    response = client.post(
        "/settings/queries",
        json={
            "keywords": "data scientist",
            "locations": ["Remote"],
            "time_filter": "week",
            "limit": 10,
            "enabled": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    query = db_session.get(SearchQuery, data["id"])
    assert query is not None
    assert query.keywords == "data scientist"


def test_update_query(client, db_session, sample_query):
    response = client.put(
        f"/settings/queries/{sample_query.id}",
        json={"keywords": "senior engineer", "enabled": False},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    db_session.refresh(sample_query)
    assert sample_query.keywords == "senior engineer"
    assert sample_query.enabled is False


def test_delete_query(client, db_session, sample_query):
    response = client.delete(f"/settings/queries/{sample_query.id}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert (
        db_session.exec(select(SearchQuery.id).where(SearchQuery.id == sample_query.id)).first()
        is None
    )


def test_create_setting(client, db_session):
    response = client.post(
        "/settings/setting/test_key",
        json={"value": "test_value"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    setting = db_session.get(Setting, "test_key")
    assert setting is not None
    assert setting.value == "test_value"


def test_update_setting(client, db_session, sample_setting):
    response = client.post(
        f"/settings/setting/{sample_setting.key}",
        json={"value": "updated_value"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    db_session.refresh(sample_setting)
    assert sample_setting.value == "updated_value"
