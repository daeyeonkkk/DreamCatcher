import json
import os
from pathlib import Path
import subprocess
import sys

TEST_DEPS = Path(__file__).resolve().parents[3] / "app" / "backend" / ".codex_tmp_testdeps"


def _script_path(name: str) -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "app" / "scripts" / name


def _run_script_without_pythonpath(script_name: str, out_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(TEST_DEPS) if TEST_DEPS.exists() else ""
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [
            sys.executable,
            str(_script_path(script_name)),
            "--allow-missing",
            "--out",
            str(out_path),
        ],
        cwd=str(out_path.parent),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _run_script_help_without_pythonpath(script_name: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(TEST_DEPS) if TEST_DEPS.exists() else ""
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [
            sys.executable,
            str(_script_path(script_name)),
            "--help",
        ],
        cwd=str(_script_path(script_name).parent),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_rawprep_healthcheck_script_bootstraps_import_paths(tmp_path):
    out_path = tmp_path / "rawprep_healthcheck.json"

    result = _run_script_without_pythonpath("rawprep_healthcheck.py", out_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["engine_stack"] == "dreamraw_tri_v2"
    assert "required_tools" in payload
    assert "tool_status" in payload


def test_single_raw_healthcheck_script_bootstraps_import_paths(tmp_path):
    out_path = tmp_path / "single_raw_healthcheck.json"

    result = _run_script_without_pythonpath("single_raw_healthcheck.py", out_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "preferred_backend" in payload
    assert "supports_sensor_decode" in payload


def test_runpod_bootstrap_script_extracts_embedded_smoke_bundle_without_unzip():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "runpod" / "bootstrap.sh"
    script_text = script_path.read_text(encoding="utf-8")

    assert "runpod_inputs/rawprep_runpod_smoke_sample_bundle.zip" in script_text
    assert "zipfile.ZipFile" in script_text
    assert "unzip" not in script_text


def test_runpod_smoke_helper_scripts_bootstrap_import_paths_for_help():
    for script_name in (
        "benchmark_runpod_smoke_handoff.py",
        "benchmark_runpod_smoke_stage.py",
        "benchmark_runpod_smoke_plan.py",
        "benchmark_runpod_smoke.py",
        "runpod_model_bootstrap_contract.py",
        "runpod_custom_node_contract.py",
        "runpod_bootstrap_summary.py",
        "runpod_refresh_bootstrap_evidence.py",
        "frontier_dataset_plan.py",
    ):
        result = _run_script_help_without_pythonpath(script_name)
        assert result.returncode == 0, f"{script_name}: {result.stderr}"
