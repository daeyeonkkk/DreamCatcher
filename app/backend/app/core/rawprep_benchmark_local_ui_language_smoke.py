from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from .studio_paths import repo_root, resolve_output_root


_UI_LANGUAGE_SURFACE_FILES: tuple[str, ...] = (
    "app/frontend/src/AppShell.tsx",
    "app/frontend/src/components/TopBar.tsx",
    "app/frontend/src/components/ToolRail.tsx",
    "app/frontend/src/components/PropertyPanel.tsx",
    "app/frontend/src/components/StudioSessionSetupSection.tsx",
    "app/frontend/src/components/StudioFocusSection.tsx",
    "app/frontend/src/components/StudioActionRailSections.tsx",
    "app/frontend/src/components/StudioOperationsBoard.tsx",
    "app/frontend/src/components/RecentSessionsBoard.tsx",
    "app/frontend/src/components/ProviderTelemetryPanel.tsx",
    "app/frontend/src/components/FinishDeliveryDesk.tsx",
    "app/frontend/src/components/CompareGuidanceDrawer.tsx",
    "app/frontend/src/deliveryPresetLibrary.ts",
    "app/frontend/src/studioPriorLabels.ts",
)

_ALLOWED_ENGLISH_TOKENS: tuple[str, ...] = (
    "A3",
    "AI",
    "API",
    "Brown-Conrady",
    "CA",
    "CFA",
    "ComfyUI",
    "CR3",
    "DEAR",
    "DNG",
    "DreamCatcher",
    "DreamGen",
    "DreamISP",
    "DreamISP-lite",
    "DreamStudio",
    "DxO",
    "EV",
    "EXIF",
    "EXIFTool",
    "EXR",
    "HDR",
    "HEIC",
    "HQ",
    "HTTP",
    "ID",
    "ISO",
    "ISP",
    "JPG",
    "JPEG",
    "JSON",
    "KB",
    "Luminar",
    "MB",
    "MMArt",
    "PDF",
    "PNG",
    "Pod",
    "RAW",
    "RGB",
    "RunPod",
    "SingleRaw",
    "TIFF",
    "TriRaw",
    "UI",
    "UX",
    "WB",
    "ZIP",
)

_STRING_LITERAL_PATTERN = r"(?P<literal>'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`)"
_VISIBLE_LITERAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"(?P<context>label|description|title|subtitle|summary|note|placeholder|promptLabel|promptPlaceholder|group)\s*[:=]\s*{_STRING_LITERAL_PATTERN}",
        re.S,
    ),
    re.compile(
        rf"(?P<context>alt|aria-label)\s*=\s*{_STRING_LITERAL_PATTERN}",
        re.S,
    ),
    re.compile(
        rf"return\s+{_STRING_LITERAL_PATTERN}",
        re.S,
    ),
)
_ENGLISH_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9.+/-]*")
_IDENTIFIER_LIKE_PATTERN = re.compile(r"^[A-Za-z0-9_./:+?&=-]+$")


class RawPrepBenchmarkLocalUiLanguageSmokeRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"


class RawPrepBenchmarkLocalUiLanguageFinding(BaseModel):
    file: str
    line: int
    context: str
    text: str
    flagged_tokens: list[str] = Field(default_factory=list)


