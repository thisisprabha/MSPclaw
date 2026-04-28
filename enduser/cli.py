"""End-user CLI — runs on the client Mac alongside the agent.

Usage:
    mspclaw issue "my mac is slow"

POSTs to the MSP server's /issues endpoint with this machine's id,
then prints the final answer.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import typer
from dotenv import load_dotenv
from rich import print
from rich.markdown import Markdown

# Load .env from the repo root (parent of enduser/) so MSPCLAW_API_URL is picked up.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = typer.Typer(help="MSPclaw — end-user self-service")


def _machine_id() -> str:
    p = Path.home() / ".mspclaw" / "machine_id"
    if not p.exists():
        print("[red]Agent not registered yet.[/red] Start the agent first: `mspclaw start` (or `make agent`).")
        raise typer.Exit(1)
    return p.read_text().strip()


def _api_url() -> str:
    return os.environ.get("MSPCLAW_API_URL", "http://localhost:8080")


@app.command()
def issue(text: str = typer.Argument(..., help="Describe your issue in plain English")) -> None:
    payload = {
        "tenant_id": os.environ.get("MSPCLAW_TENANT_ID", "default"),
        "client_id": _machine_id(),
        "subject": text[:120],
        "description": text,
        "os": "macos",
        "source": "enduser_cli",
    }
    print("[dim]Submitting to MSP server…[/dim]")
    r = httpx.post(f"{_api_url()}/issues", json=payload, timeout=300.0)
    if r.status_code >= 400:
        print(f"[red]Error {r.status_code}:[/red] {r.text}")
        raise typer.Exit(1)
    body = r.json()
    if body.get("status") != "done":
        print(body)
        return
    print(f"\n[bold green]MSPclaw resolved issue {body['job_id']} via playbook {body['playbook']}[/bold green]\n")
    print(Markdown(body["final_answer"]))


if __name__ == "__main__":
    app()
