import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _read_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _git_tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [REPO_ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def _write_minimal_seed_bundle(root: Path, *, placeholder_name: str | None = None) -> None:
    from app.core.seed_bundle import REQUIRED_API_WORKFLOWS, REQUIRED_EXTRA_FILES

    api_root = root / "api_workflows"
    api_root.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_API_WORKFLOWS:
        payload = {"_placeholder": True} if name == placeholder_name else {"nodes": [], "source": "test"}
        (api_root / name).write_text(json.dumps(payload), encoding="utf-8")
    for relpath in REQUIRED_EXTRA_FILES:
        target = root / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")


def test_root_readme_routes_to_single_foundation_source_of_truth():
    readme = _read_text("README.md")

    assert "이 루트 README는 안내판입니다. 작업 기준 문서가 아닙니다." in readme
    assert "작업 전: `PROJECT_FOUNDATION/README.md` 확인" in readme
    assert "작업 후: `PROJECT_FOUNDATION/README.md`와 `Product/` 갱신" in readme
    assert "매 작업마다: 검증 후 커밋" in readme
    assert "PROJECT_FOUNDATION/README.md" in readme
    assert "PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md" in readme
    assert "Product/USER_MANUAL.md" in readme
    assert "Product/BUILD_MANUAL.md" in readme


def test_foundation_keeps_direction_status_roadmap_and_handoff_rules():
    foundation = _read_text("PROJECT_FOUNDATION/README.md")

    required_sections = [
        "## 1. 제품 기준",
        "## 0. Every Task Rule",
        "## 2. 문서와 산출물 구조",
        "## 3. Fresh Pull Handoff",
        "## 4. RunPod 기준",
        "## 6. Studio UI 기준",
        "## 7. Frontier 모델 기준",
        "## 8. RAW 기준",
        "## 10. 품질 자동화와 튜닝 기준",
        "## 13. 현재 release gates",
        "## 14. 구현 현황과 로드맵",
    ]
    for section in required_sections:
        assert section in foundation

    assert "작업 시작 전 반드시 확인해야 하는 기준 문서" in foundation
    assert "작업 전: `PROJECT_FOUNDATION/README.md` 확인" in foundation
    assert "작업 후: `PROJECT_FOUNDATION/README.md`와 `Product/` 갱신" in foundation
    assert "매 작업마다: 검증 후 커밋" in foundation
    assert "하나의 일관된" in foundation
    assert "하드코딩은 기본적으로 피합니다" in foundation
    assert "동적으로 보이거나 비활성화" in foundation
    assert "텍스트박스, 버튼, 칩, 탭, 패널" in foundation
    assert "겹치거나" in foundation
    assert "깨지지 않는지" in foundation
    assert "현재 구현 | 남은 과업 | 구현 주안점" in foundation
    assert "Fresh RunPod smoke" in foundation
    assert "자동 코드 변경 금지" in foundation
    assert "Cold-start 기준" in foundation
    assert "runpod/prewarm/Dockerfile.runtime" in foundation
    assert "qwen_judge_signal_v2" in foundation
    assert "PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md" in foundation
    assert "aggressive_restore" in foundation
    assert "9-frame burst/HDR" in foundation
    assert "60-150 min" in foundation


def test_product_deliverables_are_the_only_user_facing_manual_set():
    product_readme = _read_text("Product/README.md")
    build_manual = _read_text("Product/BUILD_MANUAL.md")
    runpod_checklist = _read_text("PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md")

    assert "개발 판단 기준은 `PROJECT_FOUNDATION/README.md` 하나만 봅니다." in product_readme
    assert "작업 전에는 `PROJECT_FOUNDATION/README.md`를 확인" in product_readme
    assert "검증 후" in product_readme
    assert "커밋합니다" in product_readme
    assert "Product/DreamCatcher.zip" in product_readme
    assert "USER_MANUAL.md" in product_readme
    assert "BUILD_MANUAL.md" in product_readme
    assert "PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md" in product_readme
    assert "Cold-start" in product_readme
    assert "Cold-start 예상" in build_manual
    assert "Runtime prewarmed image" in build_manual
    assert "runpod/prewarm/Dockerfile.runtime" in runpod_checklist
    assert "qwen_judge_signal_v2" in runpod_checklist
    assert "aggressive_restore" in runpod_checklist
    assert "60-150 min" in build_manual

    for path in [
        "Product/README.md",
        "Product/USER_MANUAL.md",
        "Product/BUILD_MANUAL.md",
        "PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md",
    ]:
        assert (REPO_ROOT / path).is_file()


def test_release_manifest_uses_foundation_and_product_documents_only():
    manifest = json.loads(_read_text("runpod/release_bundle_manifest.json"))
    required_paths = set(manifest["required_paths"])
    include_roots = set(manifest["include_roots"])

    assert "PROJECT_FOUNDATION/README.md" in required_paths
    assert "PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md" in required_paths
    assert "Product/README.md" in required_paths
    assert "Product/USER_MANUAL.md" in required_paths
    assert "Product/BUILD_MANUAL.md" in required_paths
    assert "runpod/build_prewarmed_image.ps1" in required_paths
    assert "runpod/prewarm/Dockerfile.runtime" in required_paths
    assert "seed_bundle/runtime_priors/evaluator/golden_calibration_v1.schema.json" in required_paths
    assert "seed_bundle/runtime_priors/evaluator/golden_quality_calibration.seed.json" in required_paths
    assert "seed_bundle/runtime_priors/evaluator/judge_evidence_packet_v1.schema.json" in required_paths
    assert "seed_bundle/runtime_priors/evaluator/qwen_judge_signal_v2.schema.json" in required_paths
    assert "Product" in include_roots
    assert "PROJECT_FOUNDATION" in include_roots
    assert "README.md" in include_roots
    assert "app/backend/app/api/*_demo.py" in manifest["forbidden_globs"]
    assert "app/backend/app/api/*mock*.py" in manifest["forbidden_globs"]
    assert "app/backend/app/api/*stub*.py" in manifest["forbidden_globs"]

    assert all(not path.startswith("docs" + "/") for path in required_paths)
    assert "docs" not in include_roots


def test_backend_does_not_expose_demo_or_mock_api_surface():
    from fastapi.testclient import TestClient

    from app.api.main import app

    client = TestClient(app)
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/demo/remove-bg" not in route_paths
    assert "/demo/variants" not in route_paths
    assert "/demo/error" not in route_paths
    assert client.post("/demo/remove-bg").status_code == 404
    assert client.post("/demo/variants").status_code == 404
    assert client.get("/demo/error").status_code == 404


def test_seed_bundle_placeholders_are_release_blockers(tmp_path):
    from app.core.seed_bundle import inspect_seed_bundle

    seed_root = tmp_path / "seed_bundle"
    _write_minimal_seed_bundle(seed_root, placeholder_name="qwen_precision_edit.api.json")

    status = inspect_seed_bundle(seed_root)

    assert status.ok is False
    assert status.missing_files == []
    assert status.placeholder_api_workflows == ["qwen_precision_edit.api.json"]


def test_verify_seed_bundle_fails_on_placeholder_workflow(tmp_path):
    seed_root = tmp_path / "seed_bundle"
    _write_minimal_seed_bundle(seed_root, placeholder_name="qwen_precision_edit.api.json")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "app" / "scripts" / "verify_seed_bundle.py"),
            "--seed-root",
            str(seed_root),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 1
    assert "placeholder api workflows: qwen_precision_edit.api.json" in result.stdout
    assert "ERROR: replace placeholder API workflows" in result.stdout


