"""MSP CLI — for MSP technicians.

Manages clients, playbooks, jobs, and audit. Talks to the MSP server's REST
API. The MSP web portal (v2) will be built on top of these same endpoints.

Usage:
    msp-cli clients list
    msp-cli clients status <client-id>
    msp-cli playbook validate <path>
    msp-cli job dispatch --client <id> --issue "outlook crashes"
    msp-cli audit tail --client <id>
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import typer
import yaml
from rich import print
from rich.table import Table

app = typer.Typer(help="MSPclaw — MSP CLI")
clients_app = typer.Typer(help="Manage connected client agents")
playbook_app = typer.Typer(help="Author and validate playbooks")
job_app = typer.Typer(help="Dispatch and inspect jobs")
audit_app = typer.Typer(help="View the audit log")
app.add_typer(clients_app, name="clients")
app.add_typer(playbook_app, name="playbook")
app.add_typer(job_app, name="job")
app.add_typer(audit_app, name="audit")


def _server_url() -> str:
    return os.environ.get("MSPCLAW_API_URL", "http://localhost:8080")


@clients_app.command("list")
def clients_list() -> None:
    """List currently connected client agents."""
    r = httpx.get(f"{_server_url()}/health", timeout=5.0)
    r.raise_for_status()
    data = r.json()
    print(f"[bold]Connected agents:[/bold] {data.get('connected_agents', 0)}")


@clients_app.command("status")
def clients_status(client_id: str) -> None:
    print(f"[yellow]TODO[/yellow] fetch status for {client_id}")


@playbook_app.command("validate")
def playbook_validate(path: Path) -> None:
    """Parse a playbook YAML and check required fields."""
    raw = yaml.safe_load(path.read_text())
    required = ["id", "match", "escalation"]
    missing = [k for k in required if k not in raw]
    if missing:
        print(f"[red]invalid:[/red] missing keys {missing}")
        raise typer.Exit(1)
    print(f"[green]ok:[/green] playbook [bold]{raw['id']}[/bold] is valid")
    table = Table(title="Escalation levels")
    table.add_column("Level")
    table.add_column("Tools")
    table.add_column("Approval")
    for lvl, body in (raw.get("escalation") or {}).items():
        table.add_row(
            lvl,
            ", ".join(body.get("tools", [])),
            "yes" if body.get("requires_human_approval") else "no",
        )
    print(table)


@job_app.command("dispatch")
def job_dispatch(
    client: str = typer.Option(..., help="Target client machine_id"),
    issue: str = typer.Option(..., help="Issue description"),
) -> None:
    payload = {
        "tenant_id": os.environ.get("MSPCLAW_TENANT_ID", "default"),
        "client_id": client,
        "subject": issue,
        "description": issue,
    }
    r = httpx.post(f"{_server_url()}/issues", json=payload, timeout=60.0)
    r.raise_for_status()
    print(r.json())


@audit_app.command("tail")
def audit_tail(client: str | None = None, limit: int = 50) -> None:
    print(f"[yellow]TODO[/yellow] tail audit log (client={client}, limit={limit})")


if __name__ == "__main__":
    app()
