from linkedin_jobs_scraper.config import Config

from app.models import Setting
from app.services.scraper import _inject_linkedin_cookies


def test_inject_overrides_already_imported_config(db_session):
    Config.LI_RM_COOKIE = "stale"
    db_session.add(Setting(key="li_rm_cookie", value=" 'fresh-rm' "))
    db_session.add(Setting(key="li_bcookie", value="\"v=2&abc\""))
    db_session.add(Setting(key="li_at_cookie", value="AQE-at"))
    db_session.commit()

    _inject_linkedin_cookies()

    assert Config.LI_RM_COOKIE == "fresh-rm"
    assert Config.LI_BCOOKIE == '"v=2&abc"'
    assert Config.LI_AT_COOKIE == "AQE-at"