class RawPrepBenchmarkLocalUiLanguageSmoke(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    smoke_path: str
    status: str = "failed"
    ok: bool = False
    scanned_files: list[str] = Field(default_factory=list)
    scanned_file_count: int = 0
    scanned_literal_count: int = 0
    allowed_token_hints: list[str] = Field(default_factory=list)
    missing_files: list[str] = Field(default_factory=list)
    findings: list[RawPrepBenchmarkLocalUiLanguageFinding] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    summary: str


def _resolve_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Local UI language smoke output_dir must stay inside the configured output root.") from exc
    return resolved


def _smoke_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_output_dir(output_dir, output_root=output_root) / "rawprep_local_ui_language_smoke.json"


def _repo_relative_string(path: Path) -> str:
    resolved = path.resolve()
    root = repo_root().resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return str(resolved)


def _strip_template_expressions(value: str) -> str:
    result: list[str] = []
    index = 0
    length = len(value)
    while index < length:
        if value[index] == "$" and index + 1 < length and value[index + 1] == "{":
            index += 2
            depth = 1
            while index < length and depth > 0:
                char = value[index]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                index += 1
            continue
        result.append(value[index])
        index += 1
    return "".join(result)


def _decode_literal(literal: str) -> str:
    quote = literal[0]
    value = literal[1:-1]
    if quote == "`":
        value = _strip_template_expressions(value)
    return (
        value
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace("\\'", "'")
        .replace('\\"', '"')
        .replace("\\`", "`")
    ).strip()


def _looks_like_internal_identifier(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value).strip()
    return bool(_IDENTIFIER_LIKE_PATTERN.fullmatch(normalized))


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _is_allowed_english_token(token: str) -> bool:
    return token in _ALLOWED_ENGLISH_TOKENS


def _extract_findings(path: Path) -> tuple[list[RawPrepBenchmarkLocalUiLanguageFinding], int]:
    text = path.read_text(encoding="utf-8")
    findings: list[RawPrepBenchmarkLocalUiLanguageFinding] = []
    seen_spans: set[tuple[int, int, str]] = set()
    scanned_literal_count = 0

    for pattern in _VISIBLE_LITERAL_PATTERNS:
        for match in pattern.finditer(text):
            literal = match.group("literal")
            context = match.groupdict().get("context") or "return"
            dedupe_key = (match.start("literal"), match.end("literal"), context)
            if dedupe_key in seen_spans:
                continue
            seen_spans.add(dedupe_key)
            rendered = _decode_literal(literal)
            if not rendered:
                continue
            if _looks_like_internal_identifier(rendered):
                continue
            scanned_literal_count += 1
            english_tokens = _ENGLISH_TOKEN_PATTERN.findall(rendered)
            if not english_tokens:
                continue
            flagged_tokens = [token for token in english_tokens if not _is_allowed_english_token(token)]
            if not flagged_tokens:
                continue
            findings.append(
                RawPrepBenchmarkLocalUiLanguageFinding(
                    file=_repo_relative_string(path),
                    line=_line_number(text, match.start("literal")),
                    context=context,
                    text=rendered,
                    flagged_tokens=sorted(set(flagged_tokens)),
                )
            )

    return findings, scanned_literal_count


def build_rawprep_benchmark_local_ui_language_smoke(
    request: RawPrepBenchmarkLocalUiLanguageSmokeRequest,
) -> RawPrepBenchmarkLocalUiLanguageSmoke:
    root = repo_root().resolve()
    scanned_files: list[str] = []
    missing_files: list[str] = []
    findings: list[RawPrepBenchmarkLocalUiLanguageFinding] = []
    scanned_literal_count = 0

    for relative_path in _UI_LANGUAGE_SURFACE_FILES:
        path = (root / relative_path).resolve()
        repo_relative = _repo_relative_string(path)
        scanned_files.append(repo_relative)
        if not path.exists():
            missing_files.append(repo_relative)
            continue
        file_findings, literal_count = _extract_findings(path)
        findings.extend(file_findings)
        scanned_literal_count += literal_count

    recommended_actions: list[str] = []
    if missing_files:
        recommended_actions.append(
            "Restore or relocate the missing curated studio UI surface files before relying on the Korean UI release evidence."
        )
    if findings:
        recommended_actions.append(
            "Replace the remaining English display literals in the curated studio UI surfaces or justify them as allowed technical tokens before release review."
        )

    if not missing_files and not findings:
        status = "passed"
        summary = "Curated studio UI surfaces keep Korean-first display literals and only use approved technical English tokens."
    else:
        status = "failed"
        summary = "Curated studio UI surfaces still contain missing files or unexpected English display literals."

    return RawPrepBenchmarkLocalUiLanguageSmoke(
        output_dir=request.output_dir,
        output_root=request.output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        smoke_path=str(_smoke_path(request.output_dir, output_root=request.output_root)),
        status=status,
        ok=status == "passed",
        scanned_files=scanned_files,
        scanned_file_count=len(scanned_files),
        scanned_literal_count=scanned_literal_count,
        allowed_token_hints=list(_ALLOWED_ENGLISH_TOKENS),
        missing_files=missing_files,
        findings=findings,
        recommended_actions=recommended_actions,
        summary=summary,
    )


def write_rawprep_benchmark_local_ui_language_smoke(
    request: RawPrepBenchmarkLocalUiLanguageSmokeRequest,
) -> RawPrepBenchmarkLocalUiLanguageSmoke:
    smoke = build_rawprep_benchmark_local_ui_language_smoke(request)
    path = _smoke_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(smoke.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return smoke


def load_rawprep_benchmark_local_ui_language_smoke(
    output_dir: str,
    *,
    output_root: str = "outputs",
) -> RawPrepBenchmarkLocalUiLanguageSmoke:
    path = _smoke_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep local UI language smoke artifact was not found: {path}")
    return RawPrepBenchmarkLocalUiLanguageSmoke(**json.loads(path.read_text(encoding="utf-8")))