def test_generated_runtime_artifacts_are_ignored_and_not_tracked():
    gitignore = _read_text(".gitignore")
    required_ignored_roots = [
        "Product/DreamCatcher.zip",
        "app/frontend/dist/",
        "app/runtime/",
        "app/logs/",
        "app/workflows/runtime/",
        "outputs/",
    ]
    for root in required_ignored_roots:
        assert root in gitignore

    forbidden_tracked_prefixes = (
        "Product/DreamCatcher.zip",
        "app/frontend/dist/",
        "app/runtime/",
        "app/logs/",
        "app/workflows/runtime/",
        "outputs/",
    )
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in _git_tracked_files()
        if path.relative_to(REPO_ROOT).as_posix().startswith(forbidden_tracked_prefixes)
    ]

    assert offenders == []


def test_tracked_files_do_not_reference_retired_doc_paths():
    retired_references = [
        "docs" + "/",
        "CONTRIBUTING.md",
        "BENCHMARK_SPEC.md",
        "benchmark" + "/samples/README.md",
        "PROJECT_FOUNDATION" + "/DREAMCATCHER",
        "PROJECT_FOUNDATION" + "/ROADMAP",
        "PROJECT_FOUNDATION" + "/UI_",
        "PROJECT_FOUNDATION" + "/USER_FLOW",
        "PROJECT_FOUNDATION" + "/WORKING_PRINCIPLES",
    ]
    ignored_paths = {
        Path("app/backend/tests/test_project_handoff_contract.py"),
    }

    offenders: list[str] = []
    for file_path in _git_tracked_files():
        rel = file_path.relative_to(REPO_ROOT)
        if not file_path.exists():
            continue
        if rel in ignored_paths:
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for reference in retired_references:
            if reference in text:
                offenders.append(f"{rel.as_posix()}: {reference}")

    assert offenders == []
