"""SQLAlchemy models — multi-tenant from day 1 (schema-level, not enforced in v1).

Replaces pcfix's SQLite memory table with a proper relational schema.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Client(Base):
    __tablename__ = "clients"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    machine_id = Column(String, unique=True, nullable=False)
    hostname = Column(String)
    os = Column(String)
    last_seen_at = Column(DateTime)


class Issue(Base):
    __tablename__ = "issues"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=False, index=True)
    source = Column(String, nullable=False)  # cli | email | api
    raw_text = Column(Text)
    parsed_issue = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True)
    issue_id = Column(String, ForeignKey("issues.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="pending")
    playbook_id = Column(String, ForeignKey("playbooks.id"))
    escalation_level = Column(String)  # L1 | L2 | L3
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


class JobStep(Base):
    __tablename__ = "job_steps"
    id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False, index=True)
    step_no = Column(Integer, nullable=False)
    tool = Column(String, nullable=False)
    args = Column(JSONB)
    result = Column(JSONB)
    approved_by = Column(String)
    ran_at = Column(DateTime)


class Playbook(Base):
    __tablename__ = "playbooks"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    slug = Column(String, nullable=False)
    yaml_blob = Column(Text, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Role(Base):
    __tablename__ = "roles"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_email = Column(String, nullable=False)
    level = Column(String, nullable=False)  # L1 | L2 | L3


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    target = Column(String)
    payload = Column(JSONB)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)
