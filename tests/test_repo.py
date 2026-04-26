import pytest
from server.storage.db import init_db, get_session
from server.storage import repo


@pytest.fixture
def session(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    init_db(db_url)
    with get_session() as s:
        yield s


def test_create_issue_and_job(session):
    issue_id = repo.create_issue(
        session,
        tenant_id="default",
        client_id="mac-1",
        source="cli",
        raw_text="my mac is slow",
        parsed_issue={"issue": "slow mac", "possibleCauses": ["x"], "resolutionSteps": ["y"]},
    )
    job_id = repo.create_job(session, issue_id=issue_id, playbook_id="macos-slow", level="L1")
    repo.append_step(session, job_id=job_id, step_no=1, tool="get_system_info", args={}, result={"cpu": 12.3})

    job = repo.get_job(session, job_id)
    assert job.status == "pending"
    assert len(job.steps) == 1
    assert job.steps[0].tool == "get_system_info"
