import json

from app.core.rawprep_benchmark_local_ui_language_smoke import (
    RawPrepBenchmarkLocalUiLanguageSmokeRequest,
    _UI_LANGUAGE_SURFACE_FILES,
    build_rawprep_benchmark_local_ui_language_smoke,
)


def _write_ui_surface_tree(tmp_path, *, english_surface: str | None = None) -> None:
    for relative_path in _UI_LANGUAGE_SURFACE_FILES:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(
            [
                "export const title = '현재 작업 공간';",
                "export const label = 'DreamCatcher 작업실';",
                "export const description = 'DreamISP 연결 상태를 확인합니다.';",
                "export function summary() {",
                "  return 'SingleRaw 비교 보드';",
                "}",
            ]
        )
        if english_surface is not None and relative_path == english_surface:
            text = "\n".join(
                [
                    "export const title = 'Workflow Rail';",
                    "export const description = '현재 작업 흐름을 정리합니다.';",
                ]
            )
        path.write_text(text, encoding="utf-8")


def test_local_ui_language_smoke_passes_on_korean_curated_surfaces(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_local_ui_language_smoke.repo_root", lambda: tmp_path)
    _write_ui_surface_tree(tmp_path)

    smoke = build_rawprep_benchmark_local_ui_language_smoke(
        RawPrepBenchmarkLocalUiLanguageSmokeRequest(
            output_dir="benchmarks/ui_language_pass",
            output_root="outputs",
        )
    )

    assert smoke.status == "passed"
    assert smoke.ok is True
    assert smoke.scanned_file_count == len(_UI_LANGUAGE_SURFACE_FILES)
    assert smoke.findings == []
    assert smoke.missing_files == []


def test_local_ui_language_smoke_reports_remaining_english_literals(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_local_ui_language_smoke.repo_root", lambda: tmp_path)
    _write_ui_surface_tree(tmp_path, english_surface="app/frontend/src/components/ToolRail.tsx")

    smoke = build_rawprep_benchmark_local_ui_language_smoke(
        RawPrepBenchmarkLocalUiLanguageSmokeRequest(
            output_dir="benchmarks/ui_language_fail",
            output_root="outputs",
        )
    )

    assert smoke.status == "failed"
    assert smoke.ok is False
    assert smoke.findings
    assert smoke.findings[0].file.endswith("app/frontend/src/components/ToolRail.tsx")
    assert set(smoke.findings[0].flagged_tokens) == {"Rail", "Workflow"}
    assert any("English display literals" in action for action in smoke.recommended_actions)
