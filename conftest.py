"""Pytest fixtures shared across the suite. Living at the repo root, this also
puts the repo root on sys.path so `world`, `trace`, etc. import cleanly."""
from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from world.server import create_app
from world.state import InjectionSpec, RunConfig


@dataclass
class World:
    client: TestClient
    config: RunConfig
    trace_path: str


@pytest.fixture
def make_world(tmp_path):
    """Build an isolated world app + client; each call is one simulated run."""
    counter = {"n": 0}

    def _make(seed: int = 1, n_inject: int | None = None,
              injection: dict | None = None) -> World:
        counter["n"] += 1
        run_id = f"test-{counter['n']:03d}"
        trace_path = str(tmp_path / f"{run_id}.jsonl")
        config = RunConfig(
            run_id=run_id,
            seed=seed,
            system="test",
            task_id="t0",
            n_inject=n_inject,
            injection=InjectionSpec(**injection) if injection else None,
            trace_path=trace_path,
        )
        return World(client=TestClient(create_app(config)), config=config,
                     trace_path=trace_path)

    return _make


def get_token(client: TestClient, worker: str = "w1") -> str:
    response = client.post("/auth/token", headers={"X-Worker-Id": worker})
    assert response.status_code == 200
    return response.json()["token"]


def auth_headers(token: str, worker: str = "w1") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Worker-Id": worker}
