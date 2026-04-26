"""CRUD helpers. Keep narrow — the brain/dispatcher should not write SQL."""
import uuid
from typing import Any

from server.storage.sqlite_schema import Issue, Job, JobStep


def _id() -> str:
    return uuid.uuid4().hex


def create_issue(session, *, tenant_id: str, client_id: str, source: str,
                 raw_text: str, parsed_issue: dict) -> str:
    issue = Issue(
        id=_id(), tenant_id=tenant_id, client_id=client_id,
        source=source, raw_text=raw_text, parsed_issue=parsed_issue,
    )
    session.add(issue)
    session.flush()
    return issue.id


def create_job(session, *, issue_id: str, playbook_id: str, level: str) -> str:
    job = Job(id=_id(), issue_id=issue_id, playbook_id=playbook_id, escalation_level=level)
    session.add(job)
    session.flush()
    return job.id


def append_step(session, *, job_id: str, step_no: int, tool: str,
                args: dict, result: Any = None, error: str | None = None) -> str:
    step = JobStep(id=_id(), job_id=job_id, step_no=step_no,
                   tool=tool, args=args, result=result, error=error)
    session.add(step)
    session.flush()
    return step.id


def get_job(session, job_id: str) -> Job | None:
    return session.get(Job, job_id)


def set_job_done(session, job_id: str, final_answer: str) -> None:
    job = session.get(Job, job_id)
    if job:
        job.status = "done"
        job.final_answer = final_answer
