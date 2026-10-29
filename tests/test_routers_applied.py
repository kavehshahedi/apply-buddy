from datetime import UTC, datetime, timedelta

from app.models import Job, JobStatus


def test_applied_board_returns_200(client, db_session):
    job_data = {
        "linkedin_job_id": "applied_1",
        "title": "Applied Engineer",
        "company": "Test Corp",
        "description": "A job",
        "date_posted_dt": datetime.now(UTC) - timedelta(days=1),
    }
    job = Job(**{**job_data, "status": JobStatus.applied})
    db_session.add(job)
    db_session.commit()

    response = client.get("/applied/")
    assert response.status_code == 200
    assert "Applied Engineer" in response.text


def test_applied_board_includes_multiple_statuses(client, db_session):
    statuses = [
        JobStatus.applied,
        JobStatus.interview,
        JobStatus.rejected,
        JobStatus.offer,
        JobStatus.accepted,
    ]
    for i, status in enumerate(statuses):
        job = Job(
            linkedin_job_id=f"job_{i}",
            title=f"Job {status.value}",
            company="Test Corp",
            description="A job",
            status=status,
        )
        db_session.add(job)
    db_session.commit()

    response = client.get("/applied/")
    assert response.status_code == 200
    for status in statuses:
        assert f"Job {status.value}" in response.text


def test_applied_board_excludes_new_and_interested(client, db_session):
    applied_job = Job(
        linkedin_job_id="applied_1",
        title="Applied Job",
        company="Test Corp",
        description="A job",
        status=JobStatus.applied,
    )
    new_job = Job(
        linkedin_job_id="new_1",
        title="New Job",
        company="Test Corp",
        description="A job",
        status=JobStatus.new,
    )
    interested_job = Job(
        linkedin_job_id="interested_1",
        title="Interested Job",
        company="Test Corp",
        description="A job",
        status=JobStatus.interested,
    )
    db_session.add_all([applied_job, new_job, interested_job])
    db_session.commit()

    response = client.get("/applied/")
    assert response.status_code == 200
    assert "Applied Job" in response.text
    assert "New Job" not in response.text
    assert "Interested Job" not in response.text


def test_build_flow_routes_each_job_to_the_right_terminal_node():
    from app.routers.applied import build_flow

    now = datetime.now(UTC)
    old, recent = now - timedelta(days=45), now - timedelta(days=3)
    cases = {
        1: (Job(status=JobStatus.applied, applied_at=recent), "applied awaiting"),
        2: (Job(status=JobStatus.applied, applied_at=old), "applied ghosted"),
        3: (Job(status=JobStatus.rejected), "applied rejected"),
        4: (
            Job(status=JobStatus.rejected, interviewed_at=old),
            "applied interview interview_rejected",
        ),
        5: (
            Job(status=JobStatus.rejected),
            "applied interview interview_rejected",
        ),  # has prep session
        6: (Job(status=JobStatus.interview), "applied interview interviewing"),
        7: (Job(status=JobStatus.offer), "applied interview offer offer_pending"),
        8: (Job(status=JobStatus.accepted), "applied interview offer accepted"),
        9: (Job(status=JobStatus.rejected, offered_at=old), "applied interview offer declined"),
    }
    jobs = []
    for job_id, (job, _) in cases.items():
        job.id = job_id
        jobs.append(job)

    flow, paths = build_flow(jobs, interviewed_ids={5}, now=now)

    assert {i: " ".join(p) for i, p in paths.items()} == {i: c[1] for i, c in cases.items()}
    assert flow["total"] == 9
    links = {(e["source"], e["target"]): e["value"] for e in flow["links"]}
    assert links[("applied", "interview")] == 6
    assert links[("interview", "offer")] == 3
    assert {n["id"] for n in flow["nodes"]} >= {"ghosted", "declined", "interview_rejected"}


def test_status_change_stamps_stage_once(client, db_session):
    job = Job(linkedin_job_id="stamp_1", title="T", company="C", status=JobStatus.applied)
    db_session.add(job)
    db_session.commit()

    client.post(f"/jobs/{job.id}/status", data={"status": "interview"})
    db_session.refresh(job)
    first = job.interviewed_at
    assert first is not None

    client.post("/jobs/bulk", json={"ids": [job.id], "action": "status", "status": "interview"})
    db_session.refresh(job)
    assert job.interviewed_at == first


def test_applied_board_period_and_sort(client, db_session):
    now = datetime.now(UTC)
    for title, company, days in [("Old Role", "Zeta", 60), ("Fresh Role", "Acme", 10)]:
        db_session.add(
            Job(
                linkedin_job_id=title,
                title=title,
                company=company,
                status=JobStatus.applied,
                applied_at=now - timedelta(days=days),
            )
        )
    db_session.commit()

    recent = client.get("/applied/?period=30").text
    assert "Fresh Role" in recent and "Old Role" not in recent
    assert "from the last 30 days" in recent

    by_company = client.get("/applied/?sort=company&order=asc").text
    assert by_company.index("Fresh Role") < by_company.index("Old Role")

    empty = client.get("/applied/?period=7").text
    assert "No applications in the last 7 days" in empty and "Reset Filters" in empty
