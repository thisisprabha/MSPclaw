"""SQLite-friendly schema (uses JSON text columns instead of JSONB)."""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Issue(Base):
    __tablename__ = "issues"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    client_id = Column(String, nullable=False)
    source = Column(String, nullable=False)
    raw_text = Column(Text)
    parsed_issue = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    jobs = relationship("Job", back_populates="issue", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True)
    issue_id = Column(String, ForeignKey("issues.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="pending")  # pending | running | done | failed
    playbook_id = Column(String)
    escalation_level = Column(String)
    final_answer = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    issue = relationship("Issue", back_populates="jobs")
    steps = relationship("JobStep", back_populates="job", cascade="all, delete-orphan", order_by="JobStep.step_no")


class JobStep(Base):
    __tablename__ = "job_steps"
    id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False, index=True)
    step_no = Column(Integer, nullable=False)
    tool = Column(String, nullable=False)
    args = Column(JSON)
    result = Column(JSON)
    error = Column(Text)
    ran_at = Column(DateTime, default=datetime.utcnow)
    job = relationship("Job", back_populates="steps")
