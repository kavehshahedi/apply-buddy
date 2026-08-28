from datetime import UTC, datetime, timedelta

from app.main import _beautify_description, _timeago


class TestRootRedirect:
    def test_root_redirects_to_jobs(self, client):
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/jobs/"

    def test_root_redirect_followed(self, client):
        response = client.get("/", follow_redirects=True)
        assert response.status_code == 200


class TestTimeagoFilter:
    def test_none_returns_empty_string(self):
        assert _timeago(None) == ""

    def test_just_now_for_future(self):
        dt = datetime.now(UTC) + timedelta(seconds=10)
        assert _timeago(dt) == "just now"

    def test_seconds(self):
        dt = datetime.now(UTC) - timedelta(seconds=30)
        assert _timeago(dt) == "30s ago"

    def test_minutes(self):
        dt = datetime.now(UTC) - timedelta(minutes=5)
        assert _timeago(dt) == "5m ago"

    def test_hours(self):
        dt = datetime.now(UTC) - timedelta(hours=3)
        assert _timeago(dt) == "3h ago"

    def test_days(self):
        dt = datetime.now(UTC) - timedelta(days=4)
        assert _timeago(dt) == "4d ago"

    def test_weeks(self):
        dt = datetime.now(UTC) - timedelta(weeks=3)
        assert _timeago(dt) == "3w ago"

    def test_months(self):
        dt = datetime.now(UTC) - timedelta(days=60)
        assert _timeago(dt) == "2mo ago"

    def test_years(self):
        dt = datetime.now(UTC) - timedelta(days=400)
        assert _timeago(dt) == "1y ago"

    def test_handles_naive_datetime(self):
        dt = datetime.now(UTC) - timedelta(minutes=10)
        dt_naive = dt.replace(tzinfo=None)
        result = _timeago(dt_naive)
        assert result == "10m ago"


class TestBeautifyDescription:
    def test_empty_string(self):
        assert _beautify_description("") == ""

    def test_none_or_whitespace(self):
        assert _beautify_description("   ") == ""

    def test_single_paragraph(self):
        text = "This is a simple paragraph."
        result = _beautify_description(text)
        assert result == "<p>This is a simple paragraph.</p>"

    def test_multiple_paragraphs(self):
        text = "First paragraph.\n\nSecond paragraph."
        result = _beautify_description(text)
        assert "<p>First paragraph.</p>" in result
        assert "<p>Second paragraph.</p>" in result

    def test_section_headers(self):
        text = "Requirements\nPython experience\nQualifications\nDegree"
        result = _beautify_description(text)
        assert 'class="desc-heading"' in result
        assert "Requirements" in result
        assert "Qualifications" in result

    def test_bullet_points(self):
        text = "- First item\n- Second item\n- Third item"
        result = _beautify_description(text)
        assert "<ul>" in result
        assert "</ul>" in result
        assert "<li>First item</li>" in result
        assert "<li>Second item</li>" in result
        assert "<li>Third item</li>" in result

    def test_numbered_bullets(self):
        text = "1. First\n2. Second\n3. Third"
        result = _beautify_description(text)
        assert "<ul>" in result
        assert "<li>First</li>" in result

    def test_section_headers_and_bullets(self):
        text = "Requirements\n- Python\n- FastAPI\n\nResponsibilities\n- Code review"
        result = _beautify_description(text)
        assert 'class="desc-heading">Requirements</p>' in result
        assert 'class="desc-heading">Responsibilities</p>' in result
        assert "<li>Python</li>" in result
        assert "<li>FastAPI</li>" in result
        assert "<li>Code review</li>" in result

    def test_mixed_content(self):
        text = "Job Description\n\nWe are hiring.\n\nRequirements\n- Python\n- SQL\n\nNice to have:\n- Docker"
        result = _beautify_description(text)
        assert "<p>We are hiring.</p>" in result
        assert "<li>Python</li>" in result
        assert "<li>SQL</li>" in result
        assert "<li>Docker</li>" in result
        assert "Nice to have:" in result

    def test_long_lines_not_headers(self):
        text = "A" * 100
        result = _beautify_description(text)
        assert "desc-heading" not in result
        assert "<p>" in result

    def test_unicode_content(self):
        text = "Requirements\n- Gestion de projet\n- Équipe"
        result = _beautify_description(text)
        assert "desc-heading" in result
        assert "<li>Gestion de projet</li>" in result

    def test_section_header_by_title_case(self):
        text = "About Us\nWe are a company."
        result = _beautify_description(text)
        assert 'desc-heading">About Us</p>' in result

    def test_section_header_by_colon(self):
        text = "Key Responsibilities:\nLead the team."
        result = _beautify_description(text)
        assert 'desc-heading">Key Responsibilities:</p>' in result

    def test_what_youll_do_header(self):
        text = "What you'll do\nBuild things."
        result = _beautify_description(text)
        assert "desc-heading" in result

    def test_why_join_us_header(self):
        text = "Why join us\nGreat culture."
        result = _beautify_description(text)
        assert "desc-heading" in result

    def test_bullet_star_variant(self):
        text = "* Item one\n* Item two"
        result = _beautify_description(text)
        assert "<li>Item one</li>" in result
        assert "<li>Item two</li>" in result

    def test_bullet_unicode_variants(self):
        text = "▸ Item one\n→ Item two"
        result = _beautify_description(text)
        assert "<li>Item one</li>" in result
        assert "<li>Item two</li>" in result


class TestTemplatesRegistered:
    def test_timeago_filter_available(self, client):
        response = client.get("/jobs/")
        assert response.status_code == 200

    def test_beautify_description_filter_available(self, client):
        response = client.get("/jobs/")
        assert response.status_code == 200
