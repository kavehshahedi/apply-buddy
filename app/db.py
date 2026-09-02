from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings
from app.models import AutoPilotRun  # noqa: F401 — ensure table is registered in SQLModel.metadata

db_path = Path(settings.database_url.replace("sqlite:///", "")).resolve()
db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


def init_db():
    SQLModel.metadata.create_all(engine)
    _migrate_schema()


def _migrate_schema():
    from sqlalchemy import inspect, text

    inspector = inspect(engine)

    jobs_columns = [c["name"] for c in inspector.get_columns("jobs")]
    for col, col_type, default in [
        ("cover_letter_docx_path", "VARCHAR", None),
        ("cover_letter_pdf_path", "VARCHAR", None),
        ("tailored_cv_diff_pdf_path", "VARCHAR", None),
        ("company_logo", "VARCHAR", None),
        ("date_posted_dt", "VARCHAR", None),
        ("viewed", "BOOLEAN", "1"),
    ]:
        if col not in jobs_columns:
            sql = f"ALTER TABLE jobs ADD COLUMN {col} {col_type}"
            if default:
                sql += f" DEFAULT {default}"
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()

    if "autopilot_processed_at" not in jobs_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN autopilot_processed_at VARCHAR"))
            conn.commit()

    try:
        queries_columns = [c["name"] for c in inspector.get_columns("search_queries")]
        for col, col_type in [
            ("days_back", "INTEGER"),
            ("relevance", "VARCHAR"),
            ("industry", "VARCHAR"),
            ("base_salary", "VARCHAR"),
            ("job_function", "VARCHAR"),
            ("benefits", "VARCHAR"),
            ("commitments", "VARCHAR"),
            ("easy_apply", "BOOLEAN"),
            ("under_10_applicants", "BOOLEAN"),
        ]:
            if col not in queries_columns:
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE search_queries ADD COLUMN {col} {col_type}"))
                    conn.commit()
    except Exception:
        pass


def get_session():
    with Session(engine) as session:
        yield session
