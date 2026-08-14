import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tournament.webapp import runs as runs_module
from tournament.webapp.app import app


@pytest.fixture(autouse=True)
def isolated_results_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    monkeypatch.setattr(runs_module, "RESULTS_DIR", results_dir)
    monkeypatch.setattr(runs_module, "TRANSCRIPTS_PATH", results_dir / "llm_transcripts.jsonl")
    monkeypatch.setattr(runs_module, "RUNS", {})
    yield results_dir


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_index_serves_dashboard_html(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_standings_404_when_no_run_has_happened(client: TestClient) -> None:
    response = client.get("/api/standings")
    assert response.status_code == 404


def test_standings_returns_file_contents(client: TestClient, isolated_results_dir: Path) -> None:
    (isolated_results_dir / "standings.json").write_text(json.dumps([{"strategy": "tit_for_tat", "total_score": 10}]))

    response = client.get("/api/standings")
    assert response.status_code == 200
    assert response.json() == [{"strategy": "tit_for_tat", "total_score": 10}]


def test_matches_filters_by_model(client: TestClient, isolated_results_dir: Path) -> None:
    csv_text = (
        "strategy_a,strategy_b,rounds,score_a,score_b,model_a,model_b\n"
        "tit_for_tat,tit_for_tat,2,6,6,,\n"
        "llm_a,llm_b,2,4,4,model-x,model-y\n"
    )
    (isolated_results_dir / "matches.csv").write_text(csv_text)

    response = client.get("/api/matches", params={"model": "model-x"})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["strategy_a"] == "llm_a"


def test_create_run_returns_409_when_a_run_is_already_in_progress(client: TestClient) -> None:
    # Seed a fake in-progress run directly rather than racing a real background
    # thread, which (for a 2-round classic-only run) can finish before the
    # test's second request is even sent.
    import asyncio

    fake_run = runs_module.RunState(run_id="fake", experiment="classic_round_robin", loop=asyncio.new_event_loop())
    runs_module.RUNS["fake"] = fake_run

    response = client.post("/api/runs", json={"experiment": "classic_round_robin", "rounds": 2})
    assert response.status_code == 409


def test_create_run_with_unknown_experiment_returns_400(client: TestClient) -> None:
    response = client.post("/api/runs", json={"experiment": "not_a_real_experiment"})
    assert response.status_code == 400


def test_run_events_404_for_unknown_run_id(client: TestClient) -> None:
    response = client.get("/api/runs/does-not-exist/events")
    assert response.status_code == 404


def test_transcripts_empty_list_when_no_transcripts_file(client: TestClient) -> None:
    response = client.get("/api/transcripts")
    assert response.status_code == 200
    assert response.json() == []


def test_transcripts_full_includes_moves(client: TestClient, isolated_results_dir: Path) -> None:
    line = {
        "strategy_a": "llm_a",
        "strategy_b": "llm_b",
        "model_a": "model-x",
        "model_b": "model-y",
        "rounds": 2,
        "moves": [[0, "C", "D"], [1, "C", "C"]],
        "score_a": 3,
        "score_b": 8,
        "timestamp": 1.0,
    }
    runs_module.TRANSCRIPTS_PATH.write_text(json.dumps(line) + "\n")

    summary_only = client.get("/api/transcripts").json()
    assert "moves" not in summary_only[0]

    full = client.get("/api/transcripts", params={"full": "true"}).json()
    assert full[0]["moves"] == [[0, "C", "D"], [1, "C", "C"]]


def test_transcripts_filters_by_run_id(client: TestClient, isolated_results_dir: Path) -> None:
    lines = [
        {
            "run_id": "run-1",
            "strategy_a": "llm_a",
            "strategy_b": "llm_b",
            "model_a": "model-x",
            "model_b": "model-y",
            "rounds": 2,
            "moves": [],
            "score_a": 3,
            "score_b": 8,
            "timestamp": 1.0,
        },
        {
            "run_id": "run-2",
            "strategy_a": "llm_c",
            "strategy_b": "llm_d",
            "model_a": "model-x",
            "model_b": "model-y",
            "rounds": 2,
            "moves": [],
            "score_a": 5,
            "score_b": 5,
            "timestamp": 2.0,
        },
    ]
    runs_module.TRANSCRIPTS_PATH.write_text("\n".join(json.dumps(line) for line in lines) + "\n")

    response = client.get("/api/transcripts", params={"run_id": "run-2"})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["strategy_a"] == "llm_c"


def test_last_round_experiment_404_when_no_run_has_happened(client: TestClient) -> None:
    response = client.get("/api/last-round-experiment")
    assert response.status_code == 404


def test_last_round_experiment_returns_file_contents(client: TestClient, isolated_results_dir: Path) -> None:
    (isolated_results_dir / "last_round_experiment.json").write_text(json.dumps({"llama": {"z_score": 2.0}}))

    response = client.get("/api/last-round-experiment")
    assert response.status_code == 200
    assert response.json() == {"llama": {"z_score": 2.0}}


def test_runs_history_returns_archived_manifests(client: TestClient, isolated_results_dir: Path) -> None:
    archive_dir = isolated_results_dir / "runs" / "abc123"
    archive_dir.mkdir(parents=True)
    (archive_dir / "manifest.json").write_text(
        json.dumps({"run_id": "abc123", "experiment": "classic_round_robin", "archived_at": 100.0, "files": []})
    )

    response = client.get("/api/runs/history")
    assert response.status_code == 200
    assert response.json() == [{"run_id": "abc123", "experiment": "classic_round_robin", "archived_at": 100.0, "files": []}]


def test_spatial_response_includes_seed(client: TestClient, isolated_results_dir: Path) -> None:
    (isolated_results_dir / "spatial_summary.json").write_text(json.dumps([{"generation": 0, "counts": {}}]))

    response = client.get("/api/spatial")
    assert response.status_code == 200
    assert response.json()["seed"] == runs_module.SEED


def test_model_catalog_returns_size_lookup(client: TestClient) -> None:
    response = client.get("/api/model-catalog")
    assert response.status_code == 200
    data = response.json()
    assert data["llama-3.3-70b-versatile"] == 70.0
    assert data["claude-sonnet-5"] is None


def test_configured_models_reflects_env_vars(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")

    response = client.get("/api/configured-models")
    assert response.status_code == 200
    assert response.json() == ["qwen2.5"]


def test_create_run_passes_models_and_repeats_through(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def fake_start_run(experiment, rounds, include_classics, models, repeats):
        captured["args"] = (experiment, rounds, include_classics, models, repeats)
        run = runs_module.RunState(run_id="fake", experiment=experiment, loop=None)
        run.status = "done"
        return run

    monkeypatch.setattr("tournament.webapp.app.start_run", fake_start_run)

    response = client.post(
        "/api/runs",
        json={
            "experiment": "last_round_experiment",
            "rounds": 20,
            "models": ["llama-3.1-8b-instant"],
            "repeats": 2,
        },
    )

    assert response.status_code == 200
    assert captured["args"] == ("last_round_experiment", 20, False, ["llama-3.1-8b-instant"], 2)
