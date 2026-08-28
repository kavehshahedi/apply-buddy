from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel

from app.db import _migrate_schema, get_session, init_db


class TestInitDb:
    def test_creates_all_tables(self, test_engine):
        SQLModel.metadata.drop_all(test_engine)
        init_db()

        inspector = inspect(test_engine)
        table_names = inspector.get_table_names()
        assert "jobs" in table_names
        assert "search_queries" in table_names
        assert "settings" in table_names

    def test_tables_have_expected_columns(self, test_engine):
        SQLModel.metadata.drop_all(test_engine)
        init_db()

        inspector = inspect(test_engine)
        jobs_columns = [c["name"] for c in inspector.get_columns("jobs")]
        assert "id" in jobs_columns
        assert "linkedin_job_id" in jobs_columns
        assert "title" in jobs_columns
        assert "company" in jobs_columns
        assert "description" in jobs_columns
        assert "status" in jobs_columns
        assert "viewed" in jobs_columns

        queries_columns = [c["name"] for c in inspector.get_columns("search_queries")]
        assert "id" in queries_columns
        assert "keywords" in queries_columns
        assert "locations" in queries_columns
        assert "time_filter" in queries_columns

        settings_columns = [c["name"] for c in inspector.get_columns("settings")]
        assert "key" in settings_columns
        assert "value" in settings_columns


class TestMigrateSchema:
    def test_adds_missing_jobs_columns(self, test_engine):
        inspector = inspect(test_engine)
        jobs_columns = [c["name"] for c in inspector.get_columns("jobs")]

        if "company_logo" in jobs_columns:
            with test_engine.connect() as conn:
                conn.execute(text("ALTER TABLE jobs DROP COLUMN company_logo"))
                conn.commit()

        if "viewed" in jobs_columns:
            with test_engine.connect() as conn:
                conn.execute(text("ALTER TABLE jobs DROP COLUMN viewed"))
                conn.commit()

        _migrate_schema()

        inspector = inspect(test_engine)
        jobs_columns = [c["name"] for c in inspector.get_columns("jobs")]
        assert "company_logo" in jobs_columns
        assert "viewed" in jobs_columns

    def test_adds_missing_search_queries_column(self, test_engine):
        inspector = inspect(test_engine)
        queries_columns = [c["name"] for c in inspector.get_columns("search_queries")]

        if "days_back" in queries_columns:
            with test_engine.connect() as conn:
                conn.execute(text("ALTER TABLE search_queries DROP COLUMN days_back"))
                conn.commit()

        _migrate_schema()

        inspector = inspect(test_engine)
        queries_columns = [c["name"] for c in inspector.get_columns("search_queries")]
        assert "days_back" in queries_columns

    def test_no_error_when_all_columns_exist(self, test_engine):
        _migrate_schema()

    def test_handles_missing_search_queries_table_gracefully(self, test_engine):
        with test_engine.connect() as conn:
            conn.execute(text("ALTER TABLE search_queries RENAME TO search_queries_backup"))
            conn.commit()

        try:
            _migrate_schema()
        finally:
            with test_engine.connect() as conn:
                conn.execute(text("ALTER TABLE search_queries_backup RENAME TO search_queries"))
                conn.commit()


class TestGetSession:
    def test_yields_a_session(self, test_engine):
        sessions = list(get_session())
        assert len(sessions) == 1
        assert isinstance(sessions[0], Session)

    def test_session_is_usable(self, test_engine):
        session = next(get_session())
        result = session.exec(text("SELECT 1")).first()
        assert result[0] == 1
