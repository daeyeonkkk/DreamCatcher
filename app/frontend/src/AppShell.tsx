import React, { useEffect, useMemo, useRef, useState } from 'react';
import { TopBar } from './components/TopBar';
import { ToolRail, type ToolRailItem } from './components/ToolRail';
import { PropertyPanel, type PropertyPanelSection } from './components/PropertyPanel';
import { FinishDeliveryDesk } from './components/FinishDeliveryDesk';
import { RecentSessionsBoard } from './components/RecentSessionsBoard';
import { StudioActionRailSections } from './components/StudioActionRailSections';
import { StudioFocusSection } from './components/StudioFocusSection';
import { StudioOperationsBoard } from './components/StudioOperationsBoard';
import { StudioSessionSetupSection } from './components/StudioSessionSetupSection';
import { StudioWorkspaceFrame } from './components/StudioWorkspaceFrame';
import { StudioWorkSurfaceNav, type WorkSurfaceNavItem } from './components/StudioWorkSurfaceNav';
import { EphemeralRunPodStrip } from './components/EphemeralRunPodStrip';
import type {
  CompareSource,
  ExportPackageItem,
  OpsEventGroup,
  PodStatusSnapshot,
  SingleRawSummaryView,
  StageItem,
  ToolMetaView,
  WorkspaceModeOption,
} from './components/studioWorkspaceTypes';
import {
  type RawprepArtifactResponse,
  type CameraProfile,
  type EntryPreference,
  type IntakePlan,
  type QualityAutomationPolicy,
  type QualityPreset,
  type SingleRawModePreference,
  type RecentStudioSessionSummary,
  type RecentStudioSessionsResponse,
  type StudioDeadLetterSummary,
  type StudioDeadLetterRetryResponse,
  type StudioEditLinkageState,
  type StudioOpsEventsResponse,
  type StudioProviderCheckpointSessionSnapshot,
  type StudioProviderSummary,
  type StudioOpsRootSummary,
  type StudioOpsRootsResponse,
  type StudioOpsSummary,
  type StudioTelemetryEvent,
  type StudioWorkerControlResponse,
  type RawprepHealthPayload,
  type RawprepJobRecord,
  type RawprepReferencePolicy,
  type RawRestorationGoal,
  type RawRestorationGoalOption,
  type RawRestorationPolicyPayload,
  type StudioBatchExportResponse,
  type StudioCatalogBatchResponse,
  type StudioExportRecord,
  type StudioExportPackageRecord,
  type StudioJobRecord,
  type StudioPresetExportResponse,
  type StudioSelectionState,
  type ToolKey,
  type WorkflowPlan,
  applyStudioSelectionState,
  fetchQualityAutomationPolicy,
  fetchRawRestorationPolicy,
  fetchStudioEditLinkageState,
  fetchStudioSelectionState,
  generateSessionId,
  applyDreamispPreviewAdjustments,
  isAiCapableTool,
  parseJson,
  recordStudioCompareDecision,
  syncStudioEditLinkageState,
  summarizeRawprepHealth,
} from './studioApi';
import {
  defaultWorkspacePreferences,
  loadWorkspacePreferences,
  saveWorkspacePreferences,
  type WorkspaceSliderState,
  type WorkspacePreferences,
} from './workspacePreferences';
import {
  loadWorkspacePresets,
  saveWorkspacePresets,
  type WorkspacePreset,
} from './workspacePresetLibrary';
import {
  clearStudioSessionRecovery,
  loadStudioSessionRecovery,
  saveStudioSessionRecovery,
  type StudioSavedVersionSnapshot,
  type StudioSessionRecoverySnapshot,
} from './studioSessionRecovery';
import {
  describeDeliveryPreset,
  deserializeDeliveryPresetProfiles,
  loadDeliveryPresetProfiles,
  saveDeliveryPresetProfiles,
  type DeliveryPresetKey,
  type DeliveryPresetProfile,
  type DeliveryPresetScope,
} from './deliveryPresetLibrary';
import { studioTokens } from './designTokens';

const tools: ToolMetaView[] = [
  { key: 'removeBg', label: '배경 제거', description: '피사체만 깔끔하게 남깁니다.', group: '마스크' },
  { key: 'replaceBg', label: '배경 교체', description: '새 배경을 만들고 자연스럽게 합성합니다.', group: '생성 편집' },
  { key: 'replaceObject', label: '오브젝트 편집', description: '선택한 영역을 지우거나 바꿉니다.', group: '생성 편집' },
  { key: 'expandCanvas', label: '화면 확장', description: '프레임 밖 여백을 채웁니다.', group: '생성 편집' },
  { key: 'relight', label: '조명 보정', description: '빛 방향과 분위기를 맞춥니다.', group: '보정' },
  { key: 'retouch', label: '리터치', description: '먼지, 결점, 경계선을 손봅니다.', group: '보정' },
  { key: 'enhance', label: '품질 개선', description: '노이즈를 줄이고 디테일을 살립니다.', group: '보정' },
  { key: 'compare', label: '비교 보기', description: '원본과 후보를 나란히 확인합니다.', group: '비교 보기' },
  { key: 'finish', label: '최종 출력', description: '완성본과 패키지를 저장합니다.', group: '내보내기' },
];

const stages: readonly StageItem[] = [
  { key: 'intake', label: '1. 입력 분석' },
  { key: 'rawprep', label: '2. TriRaw 선택' },
  { key: 'edit', label: '3. 편집 작업' },
  { key: 'finish', label: '4. 검토 및 출력' },
] as const;

const workspaceModes: readonly WorkspaceModeOption[] = [
  {
    key: 'standard',
    label: '기본 작업 공간',
    description: '자주 쓰는 작업만 간단히 봅니다.',
  },
  {
    key: 'advanced',
    label: '확장 작업 공간',
    description: 'RAW 근거와 운영 상태까지 확인합니다.',
  },
] as const;

type WorkspaceMode = WorkspacePreferences['workspaceMode'];
type WorkSurfaceKey = 'intake' | 'raw' | 'edit' | 'review' | 'deliver' | 'operate';

const previewableSuffixes = new Set(['.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.heic']);
const supportedUploadSuffixes = new Set(['.rw2', '.cr3', '.dng', '.nef', '.arw', '.orf', '.raf', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp', '.heic']);
const fallbackRawRestorationGoalOptions: RawRestorationGoalOption[] = [
  {
    id: 'truth_preserving',
    label: '진실 보존',
    summary: '실제 프레임 근거를 우선해 고스팅과 과한 질감 생성을 낮춥니다.',
    approval: 'default_delivery_path',
    risk: null,
    delivery_default: true,
    requires_human_review: false,
    tone: 'success',
    review_gates: [],
  },
  {
    id: 'aggressive_restore',
    label: '공격적 복원 후보',
    summary: '고스트와 노이즈 근거를 보며 더 강한 디테일 후보를 만듭니다. 최종 채택 전 검수가 필요합니다.',
    approval: 'qwen_metric_golden_human_review_required',
    risk: 'hallucinated_detail_or_over_sharpened_texture',
    delivery_default: false,
    requires_human_review: true,
    tone: 'warning',
    review_gates: ['qwen_judge_signal_v2', 'metric_checker_layer', 'golden_session_runner', 'human_approval'],
  },
];

function normalizeRawRestorationGoal(value: unknown, options: ReadonlyArray<RawRestorationGoalOption>): RawRestorationGoal {
  const fallback = options.find((option) => option.delivery_default)?.id ?? options[0]?.id ?? 'truth_preserving';
  return typeof value === 'string' && options.some((option) => option.id === value)
    ? (value as RawRestorationGoal)
    : fallback;
}

function rawRestorationGoalLabel(value: RawRestorationGoal, options: ReadonlyArray<RawRestorationGoalOption>): string {
  return options.find((option) => option.id === value)?.label ?? value.replace(/_/g, ' ');
}

function propertyPanelTone(tone: RawRestorationGoalOption['tone'] | undefined): 'default' | 'success' | 'warning' {
  if (tone === 'success' || tone === 'warning') {
    return tone;
  }
  return 'default';
}

function workSurfaceForTool(tool: ToolKey): WorkSurfaceKey {
  if (tool === 'compare') {
    return 'review';
  }
  if (tool === 'finish') {
    return 'deliver';
  }
  return 'edit';
}

function workSurfaceForStage(stage: string): WorkSurfaceKey {
  if (stage === 'rawprep') {
    return 'raw';
  }
  if (stage === 'edit') {
    return 'edit';
  }
  if (stage === 'finish') {
    return 'review';
  }
  return 'intake';
}

type DreamispControlsState = {
  temperatureDelta: number;
  tintDelta: number;
  exposureEv: number;
  contrast: number;
  clarity: number;
};

type SelectionControlsState = {
  threshold: number;
  expandPixels: number;
  featherRadius: number;
};

type SingleRawLensCorrectionSummary = {
  cameraKey: string | null;
  lensKey: string | null;
  distortionModel: string | null;
  applyDistortion: boolean;
  applyVignette: boolean;
  applyLateralCa: boolean;
  cropMarginRatio: number | null;
  notes: string[];
};

function defaultDreamispControls(): DreamispControlsState {
  return {
    temperatureDelta: 0,
    tintDelta: 0,
    exposureEv: 0,
    contrast: 0,
    clarity: 0,
  };
}

function defaultSelectionControls(): SelectionControlsState {
  return {
    threshold: 128,
    expandPixels: 0,
    featherRadius: 4,
  };
}

function clampDreamispControl(value: unknown, minimum: number, maximum: number, fallback = 0): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return fallback;
  }
  return Math.max(minimum, Math.min(maximum, Number(value)));
}

function clampSelectionControl(value: unknown, minimum: number, maximum: number, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return fallback;
  }
  return Math.max(minimum, Math.min(maximum, Number(value)));
}

function dreamispControlsFromPlan(plan: IntakePlan | null): DreamispControlsState {
  const defaults = defaultDreamispControls();
  const dreamispPlan = plan?.dreamisp_plan;
  if (!dreamispPlan || typeof dreamispPlan !== 'object') {
    return defaults;
  }
  const renderState = (dreamispPlan as Record<string, unknown>).render_state;
  if (!renderState || typeof renderState !== 'object') {
    return defaults;
  }
  const whiteBalance = ((renderState as Record<string, unknown>).white_balance ?? {}) as Record<string, unknown>;
  const tone = ((renderState as Record<string, unknown>).tone ?? {}) as Record<string, unknown>;
  const detail = ((renderState as Record<string, unknown>).detail ?? {}) as Record<string, unknown>;
  return {
    temperatureDelta: clampDreamispControl(whiteBalance.temperature_delta, -100, 100, defaults.temperatureDelta),
    tintDelta: clampDreamispControl(whiteBalance.tint_delta, -100, 100, defaults.tintDelta),
    exposureEv: clampDreamispControl(tone.exposure_ev, -4, 4, defaults.exposureEv),
    contrast: clampDreamispControl(tone.contrast, -100, 100, defaults.contrast),
    clarity: clampDreamispControl(detail.clarity, -100, 100, defaults.clarity),
  };
}

function selectionControlsFromState(state: StudioSelectionState | null): SelectionControlsState {
  const defaults = defaultSelectionControls();
  if (!state) {
    return defaults;
  }
  return {
    threshold: clampSelectionControl(state.controls.threshold, 0, 255, defaults.threshold),
    expandPixels: clampSelectionControl(state.controls.expand_pixels, -32, 32, defaults.expandPixels),
    featherRadius: clampSelectionControl(state.controls.feather_radius, 0, 32, defaults.featherRadius),
  };
}

function singleRawLensCorrectionSummary(plan: IntakePlan | null): SingleRawLensCorrectionSummary | null {
  const singleRawPlan = plan?.single_raw_plan;
  if (!singleRawPlan || typeof singleRawPlan !== 'object') {
    return null;
  }
  const lensCorrection = (singleRawPlan as Record<string, unknown>).lens_correction;
  if (!lensCorrection || typeof lensCorrection !== 'object') {
    return null;
  }
  const payload = lensCorrection as Record<string, unknown>;
  const cropMarginRatio = typeof payload.crop_margin_ratio === 'number' && Number.isFinite(payload.crop_margin_ratio)
    ? Number(payload.crop_margin_ratio)
    : null;
  return {
    cameraKey: typeof payload.camera_key === 'string' ? payload.camera_key : null,
    lensKey: typeof payload.lens_key === 'string' ? payload.lens_key : null,
    distortionModel: typeof payload.distortion_model === 'string' ? payload.distortion_model : null,
    applyDistortion: payload.apply_distortion === true,
    applyVignette: payload.apply_vignette === true,
    applyLateralCa: payload.apply_lateral_ca === true,
    cropMarginRatio,
    notes: Array.isArray(payload.notes) ? payload.notes.filter((note): note is string => typeof note === 'string') : [],
  };
}

function singleRawStatusTone(status: string | null | undefined): SingleRawSummaryView['statusTone'] {
  if (status === 'sensor_decoded') {
    return 'success';
  }
  if (status === 'preview_bootstrapped') {
    return 'warning';
  }
  return 'default';
}

function singleRawMetadataSourceLabel(source: unknown): string {
  switch (source) {
    case 'provided':
      return '세션 제공 메타데이터';
    case 'exiftool':
      return 'EXIFTool 추출 메타데이터';
    case 'default':
      return '보수 기본 메타데이터';
    default:
      return '메타데이터 준비 중';
  }
}

function singleRawQualityPresetLabel(value: unknown): string {
  return value === 'safe' ? '안전 우선' : '표준 시작';
}

function singleRawModePreferenceLabel(value: SingleRawModePreference): string {
  switch (value) {
    case 'fast':
      return '고속 모드 고정';
    case 'hq':
      return '정밀 모드 고정';
    case 'safe':
      return '안전 모드 고정';
    default:
      return '자동';
  }
}

function singleRawModeLabel(value: unknown): string {
  switch (value) {
    case 'safe':
      return '안전 모드';
    case 'hq':
      return '정밀 모드';
    case 'fast':
      return '고속 모드';
    default:
      return '모드 준비 중';
  }
}

function singleRawModeSummary(policy: Record<string, unknown> | null, resolvedMode: unknown): string {
  if (policy && typeof policy.summary === 'string' && policy.summary.trim()) {
    if (resolvedMode === 'safe') {
      return '안전 모드: 보수적인 기본 결과와 진단을 유지합니다.';
    }
    if (resolvedMode === 'hq') {
      return '정밀 모드: 복원 품질을 우선합니다.';
    }
    return '고속 모드: 빠른 기본 결과를 만듭니다.';
  }
  if (resolvedMode === 'safe') {
    return '안전 모드: 보수적인 기본 결과와 진단을 유지합니다.';
  }
  if (resolvedMode === 'hq') {
    return '정밀 모드: 복원 품질을 우선합니다.';
  }
  return '고속 모드: 빠른 기본 결과를 만듭니다.';
}

function singleRawRuntimeProfileLabel(value: unknown): string {
  switch (value) {
    case 'sensor_safe_guarded_v1':
      return '안전 가드레일 프로파일';
    case 'sensor_hq_recovery_v1':
      return '정밀 복원 프로파일';
    case 'sensor_fast_preview_v1':
      return '고속 미리보기 프로파일';
    default:
      return '기본 런타임 프로파일';
  }
}

function singleRawRuntimeBackendLabel(value: unknown): string {
  if (typeof value === 'string' && value.trim()) {
    return value;
  }
  return '미리보기 기반 기본 경로';
}

function singleRawTimingSummary(timingReport: Record<string, unknown> | null, resolvedMode: unknown): string {
  if (timingReport && typeof timingReport.summary === 'string' && timingReport.summary.trim()) {
    return timingReport.summary;
  }
  if (resolvedMode === 'hq') {
    return '정밀 모드 처리 시간 근거를 아직 수집하지 못했습니다.';
  }
  if (resolvedMode === 'safe') {
    return '안전 모드 처리 시간 근거를 아직 수집하지 못했습니다.';
  }
  return '고속 모드 처리 시간 근거를 아직 수집하지 못했습니다.';
}

function singleRawNoiseReportSummary(noiseReport: Record<string, unknown> | null, resolvedMode: unknown): string {
  if (noiseReport && typeof noiseReport.summary === 'string' && noiseReport.summary.trim()) {
    return noiseReport.summary;
  }
  if (resolvedMode === 'safe') {
    return '잔여 노이즈를 보수적으로 억제합니다.';
  }
  if (resolvedMode === 'hq') {
    return '잔여 노이즈를 부드럽게 줄입니다.';
  }
  return '노이즈 진단을 유지합니다.';
}

function singleRawRecoveryReportSummary(recoveryReport: Record<string, unknown> | null, resolvedMode: unknown): string {
  if (recoveryReport && typeof recoveryReport.summary === 'string' && recoveryReport.summary.trim()) {
    return recoveryReport.summary;
  }
  if (resolvedMode === 'hq') {
    return '정밀 모드는 저조도 장면과 강한 하이라이트에서 복원 우선 미리보기를 유지합니다.';
  }
  if (resolvedMode === 'safe') {
    return '안전 모드는 복원보다 보수적인 보류 결과를 우선합니다.';
  }
  return '고속 모드는 전용 복원보다 빠른 편집 시작을 우선합니다.';
}

function singleRawArtifactGuardrailSummary(artifactGuardrail: Record<string, unknown> | null, resolvedMode: unknown): string {
  if (artifactGuardrail && typeof artifactGuardrail.summary === 'string' && artifactGuardrail.summary.trim()) {
    return artifactGuardrail.summary;
  }
  if (resolvedMode === 'safe') {
    return '안전 모드 가드레일이 미리보기 단계에서 과한 질감과 경계 흔들림을 더 보수적으로 누릅니다.';
  }
  if (resolvedMode === 'hq') {
    return '정밀 모드 가드레일은 복원 여지를 남기는 미세 보호층으로만 개입합니다.';
  }
  return '고속 모드 가드레일은 고속 미리보기의 직접성을 유지하도록 최소 개입만 합니다.';
}

function singleRawArtifactSuppressionSummary(
  artifactSuppression: Record<string, unknown> | null,
  resolvedMode: unknown,
): string {
  if (artifactSuppression && typeof artifactSuppression.summary === 'string' && artifactSuppression.summary.trim()) {
    return artifactSuppression.summary;
  }
  if (resolvedMode === 'safe') {
    return '안전 모드는 과한 질감과 채도 치우침을 더 강하게 눌러 보수적인 기본 결과를 만듭니다.';
  }
  if (resolvedMode === 'hq') {
    return '정밀 모드는 복원 여지를 남기면서 질감 과장과 색 치우침을 부드럽게 누릅니다.';
  }
  return '고속 모드는 편집 시작 속도를 해치지 않는 범위에서만 질감과 채도 억제를 적용합니다.';
}

function singleRawSafetyFallbackSummary(
  fallbackDecision: Record<string, unknown> | null,
  resolvedMode: unknown,
): string {
  if (fallbackDecision && typeof fallbackDecision.summary === 'string' && fallbackDecision.summary.trim()) {
    return fallbackDecision.summary;
  }
  if (resolvedMode === 'safe') {
    return '안전 모드는 실패나 대체 경로 상황에서 더 보수적인 기본 결과를 우선 남깁니다.';
  }
  if (resolvedMode === 'hq') {
    return '정밀 모드는 복원 우선 미리보기를 유지하고 별도 보류 결과로 내려가지 않습니다.';
  }
  return '고속 모드는 대체 경로 상황에서도 편집 시작 속도를 우선합니다.';
}

function singleRawOpticalSummary(
  lens: SingleRawLensCorrectionSummary | null,
  lensCorrectionReport: Record<string, unknown> | null,
): string {
  if (lensCorrectionReport && typeof lensCorrectionReport.summary === 'string' && lensCorrectionReport.summary.trim()) {
    return lensCorrectionReport.summary;
  }
  if (!lens) {
    return '광학 보정 계획을 아직 읽지 못했습니다.';
  }
  const steps: string[] = [];
  if (lens.applyDistortion) {
    steps.push('왜곡 보정');
  }
  if (lens.applyVignette) {
    steps.push('비네팅 보정');
  }
  if (lens.applyLateralCa) {
    steps.push('색수차 보정');
  }
  const body = steps.length ? steps.join(', ') : '기본 광학 계획 유지';
  const cropMargin = typeof lens.cropMarginRatio === 'number'
    ? `크롭 여유 ${(lens.cropMarginRatio * 100).toFixed(1)}%`
    : '크롭 여유 없음';
  return `${body} · ${cropMargin}`;
}

function singleRawProcessingSummary(
  status: string,
  previewPath: string | null,
  sceneLinearPath: string | null,
  noiseMapPath: string | null,
): string {
  const parts: string[] = [];
  if (status === 'sensor_decoded') {
    parts.push('센서 RAW 디코드로 기본 결과를 만들었습니다.');
  } else if (status === 'preview_bootstrapped') {
    parts.push('세션 미리보기 기반 기본 결과가 준비되었습니다.');
  } else {
    parts.push('SingleRaw 기본 계획을 준비 중입니다.');
  }
  if (previewPath) {
    parts.push('즉시 작업을 시작할 수 있습니다.');
  }
  if (sceneLinearPath) {
    parts.push('장면 선형 마스터를 함께 기록했습니다.');
  }
  if (noiseMapPath) {
    parts.push('노이즈 진단 보기까지 같이 준비했습니다.');
  }
  return parts.join(' ');
}

function singleRawSessionNote(status: string, previewPath: string | null): string {
  if (status === 'sensor_decoded') {
    return '센서 디코드 결과를 작업 기준으로 사용할 수 있습니다.';
  }
  if (status === 'preview_bootstrapped' && previewPath) {
    return '기본 미리보기 결과가 준비되었습니다.';
  }
  return 'SingleRaw 품질 결과를 준비합니다.';
}

function rawprepDreamispEditableSource(job: RawprepJobRecord | null): string | null {
  return firstPreviewableSessionPath(
    job?.group_reports?.[0]?.dreamisp_handoff?.render_preview_path ?? null,
    job?.group_reports?.[0]?.dreamisp_handoff?.recommended_editable_source_path ?? null,
  );
}

function rawprepRecommendedSource(job: RawprepJobRecord | null): string | null {
  return rawprepDreamispEditableSource(job) ?? job?.group_reports?.[0]?.recommended_artifact ?? null;
}

function editableSource(plan: IntakePlan | null, job: RawprepJobRecord | null, directPath: string | null): string | null {
  if (directPath) return directPath;
  const rawprepSource = rawprepRecommendedSource(job);
  if (rawprepSource) return rawprepSource;
  if (!plan || plan.entry_mode === 'rawprep_bracket') return null;
  return plan.editable_asset_path ?? null;
}

function artifactLabel(kind: string): string {
  switch (kind) {
    case 'preview':
      return '미리보기';
    case 'scene_linear':
      return '장면 선형 마스터';
    case 'report':
      return '처리 보고서';
    case 'diagnostics_manifest':
      return '진단 목록';
    case 'noise_map':
      return '노이즈 맵';
    case 'motion_map':
      return '움직임 맵';
    case 'confidence_map':
      return '신뢰도 맵';
    case 'motion_overlay_jpg':
      return '움직임 오버레이';
    default:
      return kind;
  }
}

function isPreviewablePath(path: string): boolean {
  const dot = path.lastIndexOf('.');
  if (dot < 0) return false;
  return previewableSuffixes.has(path.slice(dot).toLowerCase());
}

function uploadFileKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function basenameFromPath(path: string): string {
  const segments = path.split(/[\\/]/).filter(Boolean);
  return segments[segments.length - 1] ?? path;
}

function toolLabelFromKey(value: string | null | undefined): string {
  if (!value) {
    return 'AI 결과';
  }
  const matched = tools.find((tool) => tool.key === value);
  return matched?.label ?? value;
}

function assetKindLabel(kind: 'raw' | 'image' | 'unknown'): string {
  switch (kind) {
    case 'raw':
      return 'RAW 원본';
    case 'image':
      return '이미지 원본';
    default:
      return '미확인 자산';
  }
}

function studioOutputLabel(label: string): string {
  const matched = /^(removeBg|replaceBg|relight|replaceObject|expandCanvas|retouch|enhance|finish|compare) output (\d+)$/i.exec(label);
  if (!matched) {
    return label;
  }
  return `${toolLabelFromKey(matched[1])} 결과 ${matched[2]}`;
}

function studioOutputOriginLabel(origin: string | null | undefined): string | undefined {
  if (!origin) {
    return undefined;
  }
  const name = basenameFromPath(origin);
  return name ? `원본 결과 ${name}` : '워크플로 원본 결과';
}

function studioMaskOutputLabel(label: string): string {
  return `${studioOutputLabel(label)} 마스크`;
}

function generatedCandidateGroup(tool: string | null | undefined): string {
  switch (tool) {
    case 'replaceBg':
      return '배경 교체 후보';
    case 'replaceObject':
      return '선택 영역 채우기 후보';
    case 'expandCanvas':
      return '화면 확장 후보';
    default:
      return '생성 편집 후보';
  }
}

function generatedCandidateNote(tool: string | null | undefined): string {
  switch (tool) {
    case 'replaceBg':
      return '배경 교체 후보입니다.';
    case 'replaceObject':
      return '선택 영역 채우기 후보입니다.';
    case 'expandCanvas':
      return '화면 확장 후보입니다.';
    default:
      return '생성 편집 후보입니다.';
  }
}

function editCandidateGroups(tool: string | null | undefined): string[] {
  if (tool === 'expandCanvas') {
    return ['화면 확장 후보', '생성 편집 후보'];
  }
  return Array.from(new Set(['배경 분리 결과', generatedCandidateGroup(tool), '생성 편집 후보']));
}

function studioOutputGroup(output: StudioJobRecord['outputs'][number], tool: string | null | undefined): string {
  switch (output.kind) {
    case 'background_cutout':
      return '배경 분리 결과';
    case 'generated_candidate':
      return generatedCandidateGroup(tool);
    default:
      return 'AI 결과';
  }
}

function studioOutputNote(output: StudioJobRecord['outputs'][number], tool: string | null | undefined): string | undefined {
  const notes: string[] = [];
  if (output.kind === 'background_cutout') {
    notes.push('피사체가 분리된 편집 소스입니다.');
  } else if (output.kind === 'generated_candidate') {
    notes.push(generatedCandidateNote(tool));
  }
  const originLabel = studioOutputOriginLabel(output.origin);
  if (originLabel) {
    notes.push(originLabel);
  }
  return notes.length ? notes.join(' | ') : undefined;
}

function selectionCoverageLabel(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '계산 전';
  }
  return `${(value * 100).toFixed(1)}%`;
}

function selectionSourceLabel(state: StudioSelectionState | null): string {
  if (!state?.source_mask_path) {
    return '아직 선택 기준이 없습니다.';
  }
  return basenameFromPath(state.source_mask_path);
}

function selectionSourceMismatchNote(state: StudioSelectionState | null, sourcePath: string | null): string | null {
  if (!state?.source_asset_path || !sourcePath) {
    return null;
  }
  if (state.source_asset_path === sourcePath) {
    return null;
  }
  return '현재 작업 소스가 바뀌어 이 선택 미리보기는 이전 소스 기준입니다. 마스크 자산에서 다시 적용해 주세요.';
}

function buildSavedVersionLabel(
  path: string,
  currentCount: number,
  toolLabel: string,
  compareSources: CompareSource[],
): string {
  const matched = compareSources.find((item) => item.path === path);
  const sourceLabel = matched?.label ?? basenameFromPath(path);
  return `버전 ${String(currentCount + 1).padStart(2, '0')} • ${toolLabel} • ${sourceLabel}`;
}

function uniquePackageItems(items: ExportPackageItem[]): ExportPackageItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (!item.path || seen.has(item.path)) {
      return false;
    }
    seen.add(item.path);
    return true;
  });
}

function currentWorkspacePresetSnapshot(
  preferences: WorkspacePreferences,
  name: string,
): WorkspacePreset {
  return {
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name,
    createdAt: new Date().toISOString(),
    ...preferences,
  };
}

function currentDeliveryPresetSnapshot(
  preset: DeliveryPresetKey,
  name: string,
  scope: DeliveryPresetScope,
): DeliveryPresetProfile {
  const descriptor = describeDeliveryPreset(preset);
  return {
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name,
    preset,
    scope,
    createdAt: new Date().toISOString(),
    profileId: descriptor.profileId,
    profileLabel: descriptor.label,
    stage: descriptor.stage,
    masterSource: descriptor.masterSource,
    description: descriptor.description,
  };
}

function deliveryPresetScopeTitle(value: DeliveryPresetScope): string {
  switch (value) {
    case 'batch':
      return '배치';
    case 'session':
      return '세션';
    case 'both':
      return '통합';
    default:
      return value;
  }
}

function exportJsonDownload(payload: unknown, fileName: string): void {
  if (typeof document === 'undefined') {
    return;
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  anchor.rel = 'noopener';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function isSupportedUploadFile(file: File): boolean {
  const dot = file.name.lastIndexOf('.');
  if (dot < 0) return false;
  return supportedUploadSuffixes.has(file.name.slice(dot).toLowerCase());
}

function dedupeUploadFiles(files: File[]): File[] {
  const seen = new Set<string>();
  return files.filter((file) => {
    const key = uploadFileKey(file);
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function cycleComparePath(paths: string[], current: string | null, direction: 1 | -1, blockedPath: string | null = null): string | null {
  if (!paths.length) return null;
  const startIndex = current ? paths.indexOf(current) : -1;
  for (let step = 1; step <= paths.length; step += 1) {
    const candidate = paths[(startIndex + direction * step + paths.length) % paths.length];
    if (candidate !== blockedPath) {
      return candidate;
    }
  }
  return blockedPath && paths.includes(blockedPath) ? blockedPath : paths[0];
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tagName = target.tagName.toLowerCase();
  return target.isContentEditable || tagName === 'input' || tagName === 'textarea' || tagName === 'select';
}

function isRawprepActiveStatus(status: string | undefined): boolean {
  return status === 'queued' || status === 'running' || status === 'cancelling';
}

function isRawprepFailureStatus(status: string | undefined): boolean {
  return status === 'error' || status === 'failed';
}

function isStudioJobActiveStatus(status: string | undefined): boolean {
  return status === 'queued' || status === 'running' || status === 'submitted' || status === 'cancelling';
}

function sessionEntryLabel(entryMode: string): string {
  switch (entryMode) {
    case 'rawprep_bracket':
      return 'TriRaw 브라켓';
    case 'direct_edit_raw':
      return '단일 RAW 일괄 처리';
    case 'direct_edit_image':
      return '이미지 직접 보정';
    default:
      return entryMode;
  }
}

function sessionStatusTone(status: string | null | undefined): { background: string; color: string } {
  if (status === 'done') {
    return { background: '#edf7f1', color: '#19643a' };
  }
  if (status === 'queued' || status === 'running' || status === 'submitted') {
    return { background: '#eef3f8', color: '#233044' };
  }
  if (status === 'cancelling' || status === 'cancelled') {
    return { background: '#f4f0ff', color: '#5f4a8a' };
  }
  if (status === 'error' || status === 'failed' || status === 'blocked') {
    return { background: '#fff4eb', color: '#8a4b16' };
  }
  return { background: '#f4f6f8', color: '#5a6778' };
}

function formatSessionTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

const sessionStepLabels: Record<string, string> = {
  planned: '계획 수립',
  queued: '대기',
  submitted: '제출됨',
  running: '실행 중',
  done: '완료',
  completed: '완료',
  failed: '실패',
  error: '오류',
  blocked: '차단됨',
  cancelled: '중지됨',
  cancelling: '중지 중',
  backend_unavailable: '백엔드 연결 대기',
  waiting_for_source: '작업 소스 대기',
  missing_workflow: '워크플로 누락',
  preparing_input: '입력 준비',
  submitting_to_comfyui: 'ComfyUI 제출',
  waiting_for_history: '기록 대기',
  comfy_failed: 'ComfyUI 실패',
  no_outputs: '산출물 없음',
  waiting_for_outputs: '산출물 대기',
  foundation_ready: '기반 준비 완료',
  waiting_for_runtime: '런타임 대기',
  tri_raw_preview_runtime: 'TriRaw 미리보기 런타임',
  waiting_for_preview_runtime: '미리보기 런타임 대기',
  preview_bootstrapped: '기본 미리보기 준비 완료',
  sensor_decoded: '센서 RAW 디코드 완료',
  checkpointed: '체크포인트 저장됨',
  provider_resume_pending: 'Pod 재개 대기',
  preview_rendered: '미리보기 렌더 완료',
};

const telemetryEventLabels: Record<string, string> = {
  dreamisp_preview_rendered: 'DreamISP 미리보기 렌더 완료',
  session_catalog_updated: '세션 분류 정보 갱신',
  session_catalog_batch_updated: '배치 분류 정보 갱신',
  provider_pause_recovery_ready: 'Pod 일시정지 전 복구 준비 완료',
  dead_letter_investigated: '오류 보관함 조사 갱신',
  compare_decision_recorded: '비교 결정 기록',
  asset_exported: '작업 소스 저장',
  package_exported: '세션 패키지 저장',
  delivery_preset_exported: '납품 프리셋 저장',
  session_recovery_packet_built: '세션 복구 패킷 생성',
  batch_package_exported: '배치 패키지 저장',
  provider_lifecycle_changed: 'Pod 수명주기 변경',
  provider_migration_detected: 'Pod 이동 감지',
  provider_allocation_changed: 'Pod 할당 상태 변경',
  provider_checkpoint_saved: '체크포인트 저장',
  provider_stop_requested: 'Pod 종료 요청',
  provider_resume_completed: 'Pod 재개 완료',
  provider_resume_requested: 'Pod 재개 요청',
  worker_stop_requested: '작업기 중지 요청',
  job_enqueued: '작업 대기열 등록',
  job_recovered: '작업 복구 등록',
  worker_launch_requested: '작업기 시작 요청',
  worker_launch_failed: '작업기 시작 실패',
  job_started: '작업 시작',
  job_poll_scheduled: '작업 상태 조회 예약',
  job_retry_scheduled: '작업 재시도 예약',
  worker_started: '작업기 시작',
  worker_stopped: '작업기 종료',
  worker_idle_shutdown: '유휴 자동 종료',
};

function formatDurationRange(start: string | null | undefined, end: string | null | undefined): string {
  if (!start || !end) {
    return '기록 없음';
  }
  const startTime = new Date(start).getTime();
  const endTime = new Date(end).getTime();
  if (Number.isNaN(startTime) || Number.isNaN(endTime) || endTime < startTime) {
    return '기록 없음';
  }
  const totalSeconds = Math.round((endTime - startTime) / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes <= 0) {
    return `${seconds}초`;
  }
  return `${minutes}분 ${String(seconds).padStart(2, '0')}초`;
}

function formatSessionStep(step: string | null | undefined): string | null {
  if (!step) {
    return null;
  }
  return sessionStepLabels[step] ?? step.replace(/_/g, ' ');
}

function formatTriRawRecommendedArtifact(path: string | null | undefined): string {
  if (!path) {
    return '정보 없음';
  }
  const filename = path.split(/[\\/]/).pop() ?? path;
  switch (filename) {
    case 'selected_reference_preview.jpg':
      return '기준 프레임 우선 미리보기';
    case 'merged_preview.jpg':
      return '병합 결과 미리보기';
    case 'guarded_preview.jpg':
      return '보수 병합 미리보기';
    case 'preview.jpg':
      return '현재 결과 미리보기';
    case 'scene_linear.tiff':
      return '장면 선형 마스터';
    default:
      return filename;
  }
}

function formatTriRawFallbackReason(reason: string | null | undefined): string {
  switch (reason) {
    case 'narrow_bracket':
      return '브라켓 폭이 좁아 기준 프레임을 우선했습니다.';
    case 'motion_guard':
      return '움직임이 커서 보수 병합 경로를 선택했습니다.';
    case 'alignment_guard':
      return '정렬 압력이 커서 보수 병합 경로를 선택했습니다.';
    case 'none':
    case undefined:
    case null:
      return '대체 이유 없이 현재 결과 사용';
    default:
      return reason.replace(/_/g, ' ');
  }
}

function formatCameraProfileLabel(profile: string | null | undefined): string {
  if (!profile || profile === 'auto') {
    return '자동';
  }
  return profile;
}

function formatTelemetryEventLabel(eventType: string): string {
  return telemetryEventLabels[eventType] ?? eventType.replace(/_/g, ' ');
}

function telemetrySourceLabel(source: StudioTelemetryEvent['source']): string {
  switch (source) {
    case 'queue':
      return '처리 대기열';
    case 'studio':
      return '작업 스튜디오';
    case 'rawprep':
      return 'TriRaw';
    case 'export':
      return '내보내기';
    case 'ops':
      return '운영';
    case 'quality_automation':
      return '품질 자동화';
    case 'quality_tuning':
      return '튜닝 제안';
    default:
      return source;
  }
}

function formatWorkerModeLabel(mode: 'embedded' | 'external' | null | undefined): string {
  if (mode === 'external') {
    return '외부 작업기';
  }
  if (mode === 'embedded') {
    return '내장 작업기';
  }
  return '대기 중';
}

function formatProviderControlState(state: StudioProviderSummary['control_state'] | undefined): string {
  switch (state) {
    case 'running':
      return '실행 중';
    case 'starting':
      return '시작 중';
    case 'stopping':
      return '종료 중';
    case 'stopped':
      return '종료됨';
    case 'offline':
      return '오프라인';
    case 'error':
      return '오류';
    default:
      return '미설정';
  }
}

function providerCheckpointToRecoverySnapshot(
  snapshot: StudioProviderCheckpointSessionSnapshot | null | undefined,
): StudioSessionRecoverySnapshot | null {
  if (!snapshot) {
    return null;
  }
  return {
    sessionId: snapshot.session_id,
    outputRoot: snapshot.output_root,
    rawprepJobId: snapshot.rawprep_job_id ?? null,
    studioJobId: snapshot.studio_job_id ?? null,
    directPath: snapshot.direct_path ?? null,
    comparePrimary: snapshot.compare_primary ?? null,
    compareCandidate: snapshot.compare_candidate ?? null,
    sourceHistory: snapshot.source_history ?? [],
    sourceHistoryIndex: typeof snapshot.source_history_index === 'number' ? snapshot.source_history_index : -1,
    savedVersions: (snapshot.saved_versions ?? []).map((item) => ({
      id: item.id,
      label: item.label,
      path: item.path,
      createdAt: item.created_at,
    })),
  };
}

function outputRootLabel(outputRoot: string): string {
  const segments = outputRoot.split(/[\\/]/).filter(Boolean);
  return segments[segments.length - 1] ?? outputRoot;
}

function deadLetterToolLabel(deadLetter: StudioDeadLetterSummary): string {
  if (deadLetter.task_type === 'rawprep') {
    return 'TriRaw';
  }
  return toolLabelFromKey(deadLetter.tool);
}

function deadLetterInvestigationLabel(status: StudioDeadLetterSummary['investigation_status']): string {
  switch (status) {
    case 'acknowledged':
      return '확인됨';
    case 'assigned':
      return '배정됨';
    case 'resolved':
      return '해결됨';
    case 'muted':
      return '음소거';
    default:
      return '열림';
  }
}

function firstPreviewableSessionPath(...paths: Array<string | null | undefined>): string | null {
  for (const path of paths) {
    if (path && isPreviewablePath(path)) {
      return path;
    }
  }
  return null;
}

function recentResultPreviewPath(
  rawprepArtifacts: RawprepArtifactResponse | null,
  rawprepJob: RawprepJobRecord | null,
  studioJob: StudioJobRecord | null,
): string | null {
  const studioOutputPath = [...(studioJob?.outputs ?? [])]
    .reverse()
    .find((output) => isPreviewablePath(output.path))
    ?.path;
  if (studioOutputPath) {
    return studioOutputPath;
  }

  for (const kind of ['preview', 'scene_linear']) {
    const artifactPath = rawprepArtifacts?.artifacts.find((artifact) => artifact.exists && artifact.kind === kind && isPreviewablePath(artifact.path))?.path;
    if (artifactPath) {
      return artifactPath;
    }
  }

  return firstPreviewableSessionPath(
    rawprepDreamispEditableSource(rawprepJob),
    rawprepJob?.group_reports?.[0]?.recommended_artifact ?? null,
  );
}

function summarizeSessionPrompt(value: string | null | undefined, maxLength = 96): string | null {
  if (!value) {
    return null;
  }
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return null;
  }
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 3).trimEnd()}...`;
}

function previewMaxEdgeProfile(viewportWidth: number): { source: number; compare: number; recent: number } {
  if (viewportWidth < 720) {
    return { source: 960, compare: 480, recent: 240 };
  }
  if (viewportWidth < 1280) {
    return { source: 1200, compare: 640, recent: 280 };
  }
  return { source: 1400, compare: 768, recent: 320 };
}

function rawprepPollDelay(status: string | undefined, documentHidden: boolean): number {
  if (documentHidden) {
    return 5000;
  }
  if (status === 'queued') {
    return 2200;
  }
  if (status === 'running') {
    return 1400;
  }
  return 2400;
}

function studioJobPollDelay(status: string | undefined, documentHidden: boolean): number {
  if (documentHidden) {
    return 6500;
  }
  if (status === 'queued' || status === 'submitted') {
    return 2800;
  }
  if (status === 'running') {
    return 1800;
  }
  return 3200;
}

function workflowPlanDebounceDelay(documentHidden: boolean): number {
  return documentHidden ? 320 : 180;
}

function previewUrl(path: string | null, outputRoot = 'outputs', maxEdge = 1400): string | null {
  if (!path || !isPreviewablePath(path)) {
    return null;
  }
  return `/api/studio/preview?path=${encodeURIComponent(path)}&output_root=${encodeURIComponent(outputRoot)}&max_edge=${encodeURIComponent(String(maxEdge))}`;
}

function percentMetric(value: number | null | undefined, digits = 1): string | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return null;
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function aiToolStatusText(
  plan: WorkflowPlan | null,
  loading: boolean,
  tool: ToolKey,
  hasSource: boolean,
  sourcePreviewable: boolean,
  podState?: { state: 'offline' | 'booting' | 'ready' | 'busy' | 'failed' | 'stopping'; reason: string } | null,
): string {
  if (!isAiCapableTool(tool)) {
    return '이 도구는 검토 또는 출력 단계용이라 ComfyUI 작업을 실행하지 않습니다.';
  }
  if (loading) return '선택한 AI 도구의 워크플로, 모델, 실행 가능 상태를 확인하는 중입니다.';
  if (podState && ['offline', 'booting', 'failed', 'stopping'].includes(podState.state)) {
    return podState.reason;
  }
  if (hasSource && !sourcePreviewable) {
    return 'RAW 원본은 AI 도구에 직접 보낼 수 없습니다. TIFF/JPG 작업 소스를 선택하세요.';
  }
  if (!plan) return '미리보기 가능한 작업 소스를 고르면 AI 도구 실행 준비 상태를 확인합니다.';
  if (!plan.workflow_exists) return `${toolLabelFromKey(plan.tool)} 워크플로가 아직 현재 스튜디오 빌드에 연결되지 않았습니다.`;
  if (!plan.execution_ready) return plan.availability_error ?? '현재 AI 백엔드가 준비되지 않았습니다.';
  return `${toolLabelFromKey(plan.tool)} 작업을 실행할 수 있습니다.`;
}

function derivePodStatus(
  backendHealthy: boolean | null,
  opsSummary: StudioOpsSummary | null,
  rawprepHealth: RawprepHealthPayload | null,
): PodStatusSnapshot {
  if (backendHealthy === false) {
    return {
      state: 'offline',
      label: '오프라인',
      tone: '#fff0f0',
      border: '#d9a5a5',
      reason: 'Pod 또는 백엔드가 현재 닫혀 있습니다. 로컬에서 `python app/scripts/runpod_provider_control.py resume`로 Pod를 다시 연 뒤 계속 버튼을 누르면 세션 복구를 이어갈 수 있습니다.',
    };
  }
  if (!opsSummary) {
    return {
      state: backendHealthy ? 'booting' : 'offline',
      label: backendHealthy ? '기동 중' : '오프라인',
      tone: backendHealthy ? '#eef5ff' : '#fff0f0',
      border: backendHealthy ? '#bdd0e8' : '#d9a5a5',
      reason: backendHealthy
        ? '백엔드는 응답 중입니다. Studio 실행 상태를 확인하고 있습니다.'
        : 'Pod 응답을 기다리는 중입니다.',
    };
  }
  const state = opsSummary.pod_state ?? 'ready';
  const reason = opsSummary.pod_state_reason
    ?? (state === 'ready' && rawprepHealth?.ok === false
      ? 'AI는 준비됐지만 rawprep toolchain은 Pod 이미지에 없을 수 있습니다.'
      : '현재 상태를 확인했습니다.');
  const labelMap: Record<PodStatusSnapshot['state'], string> = {
    offline: '오프라인',
    booting: '기동 중',
    ready: '준비됨',
    busy: '작업 중',
    failed: '장애',
    stopping: '중지 중',
  };
  const toneMap: Record<PodStatusSnapshot['state'], { tone: string; border: string }> = {
    offline: { tone: '#fff0f0', border: '#d9a5a5' },
    booting: { tone: '#eef5ff', border: '#bdd0e8' },
    ready: { tone: '#edf8f1', border: '#c9decf' },
    busy: { tone: '#fff8eb', border: '#e5d09c' },
    failed: { tone: '#fff0f0', border: '#d9a5a5' },
    stopping: { tone: '#f3f5f8', border: '#ccd4df' },
  };
  return {
    state,
    label: labelMap[state],
    tone: toneMap[state].tone,
    border: toneMap[state].border,
    reason,
  };
}

export function AppShell() {
  const initialPreferences = useRef(loadWorkspacePreferences()).current;
  const initialPresets = useRef(loadWorkspacePresets()).current;
  const initialDeliveryPresets = useRef(loadDeliveryPresetProfiles()).current;
  const [activeTool, setActiveTool] = useState<ToolKey>(initialPreferences.activeTool);
  const [activeSurface, setActiveSurface] = useState<WorkSurfaceKey>('intake');
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>(initialPreferences.workspaceMode);
  const [files, setFiles] = useState<File[]>([]);
  const [entryPreference, setEntryPreference] = useState<EntryPreference>(initialPreferences.entryPreference);
  const [cameraProfile, setCameraProfile] = useState<CameraProfile>(initialPreferences.cameraProfile);
  const [qualityPreset, setQualityPreset] = useState<QualityPreset>(initialPreferences.qualityPreset);
  const [singleRawModePreference, setSingleRawModePreference] = useState<SingleRawModePreference>(initialPreferences.singleRawModePreference);
  const [rawRestorationGoal, setRawRestorationGoal] = useState<RawRestorationGoal>(initialPreferences.rawRestorationGoal);
  const [prompt, setPrompt] = useState(initialPreferences.prompt);
  const [sliders, setSliders] = useState<WorkspaceSliderState>(initialPreferences.sliders);
  const [backendHealthy, setBackendHealthy] = useState<boolean | null>(null);
  const [rawprepHealth, setRawprepHealth] = useState<RawprepHealthPayload | null>(null);
  const [intakePlan, setIntakePlan] = useState<IntakePlan | null>(null);
  const [rawprepJob, setRawprepJob] = useState<RawprepJobRecord | null>(null);
  const [rawprepArtifacts, setRawprepArtifacts] = useState<RawprepArtifactResponse | null>(null);
  const [workflowPlan, setWorkflowPlan] = useState<WorkflowPlan | null>(null);
  const [qualityAutomationPolicy, setQualityAutomationPolicy] = useState<QualityAutomationPolicy | null>(null);
  const [qualityAutomationPolicyError, setQualityAutomationPolicyError] = useState<string | null>(null);
  const [rawRestorationPolicy, setRawRestorationPolicy] = useState<RawRestorationPolicyPayload | null>(null);
  const [rawRestorationPolicyError, setRawRestorationPolicyError] = useState<string | null>(null);
  const [studioJob, setStudioJob] = useState<StudioJobRecord | null>(null);
  const [selectionState, setSelectionState] = useState<StudioSelectionState | null>(null);
  const [editLinkage, setEditLinkage] = useState<StudioEditLinkageState | null>(null);
  const [recentSessions, setRecentSessions] = useState<RecentStudioSessionSummary[]>([]);
  const [recentSessionsLoading, setRecentSessionsLoading] = useState(false);
  const [selectedBatchSessionIds, setSelectedBatchSessionIds] = useState<string[]>([]);
  const [opsSummary, setOpsSummary] = useState<StudioOpsSummary | null>(null);
  const [opsRoots, setOpsRoots] = useState<StudioOpsRootSummary[]>([]);
  const [opsEvents, setOpsEvents] = useState<StudioTelemetryEvent[]>([]);
  const [opsLoading, setOpsLoading] = useState(false);
  const [opsActionBusy, setOpsActionBusy] = useState<string | null>(null);
  const [opsEventSourceFilter, setOpsEventSourceFilter] = useState<'all' | StudioTelemetryEvent['source']>('all');
  const [opsEventStatusFilter, setOpsEventStatusFilter] = useState<'all' | 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'acknowledged' | 'assigned' | 'resolved' | 'muted'>('all');
  const [opsEventQuery, setOpsEventQuery] = useState('');
  const [workspacePresets, setWorkspacePresets] = useState<WorkspacePreset[]>(initialPresets);
  const [deliveryPresetProfiles, setDeliveryPresetProfiles] = useState<DeliveryPresetProfile[]>(initialDeliveryPresets);
  const [expandedRecentSessionIds, setExpandedRecentSessionIds] = useState<string[]>([]);
  const [viewportWidth, setViewportWidth] = useState(() => (typeof window === 'undefined' ? 1280 : window.innerWidth));
  const [documentHidden, setDocumentHidden] = useState(() => (typeof document === 'undefined' ? false : document.visibilityState === 'hidden'));
  const [sessionOutputRootOverride, setSessionOutputRootOverride] = useState<string | null>(null);
  const [sessionRecoveryHydrated, setSessionRecoveryHydrated] = useState(false);
  const [directPath, setDirectPath] = useState<string | null>(null);
  const [comparePrimary, setComparePrimary] = useState<string | null>(null);
  const [compareCandidate, setCompareCandidate] = useState<string | null>(null);
  const [sourceHistory, setSourceHistory] = useState<string[]>([]);
  const [sourceHistoryIndex, setSourceHistoryIndex] = useState(-1);
  const [savedVersions, setSavedVersions] = useState<StudioSavedVersionSnapshot[]>([]);
  const [uploadDragActive, setUploadDragActive] = useState(false);
  const [intakeBusy, setIntakeBusy] = useState(false);
  const [rawprepBusy, setRawprepBusy] = useState(false);
  const [workflowBusy, setWorkflowBusy] = useState(false);
  const [studioJobBusy, setStudioJobBusy] = useState(false);
  const [dreamispBusy, setDreamispBusy] = useState(false);
  const [dreamispControls, setDreamispControls] = useState<DreamispControlsState>(defaultDreamispControls());
  const [selectionBusy, setSelectionBusy] = useState(false);
  const [selectionControls, setSelectionControls] = useState<SelectionControlsState>(defaultSelectionControls());
  const [exportBusy, setExportBusy] = useState(false);
  const [lastExportPath, setLastExportPath] = useState<string | null>(null);
  const [packageBusy, setPackageBusy] = useState(false);
  const [lastPackagePath, setLastPackagePath] = useState<string | null>(null);
  const [batchPackageBusy, setBatchPackageBusy] = useState(false);
  const [lastBatchReportPath, setLastBatchReportPath] = useState<string | null>(null);
  const [catalogBusyKey, setCatalogBusyKey] = useState<string | null>(null);
  const [batchCatalogPickStatus, setBatchCatalogPickStatus] = useState<'unreviewed' | 'selected' | 'rejected' | 'hold'>('selected');
  const [batchCatalogReviewStatus, setBatchCatalogReviewStatus] = useState<'intake' | 'culling' | 'proofing' | 'client_review' | 'print_ready' | 'delivered' | 'archived'>('proofing');
  const [batchCatalogKeywords, setBatchCatalogKeywords] = useState('');
  const [batchProofingProfile, setBatchProofingProfile] = useState('');
  const [batchPrintProfile, setBatchPrintProfile] = useState('');
  const [batchClientCollection, setBatchClientCollection] = useState('');
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const presetImportInputRef = useRef<HTMLInputElement | null>(null);
  const uploadDragDepthRef = useRef(0);
  const workflowPlanCacheRef = useRef<Map<string, WorkflowPlan>>(new Map());

  const sourcePath = editableSource(intakePlan, rawprepJob, directPath);
  const rawprepRequest = intakePlan?.rawprep_request ?? null;
  const sessionOutputRoot = rawprepRequest?.output_root ?? sessionOutputRootOverride ?? 'outputs';
  const podStatus = useMemo(
    () => derivePodStatus(backendHealthy, opsSummary, rawprepHealth),
    [backendHealthy, opsSummary, rawprepHealth],
  );
  const rawRestorationGoalOptions = useMemo<RawRestorationGoalOption[]>(() => {
    const options = rawRestorationPolicy?.options?.length
      ? rawRestorationPolicy.options
      : fallbackRawRestorationGoalOptions;
    return options.length ? options : fallbackRawRestorationGoalOptions;
  }, [rawRestorationPolicy]);
  const stageKey = studioJob?.status === 'done'
    ? 'finish'
    : studioJobBusy
      ? 'edit'
      : rawprepBusy
        ? 'rawprep'
        : sourcePath
          ? 'edit'
          : intakePlan
            ? 'rawprep'
            : 'intake';
  const toolMeta = tools.find((tool) => tool.key === activeTool) ?? tools[0];
  const singleRawLensCorrection = useMemo(() => singleRawLensCorrectionSummary(intakePlan), [intakePlan]);
  const aiCapableTool = isAiCapableTool(activeTool);
  const sourcePreviewable = Boolean(sourcePath && isPreviewablePath(sourcePath));
  const aiPodReady = podStatus.state === 'ready' || podStatus.state === 'busy';
  const canRunStudioJob = Boolean(
    aiCapableTool
    && sourcePath
    && sourcePreviewable
    && aiPodReady
    && workflowPlan?.workflow_exists
    && workflowPlan?.execution_ready
    && !studioJobBusy,
  );

  useEffect(() => {
    if (stageKey === 'finish') {
      setActiveSurface((current) => (current === 'deliver' || current === 'operate' ? current : 'review'));
      return;
    }
    const nextSurface = workSurfaceForStage(stageKey);
    setActiveSurface((current) => {
      if (current === 'deliver' || current === 'operate' || current === 'review') {
        return current;
      }
      return current === nextSurface ? current : nextSurface;
    });
  }, [stageKey]);

  const previewMaxEdges = useMemo(() => previewMaxEdgeProfile(viewportWidth), [viewportWidth]);
  const selectionSourceMismatch = selectionSourceMismatchNote(selectionState, sourcePath);
  const selectionPreviewUrl = previewUrl(selectionState?.preview_path ?? null, sessionOutputRoot, previewMaxEdges.compare);
  const comparePrimaryUrl = previewUrl(comparePrimary, sessionOutputRoot, previewMaxEdges.compare);
  const compareCandidateUrl = previewUrl(compareCandidate, sessionOutputRoot, previewMaxEdges.compare);
  const sourcePreviewUrl = previewUrl(sourcePath, sessionOutputRoot, previewMaxEdges.source);
  const singleRawSummary = useMemo<SingleRawSummaryView | null>(() => {
    const payload = intakePlan?.single_raw_plan;
    if (!payload || typeof payload !== 'object') {
      return null;
    }
    const singleRawPlan = payload;
    const decode = singleRawPlan.decode && typeof singleRawPlan.decode === 'object'
      ? singleRawPlan.decode as Record<string, unknown>
      : null;
    const sceneLinear = singleRawPlan.scene_linear && typeof singleRawPlan.scene_linear === 'object'
      ? singleRawPlan.scene_linear as Record<string, unknown>
      : null;
    const modePolicy = singleRawPlan.mode_policy && typeof singleRawPlan.mode_policy === 'object'
      ? singleRawPlan.mode_policy as Record<string, unknown>
      : null;
    const status = typeof singleRawPlan.materialization_status === 'string'
      ? singleRawPlan.materialization_status
      : 'planned';
    const inputPreviewPath = typeof singleRawPlan.materialized_input_preview_path === 'string'
      ? singleRawPlan.materialized_input_preview_path
      : typeof singleRawPlan.preview_source_path === 'string'
        ? singleRawPlan.preview_source_path
        : null;
    const recoveryBaselinePath = typeof singleRawPlan.materialized_recovery_baseline_path === 'string'
      ? singleRawPlan.materialized_recovery_baseline_path
      : null;
    const previewPath = typeof singleRawPlan.materialized_preview_path === 'string'
      ? singleRawPlan.materialized_preview_path
      : intakePlan?.editable_asset_path ?? null;
    const noiseMapPath = typeof singleRawPlan.materialized_noise_map_path === 'string'
      ? singleRawPlan.materialized_noise_map_path
      : null;
    const lowlightMapPath = typeof singleRawPlan.materialized_lowlight_map_path === 'string'
      ? singleRawPlan.materialized_lowlight_map_path
      : null;
    const sceneLinearPath = typeof sceneLinear?.materialized_path === 'string'
      ? sceneLinear.materialized_path
      : null;
    const resolvedMode = typeof singleRawPlan.resolved_mode === 'string'
      ? singleRawPlan.resolved_mode
      : modePolicy?.resolved_mode;
    const qualityPreset = typeof singleRawPlan.quality_preset === 'string'
      ? singleRawPlan.quality_preset
      : modePolicy?.requested_quality_preset;
    const runtimeProfile = decode?.runtime_profile;
    const noiseReport = decode?.noise_report && typeof decode.noise_report === 'object'
      ? decode.noise_report as Record<string, unknown>
      : null;
    const recoveryReport = decode?.recovery_report && typeof decode.recovery_report === 'object'
      ? decode.recovery_report as Record<string, unknown>
      : null;
    const artifactGuardrail = decode?.artifact_guardrail && typeof decode.artifact_guardrail === 'object'
      ? decode.artifact_guardrail as Record<string, unknown>
      : null;
    const artifactSuppression = decode?.artifact_suppression && typeof decode.artifact_suppression === 'object'
      ? decode.artifact_suppression as Record<string, unknown>
      : null;
    const lensCorrectionReport = decode?.lens_correction_report && typeof decode.lens_correction_report === 'object'
      ? decode.lens_correction_report as Record<string, unknown>
      : null;
    const fallbackDecision = decode?.fallback_decision && typeof decode.fallback_decision === 'object'
      ? decode.fallback_decision as Record<string, unknown>
      : null;
    const timingReport = decode?.timing_report && typeof decode.timing_report === 'object'
      ? decode.timing_report as Record<string, unknown>
      : singleRawPlan.materialized_timing_report && typeof singleRawPlan.materialized_timing_report === 'object'
        ? singleRawPlan.materialized_timing_report as Record<string, unknown>
        : null;
    return {
      status,
      statusLabel: formatSessionStep(status) ?? status.replace(/_/g, ' '),
      statusTone: singleRawStatusTone(status),
      qualityPresetLabel: singleRawQualityPresetLabel(qualityPreset),
      modeLabel: singleRawModeLabel(resolvedMode),
      modeSummary: singleRawModeSummary(modePolicy, resolvedMode),
      runtimeProfileLabel: singleRawRuntimeProfileLabel(runtimeProfile),
      timingSummary: singleRawTimingSummary(timingReport, resolvedMode),
      noiseReportSummary: singleRawNoiseReportSummary(noiseReport, resolvedMode),
      recoveryReportSummary: singleRawRecoveryReportSummary(recoveryReport, resolvedMode),
      artifactGuardrailSummary: singleRawArtifactGuardrailSummary(artifactGuardrail, resolvedMode),
      artifactSuppressionSummary: singleRawArtifactSuppressionSummary(artifactSuppression, resolvedMode),
      safetyFallbackSummary: singleRawSafetyFallbackSummary(fallbackDecision, resolvedMode),
      inputPreviewPath,
      inputPreviewUrl: previewUrl(inputPreviewPath, sessionOutputRoot, previewMaxEdges.compare),
      recoveryBaselinePath,
      recoveryBaselineUrl: previewUrl(recoveryBaselinePath, sessionOutputRoot, previewMaxEdges.compare),
      previewPath,
      previewUrl: previewUrl(previewPath, sessionOutputRoot, previewMaxEdges.compare),
      noiseMapPath,
      noiseMapUrl: previewUrl(noiseMapPath, sessionOutputRoot, previewMaxEdges.compare),
      lowlightMapPath,
      lowlightMapUrl: previewUrl(lowlightMapPath, sessionOutputRoot, previewMaxEdges.compare),
      sceneLinearPath,
      sceneLinearUrl: previewUrl(sceneLinearPath, sessionOutputRoot, previewMaxEdges.compare),
      sceneLinearLabel: sceneLinearPath ? basenameFromPath(sceneLinearPath) : '아직 없음',
      runtimeBackendLabel: singleRawRuntimeBackendLabel(decode?.runtime_backend),
      metadataSourceLabel: singleRawMetadataSourceLabel(singleRawPlan.metadata_source),
      opticalSummary: singleRawOpticalSummary(singleRawLensCorrection, lensCorrectionReport),
      processingSummary: singleRawProcessingSummary(status, previewPath, sceneLinearPath, noiseMapPath),
      note: singleRawSessionNote(status, previewPath),
      isCurrentSource: Boolean(previewPath && sourcePath === previewPath),
    };
  }, [intakePlan, previewMaxEdges.compare, sessionOutputRoot, singleRawLensCorrection, sourcePath]);
  const rawprepGroupReport = rawprepJob?.group_reports?.[0] ?? null;
  const rawprepMotionOverlayPath = rawprepGroupReport?.motion_overlay_path ?? null;
  const rawprepMotionOverlayUrl = previewUrl(rawprepMotionOverlayPath, sessionOutputRoot, previewMaxEdges.compare);
  const rawprepMotionOverlaySummary = rawprepGroupReport?.motion_overlay_summary ?? null;
  const rawprepMotionOverlayCoverage = rawprepGroupReport?.motion_overlay_coverage ?? null;
  const rawprepDiagnosticViews = useMemo(() => {
    const report = rawprepGroupReport;
    if (!report) {
      return [];
    }
    const items = [
      {
        key: 'motion_watch',
        label: '움직임 감시',
        path: report.motion_overlay_path ?? null,
        summary: report.motion_overlay_summary ?? '선택된 기준 프레임과 비교해 움직임이 큰 구역을 강조합니다.',
        note: percentMetric(report.motion_overlay_coverage) ? `감지 범위 ${percentMetric(report.motion_overlay_coverage)}` : null,
      },
      {
        key: 'confidence_watch',
        label: '신뢰도 감시',
        path: report.confidence_preview_path ?? null,
        summary: '안전하게 병합 가능한 구역과 기준 프레임 유지 구역입니다.',
        note: [
          percentMetric(report.confidence_summary?.mean_confidence) ? `평균 ${percentMetric(report.confidence_summary?.mean_confidence)}` : null,
          percentMetric(report.confidence_summary?.reference_holdout_coverage) ? `기준 유지 ${percentMetric(report.confidence_summary?.reference_holdout_coverage)}` : null,
        ].filter((value): value is string => Boolean(value)).join(' | ') || null,
      },
      {
        key: 'ghost_risk_watch',
        label: '고스팅 위험 감시',
        path: report.ghost_risk_map_path ?? null,
        summary: '병합 시 고스팅 아티팩트가 생기기 쉬운 움직임 구역을 강조합니다.',
        note: percentMetric(report.deghost_summary?.ghost_risk_coverage) ? `위험 범위 ${percentMetric(report.deghost_summary?.ghost_risk_coverage)}` : null,
      },
      {
        key: 'highlight_watch',
        label: '하이라이트 감시',
        path: report.highlight_map_path ?? null,
        summary: '복원 가능한 하이라이트 여유 구간입니다.',
        note: percentMetric(report.hdr_summary?.highlight_recovery_coverage) ? `복원 범위 ${percentMetric(report.hdr_summary?.highlight_recovery_coverage)}` : null,
      },
      {
        key: 'shadow_watch',
        label: '암부 감시',
        path: report.shadow_map_path ?? null,
        summary: '추가 암부 복원이 가능한 구역입니다.',
        note: percentMetric(report.hdr_summary?.shadow_lift_coverage) ? `복원 범위 ${percentMetric(report.hdr_summary?.shadow_lift_coverage)}` : null,
      },
      {
        key: 'deghost_holdout',
        label: '고스팅 억제 유지',
        path: report.deghost_mask_path ?? null,
        summary: '이중 경계 위험으로 기준 프레임을 유지한 구역입니다.',
        note: [
          percentMetric(report.deghost_summary?.holdout_coverage) ? `유지 범위 ${percentMetric(report.deghost_summary?.holdout_coverage)}` : null,
          percentMetric(report.deghost_summary?.merge_coverage) ? `병합 범위 ${percentMetric(report.deghost_summary?.merge_coverage)}` : null,
        ].filter((value): value is string => Boolean(value)).join(' | ') || null,
      },
      {
        key: 'hdr_gain_watch',
        label: 'HDR 이득 감시',
        path: report.hdr_gain_map_path ?? null,
        summary: 'HDR 이득이 남아 있는 구역입니다.',
        note: percentMetric(report.hdr_summary?.hdr_gain_coverage) ? `이득 범위 ${percentMetric(report.hdr_summary?.hdr_gain_coverage)}` : null,
      },
      {
        key: 'alignment_offset_watch',
        label: '정렬 오프셋 감시',
        path: report.alignment_offset_map_path ?? null,
        summary: '지역 정렬 보정이 큰 구역입니다.',
        note: [
          typeof report.alignment_summary?.piecewise_local_alignment?.active_frame_count === 'number'
            ? `활성 프레임 ${report.alignment_summary.piecewise_local_alignment.active_frame_count}`
            : null,
          typeof report.alignment_summary?.piecewise_local_alignment?.max_local_offset === 'number'
            ? `최대 오프셋 ${report.alignment_summary.piecewise_local_alignment.max_local_offset.toFixed(1)} px`
            : null,
        ].filter((value): value is string => Boolean(value)).join(' | ') || null,
      },
      {
        key: 'alignment_residual_watch',
        label: '정렬 잔차 감시',
        path: report.alignment_residual_map_path ?? null,
        summary: '프레임 간 차이가 남은 구역입니다.',
        note: report.alignment_summary?.has_nonzero_offsets ? '잔차 집중 구역은 이후 학습형 정렬기가 더 정교하게 다뤄야 할 영역을 가리킵니다.' : null,
      },
      {
        key: 'alignment_refinement_watch',
        label: '정렬 보강 감시',
        path: report.alignment_refinement_map_path ?? null,
        summary: '보수 병합이 필요한 잔차 구역입니다.',
        note: [
          percentMetric(report.alignment_refinement_summary?.guarded_holdout_coverage)
            ? `유지 범위 ${percentMetric(report.alignment_refinement_summary?.guarded_holdout_coverage)}`
            : null,
          percentMetric(report.alignment_refinement_summary?.merge_strength_suppression_mean)
            ? `억제 정도 ${percentMetric(report.alignment_refinement_summary?.merge_strength_suppression_mean)}`
            : null,
        ].filter((value): value is string => Boolean(value)).join(' | ') || null,
      },
    ];
    return items
      .filter((item): item is { key: string; label: string; path: string; summary: string; note: string | null } => Boolean(item.path && isPreviewablePath(item.path)))
      .map((item) => ({
        ...item,
        url: previewUrl(item.path, sessionOutputRoot, previewMaxEdges.compare),
      }));
  }, [rawprepGroupReport, sessionOutputRoot, previewMaxEdges.compare]);
  const compareSources = useMemo<CompareSource[]>(() => {
    const items: CompareSource[] = [];
    const seenPaths = new Set<string>();
    const pushItem = (item: CompareSource | null) => {
      if (!item || seenPaths.has(item.path)) {
        return;
      }
      seenPaths.add(item.path);
      items.push(item);
    };
    intakePlan?.staged_assets.forEach((asset, index) => {
      if (asset.kind !== 'image' || !isPreviewablePath(asset.staged_path)) {
        return;
      }
      pushItem({
        key: `input_${index}_${asset.staged_path}`,
        label: asset.file_name,
        path: asset.staged_path,
        group: '입력 원본',
        note: assetKindLabel(asset.kind),
        previewUrl: previewUrl(asset.staged_path, sessionOutputRoot, previewMaxEdges.compare),
      });
    });
    rawprepArtifacts?.artifacts
      ?.filter((artifact) => artifact.exists && isPreviewablePath(artifact.path))
      .forEach((artifact) => {
        pushItem({
          key: `${artifact.kind}_${artifact.path}`,
          label: artifactLabel(artifact.kind),
          path: artifact.path,
          group: 'TriRaw 결과',
          note: artifact.notes ?? undefined,
          previewUrl: previewUrl(artifact.path, sessionOutputRoot, previewMaxEdges.compare),
        });
      });
    rawprepDiagnosticViews.forEach((diagnostic) => {
      pushItem({
        key: `diagnostic_${diagnostic.key}_${diagnostic.path}`,
        label: diagnostic.label,
        path: diagnostic.path,
        group: 'TriRaw 진단',
        note: [diagnostic.summary, diagnostic.note].filter((value): value is string => Boolean(value)).join(' | '),
        previewUrl: diagnostic.url,
      });
    });
    if (singleRawSummary?.previewPath && isPreviewablePath(singleRawSummary.previewPath)) {
      pushItem({
        key: `single_raw_preview_${singleRawSummary.previewPath}`,
        label: '기본 품질 결과',
        path: singleRawSummary.previewPath,
        group: 'SingleRaw 결과',
        note: singleRawSummary.processingSummary,
        previewUrl: singleRawSummary.previewUrl,
      });
    }
    if (singleRawSummary?.inputPreviewPath && isPreviewablePath(singleRawSummary.inputPreviewPath)) {
      pushItem({
        key: `single_raw_input_${singleRawSummary.inputPreviewPath}`,
        label: '입력 기준 미리보기',
        path: singleRawSummary.inputPreviewPath,
        group: 'SingleRaw 입력',
        note: '가드레일 적용 전 기준이 되는 입력 미리보기입니다.',
        previewUrl: singleRawSummary.inputPreviewUrl,
      });
    }
    if (singleRawSummary?.recoveryBaselinePath && isPreviewablePath(singleRawSummary.recoveryBaselinePath)) {
      pushItem({
        key: `single_raw_recovery_baseline_${singleRawSummary.recoveryBaselinePath}`,
        label: '복원 기준 보기',
        path: singleRawSummary.recoveryBaselinePath,
        group: 'SingleRaw 진단',
        note: '정밀 모드가 복원 우선 단계로 넘어가기 직전의 기준 미리보기입니다.',
        previewUrl: singleRawSummary.recoveryBaselineUrl,
      });
    }
    if (singleRawSummary?.sceneLinearPath && isPreviewablePath(singleRawSummary.sceneLinearPath)) {
      pushItem({
        key: `single_raw_scene_linear_${singleRawSummary.sceneLinearPath}`,
        label: '장면 선형 마스터',
        path: singleRawSummary.sceneLinearPath,
        group: 'SingleRaw 결과',
        note: '기본 품질 향상 기준이 되는 장면 선형 마스터입니다.',
        previewUrl: singleRawSummary.sceneLinearUrl,
      });
    }
    if (singleRawSummary?.noiseMapPath && isPreviewablePath(singleRawSummary.noiseMapPath)) {
      pushItem({
        key: `single_raw_noise_${singleRawSummary.noiseMapPath}`,
        label: '노이즈 보기',
        path: singleRawSummary.noiseMapPath,
        group: 'SingleRaw 진단',
        note: '세부 노이즈가 남은 구역입니다.',
        previewUrl: singleRawSummary.noiseMapUrl,
      });
    }
    if (singleRawSummary?.lowlightMapPath && isPreviewablePath(singleRawSummary.lowlightMapPath)) {
      pushItem({
        key: `single_raw_lowlight_${singleRawSummary.lowlightMapPath}`,
        label: '저조도 복원 보기',
        path: singleRawSummary.lowlightMapPath,
        group: 'SingleRaw 진단',
        note: singleRawSummary.recoveryReportSummary,
        previewUrl: singleRawSummary.lowlightMapUrl,
      });
    }
    if (sourcePath && isPreviewablePath(sourcePath)) {
      pushItem({
        key: `active_${sourcePath}`,
        label: '현재 작업 소스',
        path: sourcePath,
        group: '작업 소스',
        previewUrl: previewUrl(sourcePath, sessionOutputRoot, previewMaxEdges.compare),
      });
    }
    if (selectionState?.preview_path && isPreviewablePath(selectionState.preview_path)) {
      pushItem({
        key: `selection_preview_${selectionState.preview_path}`,
        label: '현재 선택 미리보기',
        path: selectionState.preview_path,
        group: '선택 기준',
        note: [
          `선택 범위 ${selectionCoverageLabel(selectionState.coverage_ratio)}`,
          selectionSourceMismatch ?? `기준 마스크 ${basenameFromPath(selectionState.source_mask_path)}`,
        ].filter((value): value is string => Boolean(value)).join(' | '),
        previewUrl: previewUrl(selectionState.preview_path, sessionOutputRoot, previewMaxEdges.compare),
      });
    }
    if (selectionState?.current_mask_path && isPreviewablePath(selectionState.current_mask_path)) {
      pushItem({
        key: `selection_mask_${selectionState.current_mask_path}`,
        label: '현재 선택 마스크',
        path: selectionState.current_mask_path,
        group: '마스크 자산',
        note: selectionSourceMismatch ?? '현재 선택 기준을 미세 조정해 다시 저장한 마스크입니다.',
        previewUrl: previewUrl(selectionState.current_mask_path, sessionOutputRoot, previewMaxEdges.compare),
      });
    }
    studioJob?.outputs
      ?.filter((output) => isPreviewablePath(output.path))
      .forEach((output, index) => {
        pushItem({
          key: `studio_${index}_${output.path}`,
          label: studioOutputLabel(output.label),
          path: output.path,
          group: studioOutputGroup(output, studioJob?.tool),
          note: studioOutputNote(output, studioJob?.tool),
          previewUrl: previewUrl(output.path, sessionOutputRoot, previewMaxEdges.compare),
        });
        if (output.linked_mask_path && isPreviewablePath(output.linked_mask_path)) {
          pushItem({
            key: `studio_mask_${index}_${output.linked_mask_path}`,
            label: studioMaskOutputLabel(output.label),
            path: output.linked_mask_path,
            group: '마스크 자산',
            note: '배경 제거 결과에서 다시 사용할 수 있도록 추출한 선택 마스크입니다.',
            previewUrl: previewUrl(output.linked_mask_path, sessionOutputRoot, previewMaxEdges.compare),
          });
        }
      });
    return items;
  }, [intakePlan, previewMaxEdges.compare, rawprepArtifacts, rawprepDiagnosticViews, selectionSourceMismatch, selectionState, sessionOutputRoot, singleRawSummary, sourcePath, studioJob]);
  const reusableMaskOutputs = useMemo(
    () => (
      studioJob?.outputs?.filter((output) => Boolean(output.linked_mask_path && isPreviewablePath(output.linked_mask_path))) ?? []
    ),
    [studioJob],
  );
  const backgroundCutoutOutputs = useMemo(
    () => (
      studioJob?.outputs?.filter((output) => output.kind === 'background_cutout' && isPreviewablePath(output.path)) ?? []
    ),
    [studioJob],
  );
  const generatedCandidateOutputs = useMemo(
    () => (
      studioJob?.outputs?.filter((output) => output.kind === 'generated_candidate' && isPreviewablePath(output.path)) ?? []
    ),
    [studioJob],
  );
  const generatedCandidateGroupLabel = useMemo(
    () => generatedCandidateGroup(studioJob?.tool),
    [studioJob?.tool],
  );
  const editCandidateGroupLabels = useMemo(
    () => editCandidateGroups(studioJob?.tool),
    [studioJob?.tool],
  );
  const editCandidateCompareSourceCount = useMemo(
    () => compareSources.filter((item) => editCandidateGroupLabels.includes(item.group)).length,
    [compareSources, editCandidateGroupLabels],
  );
  const rawprepSelectedReference = useMemo(() => {
    const groupReport = rawprepGroupReport;
    const referenceSelection = groupReport?.reference_selection ?? [];
    if (!referenceSelection.length) {
      return null;
    }
    return referenceSelection.find((entry) => entry.raw_path === groupReport?.selected_single_raw)
      ?? referenceSelection.reduce((best, entry) => ((entry.total_score ?? -1) > (best.total_score ?? -1) ? entry : best), referenceSelection[0]);
  }, [rawprepGroupReport]);
  const rawprepSelectedReferencePreviewPath = rawprepSelectedReference?.preview_path ?? null;
  const rawprepSelectedReferencePreviewUrl = previewUrl(rawprepSelectedReferencePreviewPath, sessionOutputRoot, previewMaxEdges.compare);
  const rawprepReferenceHighlightWatchPath = rawprepSelectedReference?.diagnostics?.highlight_watch_path ?? null;
  const rawprepReferenceHighlightWatchUrl = previewUrl(rawprepReferenceHighlightWatchPath, sessionOutputRoot, previewMaxEdges.compare);
  const rawprepReferenceShadowWatchPath = rawprepSelectedReference?.diagnostics?.shadow_watch_path ?? null;
  const rawprepReferenceShadowWatchUrl = previewUrl(rawprepReferenceShadowWatchPath, sessionOutputRoot, previewMaxEdges.compare);
  const rawprepReferenceReviewItems = useMemo(() => {
    const referenceSelection = rawprepGroupReport?.reference_selection ?? [];
    if (!referenceSelection.length) {
      return [];
    }
    const autoLeader = referenceSelection.reduce(
      (best, entry) => ((entry.total_score ?? -Infinity) > (best.total_score ?? -Infinity) ? entry : best),
      referenceSelection[0],
    );
    return referenceSelection.map((entry) => ({
      ...entry,
      previewUrl: previewUrl(entry.preview_path ?? null, sessionOutputRoot, 720),
      highlightWatchUrl: previewUrl(entry.diagnostics?.highlight_watch_path ?? null, sessionOutputRoot, 540),
      shadowWatchUrl: previewUrl(entry.diagnostics?.shadow_watch_path ?? null, sessionOutputRoot, 540),
      scoreDeltaToLeader: (entry.total_score ?? 0) - (autoLeader.total_score ?? 0),
      isSelected: entry.raw_path === rawprepSelectedReference?.raw_path,
      isAutoLeader: entry.raw_path === autoLeader.raw_path,
    }));
  }, [rawprepGroupReport, rawprepSelectedReference, sessionOutputRoot, previewMaxEdges.compare]);
  const rawprepCandidateReviewItems = useMemo(() => {
    const candidateScores = rawprepGroupReport?.candidate_scores ?? [];
    if (!candidateScores.length) {
      return [];
    }
    const leader = candidateScores.reduce(
      (best, entry) => ((entry.total_score ?? -Infinity) > (best.total_score ?? -Infinity) ? entry : best),
      candidateScores[0],
    );
    const recommendedPath = rawprepGroupReport?.recommended_artifact ?? null;
    return candidateScores.map((entry) => ({
      ...entry,
      previewUrl: previewUrl(entry.path ?? null, sessionOutputRoot, previewMaxEdges.compare),
      scoreDeltaToLeader: (entry.total_score ?? 0) - (leader.total_score ?? 0),
      isWinner: entry.path === recommendedPath,
      isLeader: entry.label === leader.label,
    }));
  }, [rawprepGroupReport, sessionOutputRoot, previewMaxEdges.compare]);
  const compareHotkeysEnabled = Boolean((workspaceMode === 'advanced' || activeTool === 'compare') && compareSources.length > 1);
  const currentRecentSessionSummary = useMemo<RecentStudioSessionSummary | null>(() => {
    if (!intakePlan) {
      return null;
    }
    const matchedSession = recentSessions.find((session) => session.session_id === intakePlan.session_id);
    return {
      session_id: intakePlan.session_id,
      output_root: sessionOutputRoot,
      session_root: intakePlan.session_root,
      entry_mode: intakePlan.entry_mode,
      staged_asset_count: intakePlan.staged_assets.length,
      primary_file_name: intakePlan.staged_assets[0]?.file_name ?? null,
      editable_asset_path: intakePlan.editable_asset_path,
      source_preview_path: firstPreviewableSessionPath(
        sourcePath,
        intakePlan.editable_asset_path,
        ...intakePlan.staged_assets.map((asset) => asset.staged_path),
      ),
      result_preview_path: recentResultPreviewPath(rawprepArtifacts, rawprepJob, studioJob),
      rawprep_job_id: rawprepJob?.job_id ?? null,
      rawprep_status: rawprepJob?.status ?? null,
      studio_job_id: studioJob?.job_id ?? null,
      studio_status: studioJob?.status ?? null,
      studio_current_step: studioJob?.current_step ?? null,
      studio_tool: studioJob?.tool ?? null,
      prompt_preview: summarizeSessionPrompt(studioJob?.prompt),
      catalog: matchedSession?.catalog ?? {
        rating: 0,
        pick_status: 'unreviewed',
        review_status: 'intake',
        keywords: [],
      },
      last_updated_at: new Date().toISOString(),
    };
  }, [intakePlan, rawprepArtifacts, rawprepJob, recentSessions, sessionOutputRoot, sourcePath, studioJob]);
  const latestResultPath = useMemo(
    () => recentResultPreviewPath(rawprepArtifacts, rawprepJob, studioJob),
    [rawprepArtifacts, rawprepJob, studioJob],
  );
  const sourceHistoryCurrentPath = sourceHistoryIndex >= 0 ? sourceHistory[sourceHistoryIndex] ?? null : null;
  const canUndoWorkingSource = sourceHistoryIndex > 0;
  const canRedoWorkingSource = sourceHistoryIndex >= 0 && sourceHistoryIndex < sourceHistory.length - 1;
  const currentWorkspacePreferences = useMemo<WorkspacePreferences>(() => ({
    activeTool,
    workspaceMode,
    entryPreference,
    cameraProfile,
    qualityPreset,
    singleRawModePreference,
    rawRestorationGoal,
    prompt,
    sliders,
  }), [activeTool, cameraProfile, entryPreference, prompt, qualityPreset, rawRestorationGoal, singleRawModePreference, sliders, workspaceMode]);
  const exportPackageItems = useMemo<ExportPackageItem[]>(() => uniquePackageItems([
    sourcePath ? { path: sourcePath, label: 'working_source' } : null,
    latestResultPath ? { path: latestResultPath, label: 'latest_result' } : null,
    comparePrimary ? { path: comparePrimary, label: 'compare_select' } : null,
    compareCandidate ? { path: compareCandidate, label: 'compare_candidate' } : null,
    ...savedVersions.map((version, index) => ({ path: version.path, label: `saved_version_${index + 1}` })),
  ].filter((item): item is ExportPackageItem => item !== null)), [
    compareCandidate,
    comparePrimary,
    latestResultPath,
    savedVersions,
    sourcePath,
  ]);
  const finishExportPresets = useMemo<Array<{
    key: DeliveryPresetKey;
    label: string;
    description: string;
    items: ExportPackageItem[];
  }>>(() => {
    const rawprepReviewPreview = rawprepArtifacts?.artifacts.find((artifact) => artifact.kind === 'preview' && artifact.exists)?.path ?? null;
    const rawprepSceneLinearMaster = rawprepArtifacts?.artifacts.find((artifact) => artifact.kind === 'scene_linear' && artifact.exists)?.path ?? null;
    const rawprepArchiveItems = rawprepArtifacts?.artifacts
      .filter((artifact) => artifact.exists)
      .map((artifact) => ({ path: artifact.path, label: artifact.kind })) ?? [];
    const reviewPack = uniquePackageItems([
      comparePrimary ? { path: comparePrimary, label: 'select_review' } : null,
      compareCandidate ? { path: compareCandidate, label: 'candidate_review' } : null,
      latestResultPath ? { path: latestResultPath, label: 'latest_result' } : null,
      rawprepReviewPreview ? { path: rawprepReviewPreview, label: 'review_preview' } : null,
    ].filter((item): item is ExportPackageItem => item !== null));
    const clientDelivery = uniquePackageItems([
      latestResultPath ? { path: latestResultPath, label: 'client_result' } : null,
      sourcePath ? { path: sourcePath, label: 'working_source' } : null,
      rawprepSceneLinearMaster ? { path: rawprepSceneLinearMaster, label: 'delivery_master' } : null,
    ].filter((item): item is ExportPackageItem => item !== null));
    const masterArchive = uniquePackageItems([
      ...exportPackageItems,
      ...rawprepArchiveItems,
    ]);
    const proofingSheet = uniquePackageItems([
      rawprepReviewPreview ? { path: rawprepReviewPreview, label: 'review_preview' } : null,
      latestResultPath ? { path: latestResultPath, label: 'proof_finish' } : null,
      rawprepSceneLinearMaster ? { path: rawprepSceneLinearMaster, label: 'scene_linear_master' } : null,
      sourcePath ? { path: sourcePath, label: 'proof_source' } : null,
    ].filter((item): item is ExportPackageItem => item !== null));
    const printMaster = uniquePackageItems([
      latestResultPath ? { path: latestResultPath, label: 'print_result' } : null,
      rawprepSceneLinearMaster ? { path: rawprepSceneLinearMaster, label: 'print_scene_linear_master' } : null,
      sourcePath ? { path: sourcePath, label: 'print_source' } : null,
    ].filter((item): item is ExportPackageItem => item !== null));
    const clientReviewPortal = uniquePackageItems([
      rawprepReviewPreview ? { path: rawprepReviewPreview, label: 'review_preview' } : null,
      latestResultPath ? { path: latestResultPath, label: 'portal_latest_result' } : null,
      sourcePath ? { path: sourcePath, label: 'portal_source' } : null,
      rawprepSceneLinearMaster ? { path: rawprepSceneLinearMaster, label: 'scene_linear_master' } : null,
    ].filter((item): item is ExportPackageItem => item !== null));
    return [
      {
        key: 'review_pack',
        label: '검토 묶음',
        description: '검토용 미리보기와 비교 결과를 묶습니다.',
        items: reviewPack,
      },
      {
        key: 'client_delivery',
        label: '고객 전달본',
        description: '최종 결과와 장면 선형 작업 마스터를 함께 묶습니다.',
        items: clientDelivery,
      },
      {
        key: 'master_archive',
        label: '마스터 보관본',
        description: '장면 선형 마스터, 미리보기, 진단 산출물, 최종 결과를 장기 보관용으로 남깁니다.',
        items: masterArchive,
      },
      {
        key: 'proofing_sheet',
        label: '교정 시트',
        description: '교정 라운드용 미리보기, 최종 결과, 장면 선형 마스터를 함께 묶습니다.',
        items: proofingSheet,
      },
      {
        key: 'print_master',
        label: '출력 마스터',
        description: '출력용 최종 결과와 장면 선형 마스터를 마무리 단계에서 분기합니다.',
        items: printMaster,
      },
      {
        key: 'client_review_portal',
        label: '고객 검토 포털',
        description: '고객 검토 포털에 올릴 미리보기/결과/소스 묶음을 만듭니다.',
        items: clientReviewPortal,
      },
    ];
  }, [compareCandidate, comparePrimary, exportPackageItems, latestResultPath, rawprepArtifacts?.artifacts, sourcePath]);
  const finishTelemetry = useMemo(() => ([
    { label: '세션 번호', value: intakePlan?.session_id ?? '미시작' },
    { label: '진입 모드', value: intakePlan ? sessionEntryLabel(intakePlan.entry_mode) : '미분석' },
    { label: '입력 자산', value: intakePlan ? `${intakePlan.staged_assets.length}개` : '0개' },
    { label: 'TriRaw 처리 시간', value: formatDurationRange(rawprepJob?.started_at, rawprepJob?.finished_at) },
    { label: 'AI 처리 시간', value: formatDurationRange(studioJob?.started_at, studioJob?.finished_at) },
    { label: 'AI 산출물', value: studioJob ? `${studioJob.outputs.length}개` : '0개' },
    { label: '저장 버전', value: `${savedVersions.length}개` },
    { label: '패키지 후보', value: `${exportPackageItems.length}개` },
  ]), [exportPackageItems.length, intakePlan, rawprepJob?.finished_at, rawprepJob?.started_at, savedVersions.length, studioJob, studioJob?.finished_at, studioJob?.started_at]);
  const groupedOpsEvents = useMemo<OpsEventGroup[]>(() => {
    const groups: OpsEventGroup[] = [];
    const groupIndex = new Map<string, OpsEventGroup>();
    opsEvents.forEach((event) => {
      const key = event.session_id ? `session:${event.session_id}` : `source:${event.source}`;
      let group = groupIndex.get(key);
      if (!group) {
        group = {
          key,
          label: event.session_id ?? `${telemetrySourceLabel(event.source)} 레인`,
          summary: '',
          items: [],
        };
        groupIndex.set(key, group);
        groups.push(group);
      }
      group.items.push(event);
    });
    return groups.map((group) => {
      const latest = group.items[0];
      const sources = [...new Set(group.items.map((item) => telemetrySourceLabel(item.source)))].join(' · ');
      const summary = `${group.items.length}건 · ${formatSessionTimestamp(latest?.occurred_at ?? '')}${sources ? ` · ${sources}` : ''}`;
      return { ...group, summary };
    });
  }, [opsEvents]);
  const selectedBatchSessions = useMemo(
    () => recentSessions.filter((session) => selectedBatchSessionIds.includes(session.session_id)),
    [recentSessions, selectedBatchSessionIds],
  );
  const workflowPlanCacheKey = `${activeTool}|${intakePlan?.session_id ?? 'none'}|${sessionOutputRoot}`;
  const isTabletLayout = viewportWidth < 1320;
  const isStackedLayout = viewportWidth < 1100;
  const isPhoneLayout = viewportWidth < 720;
  const isAdvancedWorkspace = workspaceMode === 'advanced';
  const shellGridTemplateColumns = isStackedLayout
    ? '1fr'
    : isAdvancedWorkspace
      ? '264px minmax(0, 1fr) 360px'
      : '236px minmax(0, 1fr) 316px';
  const intakeGridTemplateColumns = isStackedLayout ? '1fr' : 'minmax(0, 1.2fr) minmax(280px, 0.8fr)';
  const optionGridTemplateColumns = isPhoneLayout ? '1fr' : isTabletLayout ? 'repeat(2, minmax(0, 1fr))' : 'repeat(3, minmax(0, 1fr))';
  const workAreaGridTemplateColumns = isStackedLayout
    ? '1fr'
    : isAdvancedWorkspace
      ? 'minmax(0, 1fr) minmax(280px, 360px)'
      : '1fr';
  const compareGridTemplateColumns = isPhoneLayout ? '1fr' : 'repeat(2, minmax(0, 1fr))';
  const focusGridTemplateColumns = isPhoneLayout ? '1fr' : 'minmax(0, 1.35fr) minmax(280px, 0.65fr)';
  const standardSecondaryGridTemplateColumns = isStackedLayout ? '1fr' : 'minmax(300px, 0.78fr) minmax(0, 1.22fr)';
  const supportDeckGridTemplateColumns = isStackedLayout ? '1fr' : 'minmax(0, 1.02fr) minmax(0, 0.98fr)';
  const workSurfaceItems = useMemo<WorkSurfaceNavItem[]>(() => ([
    {
      key: 'intake',
      label: '원본',
      description: '파일 추가와 입력 분석',
      status: files.length ? `${files.length}개 파일` : '대기',
    },
    {
      key: 'raw',
      label: 'RAW',
      description: 'TriRaw와 SingleRaw 준비',
      status: rawprepBusy ? '실행 중' : rawprepRequest ? 'TriRaw 가능' : singleRawSummary ? 'SingleRaw 준비' : '대기',
    },
    {
      key: 'edit',
      label: '편집',
      description: `${toolMeta.label} 작업`,
      status: sourcePath ? '소스 선택됨' : '소스 필요',
    },
    {
      key: 'review',
      label: '검수',
      description: '비교와 품질 판단',
      status: compareSources.length ? `${compareSources.length}개 후보` : '후보 없음',
    },
    {
      key: 'deliver',
      label: '납품',
      description: '저장과 패키지',
      status: exportPackageItems.length ? `${exportPackageItems.length}개 항목` : '대기',
    },
    {
      key: 'operate',
      label: '운영',
      description: 'RunPod와 세션 복구',
      status: podStatus.label,
    },
  ]), [
    compareSources.length,
    exportPackageItems.length,
    files.length,
    podStatus.label,
    rawprepBusy,
    rawprepRequest,
    singleRawSummary,
    sourcePath,
    toolMeta.label,
  ]);

  async function refreshRuntimeHealth(): Promise<boolean> {
    try {
      const [apiResponse, rawprepResponse] = await Promise.all([fetch('/health'), fetch('/api/rawprep/health')]);
      setBackendHealthy(apiResponse.ok);
      setRawprepHealth(rawprepResponse.ok ? await rawprepResponse.json() as RawprepHealthPayload : { ok: false, engine_readiness: {} });
      return apiResponse.ok;
    } catch (_error) {
      setBackendHealthy(false);
      setRawprepHealth({ ok: false, engine_readiness: {} });
      return false;
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function loadHealth() {
      const healthy = await refreshRuntimeHealth();
      if (cancelled && !healthy) {
        return;
      }
    }
    void loadHealth();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!backendHealthy) {
      return;
    }
    let cancelled = false;
    async function loadQualityAutomationPolicy() {
      try {
        const policy = await fetchQualityAutomationPolicy();
        if (!cancelled) {
          setQualityAutomationPolicy(policy);
          setQualityAutomationPolicyError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setQualityAutomationPolicy(null);
          setQualityAutomationPolicyError(error instanceof Error ? error.message : String(error));
        }
      }
    }
    void loadQualityAutomationPolicy();
    return () => {
      cancelled = true;
    };
  }, [backendHealthy]);

  useEffect(() => {
    if (!backendHealthy) {
      return;
    }
    let cancelled = false;
    async function loadRawRestorationPolicy() {
      try {
        const policy = await fetchRawRestorationPolicy();
        if (!cancelled) {
          setRawRestorationPolicy(policy);
          setRawRestorationPolicyError(null);
          setRawRestorationGoal((current) => normalizeRawRestorationGoal(current, policy.options));
        }
      } catch (error) {
        if (!cancelled) {
          setRawRestorationPolicy(null);
          setRawRestorationPolicyError(error instanceof Error ? error.message : String(error));
        }
      }
    }
    void loadRawRestorationPolicy();
    return () => {
      cancelled = true;
    };
  }, [backendHealthy]);

  useEffect(() => {
    let frame = 0;
    const handleResize = () => {
      if (frame) {
        window.cancelAnimationFrame(frame);
      }
      frame = window.requestAnimationFrame(() => {
        setViewportWidth(window.innerWidth);
      });
    };
    window.addEventListener('resize', handleResize);
    return () => {
      if (frame) {
        window.cancelAnimationFrame(frame);
      }
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  useEffect(() => {
    const handleVisibilityChange = () => {
      setDocumentHidden(document.visibilityState === 'hidden');
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  useEffect(() => {
    saveWorkspacePreferences({
      activeTool,
      workspaceMode,
      entryPreference,
      cameraProfile,
      qualityPreset,
      singleRawModePreference,
      rawRestorationGoal,
      prompt,
      sliders,
    });
  }, [activeTool, cameraProfile, entryPreference, prompt, qualityPreset, rawRestorationGoal, singleRawModePreference, sliders, workspaceMode]);

  useEffect(() => {
    setDreamispControls(dreamispControlsFromPlan(intakePlan));
  }, [intakePlan]);

  useEffect(() => {
    setSelectionControls(selectionControlsFromState(selectionState));
  }, [selectionState]);

  useEffect(() => {
    saveWorkspacePresets(workspacePresets);
  }, [workspacePresets]);

  useEffect(() => {
    saveDeliveryPresetProfiles(deliveryPresetProfiles);
  }, [deliveryPresetProfiles]);

  async function restoreSessionSnapshot(
    snapshot: StudioSessionRecoverySnapshot,
    options?: { clearSavedSnapshotOnFailure?: boolean },
  ) {
    const clearSavedSnapshotOnFailure = options?.clearSavedSnapshotOnFailure ?? false;

    try {
      const intakeResponse = await fetch(
        `/api/studio/intake/session?session_id=${encodeURIComponent(snapshot.sessionId)}&output_root=${encodeURIComponent(snapshot.outputRoot)}`,
      );
      const restoredIntakePlan = await parseJson<IntakePlan>(intakeResponse);

      let restoredRawprepJob: RawprepJobRecord | null = null;
      let restoredRawprepArtifacts: RawprepArtifactResponse | null = null;
      if (snapshot.rawprepJobId) {
        try {
          const rawprepResponse = await fetch(
            `/api/rawprep/jobs/${encodeURIComponent(snapshot.rawprepJobId)}?output_root=${encodeURIComponent(snapshot.outputRoot)}`,
          );
          restoredRawprepJob = await parseJson<RawprepJobRecord>(rawprepResponse);
          if (restoredRawprepJob.status === 'done') {
            const artifactsResponse = await fetch(
              `/api/rawprep/jobs/${encodeURIComponent(snapshot.rawprepJobId)}/artifacts?output_root=${encodeURIComponent(snapshot.outputRoot)}`,
            );
            restoredRawprepArtifacts = await parseJson<RawprepArtifactResponse>(artifactsResponse);
          }
        } catch {
          restoredRawprepJob = null;
          restoredRawprepArtifacts = null;
        }
      }

      let restoredStudioJob: StudioJobRecord | null = null;
      if (snapshot.studioJobId) {
        try {
          const studioResponse = await fetch(
            `/api/jobs/${encodeURIComponent(snapshot.studioJobId)}?output_root=${encodeURIComponent(snapshot.outputRoot)}`,
          );
          restoredStudioJob = await parseJson<StudioJobRecord>(studioResponse);
        } catch {
          restoredStudioJob = null;
        }
      }

      let restoredSelectionState: StudioSelectionState | null = null;
      try {
        restoredSelectionState = await fetchStudioSelectionState({
          sessionId: snapshot.sessionId,
          outputRoot: snapshot.outputRoot,
        });
      } catch {
        restoredSelectionState = null;
      }

      clearPipelineState();
      setSessionOutputRootOverride(snapshot.outputRoot);
      setIntakePlan(restoredIntakePlan);
      setFiles([]);
      setRawprepJob(restoredRawprepJob);
      setRawprepArtifacts(restoredRawprepArtifacts);
      setStudioJob(restoredStudioJob);
      setSelectionState(restoredSelectionState);
      setRawprepBusy(isRawprepActiveStatus(restoredRawprepJob?.status));
      setStudioJobBusy(isStudioJobActiveStatus(restoredStudioJob?.status));
      setError(null);

      if (isRawprepFailureStatus(restoredRawprepJob?.status)) {
        setError(restoredRawprepJob?.error ?? '마지막 TriRaw 세션이 실패 상태로 복구되었습니다.');
      } else if (restoredStudioJob && (restoredStudioJob.status === 'error' || restoredStudioJob.status === 'blocked')) {
        setError(restoredStudioJob.error ?? '마지막 AI 세션이 중단 상태로 복구되었습니다.');
      }

      const availablePaths = new Set<string>();
      restoredIntakePlan.staged_assets.forEach((asset) => availablePaths.add(asset.staged_path));
      if (restoredIntakePlan.editable_asset_path) {
        availablePaths.add(restoredIntakePlan.editable_asset_path);
      }
      restoredRawprepArtifacts?.artifacts.forEach((artifact) => {
        if (artifact.exists) {
          availablePaths.add(artifact.path);
        }
      });
      restoredRawprepJob?.group_reports?.forEach((report) => {
        if (report.recommended_artifact) {
          availablePaths.add(report.recommended_artifact);
        }
      });
      restoredStudioJob?.outputs.forEach((output) => availablePaths.add(output.path));
      if (restoredSelectionState?.preview_path) {
        availablePaths.add(restoredSelectionState.preview_path);
      }
      if (restoredSelectionState?.current_mask_path) {
        availablePaths.add(restoredSelectionState.current_mask_path);
      }

      const restoredDirectPath = snapshot.directPath && availablePaths.has(snapshot.directPath) ? snapshot.directPath : null;
      const restoredComparePrimary = snapshot.comparePrimary && availablePaths.has(snapshot.comparePrimary) ? snapshot.comparePrimary : null;
      const restoredCompareCandidate = snapshot.compareCandidate && availablePaths.has(snapshot.compareCandidate) ? snapshot.compareCandidate : null;
      const restoredSourceHistory = snapshot.sourceHistory.filter((path) => availablePaths.has(path));
      const restoredSavedVersions = snapshot.savedVersions.filter((version) => availablePaths.has(version.path));

      setDirectPath(restoredDirectPath);
      setComparePrimary(restoredComparePrimary);
      setCompareCandidate(restoredCompareCandidate);
      setSourceHistory(restoredSourceHistory);
      setSourceHistoryIndex(
        restoredSourceHistory.length
          ? Math.min(Math.max(snapshot.sourceHistoryIndex, 0), restoredSourceHistory.length - 1)
          : -1,
      );
      setSavedVersions(restoredSavedVersions);
      return true;
    } catch (restoreError) {
      if (clearSavedSnapshotOnFailure) {
        clearStudioSessionRecovery();
      }
      setError(restoreError instanceof Error ? restoreError.message : '세션을 다시 불러오지 못했습니다.');
      return false;
    }
  }

  async function refreshRecentSessions() {
    setRecentSessionsLoading(true);
    try {
      const response = await fetch(`/api/studio/intake/sessions?output_root=${encodeURIComponent(sessionOutputRoot)}&limit=8`);
      const payload = await parseJson<RecentStudioSessionsResponse>(response);
      setRecentSessions(payload.items);
    } catch (_error) {
      setRecentSessions([]);
    } finally {
      setRecentSessionsLoading(false);
    }
  }

  async function refreshSelectionState(sessionId: string, outputRoot: string) {
    try {
      const payload = await fetchStudioSelectionState({ sessionId, outputRoot });
      setSelectionState(payload);
      return payload;
    } catch (_selectionError) {
      setSelectionState(null);
      return null;
    }
  }

  async function refreshEditLinkageState(sessionId: string, outputRoot: string) {
    try {
      const payload = await fetchStudioEditLinkageState({ sessionId, outputRoot });
      setEditLinkage(payload);
      return payload;
    } catch (_editLinkageError) {
      setEditLinkage(null);
      return null;
    }
  }

  async function syncEditLinkageState(request: {
    sessionId: string;
    outputRoot: string;
    currentSourcePath?: string | null;
    activeTool?: string | null;
    studioJobId?: string | null;
    sourceHistory?: string[];
    sourceHistoryIndex?: number;
  }) {
    try {
      const payload = await syncStudioEditLinkageState(request);
      setEditLinkage(payload);
      return payload;
    } catch (_editLinkageError) {
      return null;
    }
  }

  async function updateSessionCatalog(
    sessionId: string,
    patch: {
      rating?: number;
      pick_status?: 'unreviewed' | 'selected' | 'rejected' | 'hold';
      review_status?: 'intake' | 'culling' | 'proofing' | 'client_review' | 'print_ready' | 'delivered' | 'archived';
      keywords?: string[];
      proofing_profile?: string;
      print_profile?: string;
      client_collection?: string;
    },
  ) {
    setCatalogBusyKey(sessionId);
    try {
      const response = await fetch('/api/studio/catalog/session', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          output_root: sessionOutputRoot,
          ...patch,
        }),
      });
      await parseJson<unknown>(response);
      await refreshRecentSessions();
      setError(null);
    } catch (catalogError) {
      setError(catalogError instanceof Error ? catalogError.message : '세션 분류 메타데이터를 저장하지 못했습니다.');
    } finally {
      setCatalogBusyKey(null);
    }
  }

  async function applyBatchCatalogUpdate() {
    if (!selectedBatchSessionIds.length) {
      return;
    }
    setCatalogBusyKey('batch_catalog');
    try {
      const response = await fetch('/api/studio/catalog/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          output_root: sessionOutputRoot,
          session_ids: selectedBatchSessionIds,
          pick_status: batchCatalogPickStatus,
          review_status: batchCatalogReviewStatus,
          keywords: batchCatalogKeywords.split(',').map((item) => item.trim()).filter(Boolean),
          proofing_profile: batchProofingProfile.trim() || undefined,
          print_profile: batchPrintProfile.trim() || undefined,
          client_collection: batchClientCollection.trim() || undefined,
        }),
      });
      await parseJson<StudioCatalogBatchResponse>(response);
      await refreshRecentSessions();
      setError(null);
    } catch (catalogError) {
      setError(catalogError instanceof Error ? catalogError.message : '배치 분류 메타데이터를 저장하지 못했습니다.');
    } finally {
      setCatalogBusyKey(null);
    }
  }

  async function refreshOperations() {
    setOpsLoading(true);
    try {
      const eventParams = new URLSearchParams({
        output_root: sessionOutputRoot,
        limit: '20',
      });
      if (opsEventSourceFilter !== 'all') {
        eventParams.set('source', opsEventSourceFilter);
      }
      if (opsEventStatusFilter !== 'all') {
        eventParams.set('status', opsEventStatusFilter);
      }
      if (opsEventQuery.trim()) {
        eventParams.set('query', opsEventQuery.trim());
      }
      const [summaryResponse, rootsResponse, eventsResponse] = await Promise.all([
        fetch(`/api/studio/ops?output_root=${encodeURIComponent(sessionOutputRoot)}&limit=10`),
        fetch(`/api/studio/ops/roots?output_root=${encodeURIComponent(sessionOutputRoot)}&limit=8`),
        fetch(`/api/studio/ops/events?${eventParams.toString()}`),
      ]);
      const [summaryPayload, rootsPayload, eventsPayload] = await Promise.all([
        parseJson<StudioOpsSummary>(summaryResponse),
        parseJson<StudioOpsRootsResponse>(rootsResponse),
        parseJson<StudioOpsEventsResponse>(eventsResponse),
      ]);
      setOpsSummary(summaryPayload);
      setOpsRoots(rootsPayload.items);
      setOpsEvents(eventsPayload.items);
    } catch {
      setOpsSummary(null);
      setOpsRoots([]);
      setOpsEvents([]);
    } finally {
      setOpsLoading(false);
    }
  }

  async function openPodAndContinue() {
    setOpsActionBusy('pod_continue');
    setError(null);
    try {
      const healthy = await refreshRuntimeHealth();
      if (!healthy) {
        throw new Error('Pod 또는 백엔드가 아직 응답하지 않습니다. 로컬에서 `python app/scripts/runpod_provider_control.py resume`를 실행한 뒤 다시 계속 버튼을 눌러 주세요.');
      }
      const resumeResponse = await fetch('/api/studio/ops/provider/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          output_root: sessionOutputRoot,
          worker_mode: opsSummary?.worker_mode ?? 'external',
          poll_interval_seconds: documentHidden ? 4 : 2,
        }),
      });
      const providerSummary = await parseJson<StudioProviderSummary>(resumeResponse);
      const snapshot = loadStudioSessionRecovery()
        ?? providerCheckpointToRecoverySnapshot(providerSummary.checkpoint_session_snapshot);
      if (snapshot) {
        await restoreSessionSnapshot(snapshot);
      }
      await refreshOperations();
    } catch (resumeError) {
      setError(resumeError instanceof Error ? resumeError.message : 'Pod 복구를 이어가지 못했습니다.');
    } finally {
      setOpsActionBusy(null);
    }
  }

  async function checkpointAndStopPod() {
    setError(null);
    setOpsActionBusy('provider_pause');
    try {
      const snapshot = intakePlan ? {
        session_id: intakePlan.session_id,
        output_root: sessionOutputRoot,
        rawprep_job_id: rawprepJob?.job_id ?? null,
        studio_job_id: studioJob?.job_id ?? null,
        direct_path: directPath,
        compare_primary: comparePrimary,
        compare_candidate: compareCandidate,
        source_history: sourceHistory,
        source_history_index: sourceHistoryIndex,
        saved_versions: savedVersions.map((version) => ({
          id: version.id,
          label: version.label,
          path: version.path,
          created_at: version.createdAt,
        })),
      } : null;
      const response = await fetch('/api/studio/ops/provider/pause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          output_root: sessionOutputRoot,
          worker_mode: opsSummary?.worker_mode ?? 'external',
          poll_interval_seconds: documentHidden ? 4 : 2,
          reason: '운영 보드에서 상태 저장 후 Pod 일시정지를 요청했습니다.',
          session_snapshot: snapshot,
          stop_provider: true,
        }),
      });
      const providerSummary = await parseJson<StudioProviderSummary>(response);
      setOpsSummary((current) => (current ? {
        ...current,
        pod_state: 'stopping',
        pod_state_reason: providerSummary.reason ?? current.pod_state_reason,
        provider: providerSummary,
      } : current));
    } catch (pauseError) {
      setError(pauseError instanceof Error ? pauseError.message : 'Pod 상태 저장 후 중지 요청을 보내지 못했습니다.');
    } finally {
      setOpsActionBusy(null);
    }
  }

  async function startExternalWorker(outputRoots?: string[]) {
    setError(null);
    setOpsActionBusy('worker_start');
    try {
      const targetRoots = outputRoots?.length ? outputRoots : [sessionOutputRoot];
      const response = await fetch('/api/studio/ops/worker/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          output_root: targetRoots[0],
          output_roots: targetRoots.slice(1),
          mode: 'external',
          poll_interval_seconds: documentHidden ? 4 : 2,
        }),
      });
      await parseJson<StudioWorkerControlResponse>(response);
      await refreshOperations();
      window.setTimeout(() => {
        void refreshOperations();
      }, 600);
    } catch (workerError) {
      setError(workerError instanceof Error ? workerError.message : '외부 작업기를 시작하지 못했습니다.');
    } finally {
      setOpsActionBusy(null);
    }
  }

  async function stopWorkerQueue(outputRoots?: string[]) {
    setError(null);
    setOpsActionBusy('worker_stop');
    try {
      const targetRoots = outputRoots?.length ? outputRoots : [sessionOutputRoot];
      const response = await fetch('/api/studio/ops/worker/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          output_root: targetRoots[0],
          output_roots: targetRoots.slice(1),
          reason: 'manual hold from operations board',
        }),
      });
      await parseJson<StudioWorkerControlResponse>(response);
      await refreshOperations();
      window.setTimeout(() => {
        void refreshOperations();
      }, 600);
    } catch (workerError) {
      setError(workerError instanceof Error ? workerError.message : '작업기 중지 요청을 보내지 못했습니다.');
    } finally {
      setOpsActionBusy(null);
    }
  }

  async function retryVisibleDeadLetters() {
    if (!opsSummary?.dead_letters.length) {
      return;
    }
    setError(null);
    setOpsActionBusy('retry_dead_letters');
    try {
      const response = await fetch('/api/studio/ops/dead-letters/retry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          output_root: sessionOutputRoot,
          items: opsSummary.dead_letters.map((deadLetter) => ({
            job_id: deadLetter.job_id,
            task_type: deadLetter.task_type,
            output_root: deadLetter.output_root,
          })),
        }),
      });
      const payload = await parseJson<StudioDeadLetterRetryResponse>(response);
      if (!payload.queued) {
        setError('재시도할 오류 보관함 작업을 대기열에 넣지 못했습니다.');
      }
      await refreshOperations();
      await refreshRecentSessions();
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : '오류 보관함 일괄 재시도에 실패했습니다.');
    } finally {
      setOpsActionBusy(null);
    }
  }

  async function openRecentSession(session: RecentStudioSessionSummary) {
    await restoreSessionSnapshot({
      sessionId: session.session_id,
      outputRoot: session.output_root,
      rawprepJobId: session.rawprep_job_id ?? null,
      studioJobId: session.studio_job_id ?? null,
      directPath: null,
      comparePrimary: null,
      compareCandidate: null,
      sourceHistory: [],
      sourceHistoryIndex: -1,
      savedVersions: [],
    });
  }

  async function openDeadLetterSession(deadLetter: StudioDeadLetterSummary) {
    const matchedSession = recentSessions.find(
      (session) => session.session_id === deadLetter.session_id && session.output_root === deadLetter.output_root,
    );
    if (matchedSession) {
      await openRecentSession(matchedSession);
      return;
    }
    await restoreSessionSnapshot({
      sessionId: deadLetter.session_id,
      outputRoot: deadLetter.output_root,
      rawprepJobId: deadLetter.task_type === 'rawprep' ? deadLetter.job_id : null,
      studioJobId: deadLetter.task_type === 'studio' ? deadLetter.job_id : null,
      directPath: null,
      comparePrimary: null,
      compareCandidate: null,
      sourceHistory: [],
      sourceHistoryIndex: -1,
      savedVersions: [],
    });
  }

  async function retryDeadLetter(deadLetter: StudioDeadLetterSummary) {
    setError(null);
    setOpsActionBusy(`retry_${deadLetter.job_id}`);
    try {
      if (deadLetter.task_type === 'rawprep') {
        const response = await fetch(
          `/api/rawprep/jobs/${encodeURIComponent(deadLetter.job_id)}/retry?output_root=${encodeURIComponent(deadLetter.output_root)}`,
          { method: 'POST' },
        );
        const payload = await parseJson<RawprepJobRecord>(response);
        if (rawprepJob?.job_id === deadLetter.job_id) {
          setRawprepJob(payload);
          setRawprepBusy(true);
        }
      } else {
        const response = await fetch(
          `/api/jobs/${encodeURIComponent(deadLetter.job_id)}/retry?output_root=${encodeURIComponent(deadLetter.output_root)}`,
          { method: 'POST' },
        );
        const payload = await parseJson<StudioJobRecord>(response);
        if (studioJob?.job_id === deadLetter.job_id) {
          setStudioJob(payload);
          setStudioJobBusy(true);
        }
      }
      await refreshOperations();
      await refreshRecentSessions();
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : '실패 작업을 다시 큐에 넣지 못했습니다.');
    } finally {
      setOpsActionBusy(null);
    }
  }

  async function updateDeadLetterInvestigation(
    deadLetter: StudioDeadLetterSummary,
    updates: Partial<Pick<StudioDeadLetterSummary, 'assigned_to' | 'note' | 'investigation_status'>> & { acknowledged?: boolean },
  ) {
    setError(null);
    setOpsActionBusy(`investigate_${deadLetter.job_id}`);
    try {
      const response = await fetch('/api/studio/ops/dead-letters/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          output_root: deadLetter.output_root,
          history_path: deadLetter.history_path,
          assigned_to: updates.assigned_to,
          note: updates.note,
          acknowledged: updates.acknowledged,
          investigation_status: updates.investigation_status,
        }),
      });
      await parseJson<Record<string, unknown>>(response);
      await refreshOperations();
    } catch (investigationError) {
      setError(investigationError instanceof Error ? investigationError.message : '오류 보관함 조사 상태를 저장하지 못했습니다.');
    } finally {
      setOpsActionBusy(null);
    }
  }

  function saveDeliveryPresetProfile(
    preset: DeliveryPresetKey,
    scope: DeliveryPresetScope,
    label: string,
  ) {
    const profile = currentDeliveryPresetSnapshot(
      preset,
      `${label} ${deliveryPresetScopeTitle(scope)} ${new Date().toLocaleTimeString()}`,
      scope,
    );
    setDeliveryPresetProfiles((current) => [profile, ...current].slice(0, 16));
    setError(null);
  }

  function removeDeliveryPresetProfile(profileId: string) {
    setDeliveryPresetProfiles((current) => current.filter((profile) => profile.id !== profileId));
  }

  function exportDeliveryPresetProfile(profile: DeliveryPresetProfile) {
    exportJsonDownload(profile, `${profile.name.replace(/[^\w.-]+/g, '_') || 'delivery_preset'}.json`);
  }

  function exportDeliveryPresetLibrary() {
    exportJsonDownload(
      deliveryPresetProfiles,
      `delivery_preset_library_${new Date().toISOString().slice(0, 10)}.json`,
    );
  }

  async function importDeliveryPresetProfiles(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    try {
      const raw = await file.text();
      const imported = deserializeDeliveryPresetProfiles(JSON.parse(raw) as unknown);
      if (!imported.length) {
        throw new Error('저장된 프리셋이 없습니다.');
      }
      setDeliveryPresetProfiles((current) => {
        const merged = [...imported, ...current];
        const seen = new Set<string>();
        return merged.filter((profile) => {
          if (seen.has(profile.id)) {
            return false;
          }
          seen.add(profile.id);
          return true;
        }).slice(0, 16);
      });
      setError(null);
    } catch {
      setError('납품 프리셋 파일을 읽지 못했습니다.');
    } finally {
      event.target.value = '';
    }
  }

  async function applyDeliveryPresetProfile(profile: DeliveryPresetProfile) {
    if (profile.scope === 'batch') {
      await exportBatchDelivery(profile.preset);
      return;
    }
    await exportDeliveryPresetPackage(profile.preset, {
      label: profile.preset,
      metadata: {
        preset: profile.preset,
        preset_profile_id: profile.profileId,
        preset_profile_label: profile.profileLabel,
        saved_profile: profile.name,
      },
    });
  }

  function toggleRecentSessionExpanded(sessionId: string) {
    setExpandedRecentSessionIds((current) => (
      current.includes(sessionId)
        ? current.filter((value) => value !== sessionId)
        : [sessionId, ...current]
    ));
  }

  function toggleBatchSessionSelection(sessionId: string) {
    setSelectedBatchSessionIds((current) => (
      current.includes(sessionId)
        ? current.filter((value) => value !== sessionId)
        : [...current, sessionId]
    ));
  }

  function selectAllRecentSessionsForBatch() {
    setSelectedBatchSessionIds(recentSessions.map((session) => session.session_id));
  }

  function clearBatchSessionSelection() {
    setSelectedBatchSessionIds([]);
  }

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const snapshot = loadStudioSessionRecovery();
      if (!snapshot) {
        if (!cancelled) {
          setSessionRecoveryHydrated(true);
        }
        return;
      }

      await restoreSessionSnapshot(snapshot, { clearSavedSnapshotOnFailure: true });
      if (!cancelled) {
        setSessionRecoveryHydrated(true);
      }
    }

    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!sessionRecoveryHydrated) {
      return;
    }
    void refreshRecentSessions();
  }, [sessionOutputRoot, sessionRecoveryHydrated]);

  useEffect(() => {
    if (!sessionRecoveryHydrated) {
      return;
    }
    void refreshOperations();
  }, [sessionOutputRoot, sessionRecoveryHydrated]);

  useEffect(() => {
    if (!sessionRecoveryHydrated) {
      return;
    }
    if (!intakePlan?.session_id) {
      setSelectionState(null);
      return;
    }
    void refreshSelectionState(intakePlan.session_id, sessionOutputRoot);
  }, [intakePlan?.session_id, sessionOutputRoot, sessionRecoveryHydrated]);

  useEffect(() => {
    if (!sessionRecoveryHydrated) {
      return;
    }
    if (!intakePlan?.session_id) {
      setEditLinkage(null);
      return;
    }
    void refreshEditLinkageState(intakePlan.session_id, sessionOutputRoot);
  }, [intakePlan?.session_id, sessionOutputRoot, sessionRecoveryHydrated]);

  useEffect(() => {
    if (!sessionRecoveryHydrated) {
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshOperations();
    }, 160);
    return () => {
      window.clearTimeout(timer);
    };
  }, [opsEventQuery, opsEventSourceFilter, opsEventStatusFilter, sessionRecoveryHydrated]);

  useEffect(() => {
    if (!sessionRecoveryHydrated) {
      return;
    }
    if (!rawprepBusy && !studioJobBusy) {
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      if (cancelled) {
        return;
      }
      await refreshOperations();
    }, documentHidden ? 4500 : 2200);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [documentHidden, rawprepBusy, sessionRecoveryHydrated, studioJobBusy, studioJob?.status, rawprepJob?.status]);

  useEffect(() => {
    if (!sessionRecoveryHydrated || !currentRecentSessionSummary) {
      return;
    }
    setRecentSessions((current) => [
      currentRecentSessionSummary,
      ...current.filter((item) => item.session_id !== currentRecentSessionSummary.session_id),
    ].slice(0, 8));
  }, [currentRecentSessionSummary, sessionRecoveryHydrated]);

  useEffect(() => {
    setSelectedBatchSessionIds((current) => current.filter((sessionId) => recentSessions.some((session) => session.session_id === sessionId)));
  }, [recentSessions]);

  useEffect(() => {
    if (!currentRecentSessionSummary?.session_id) {
      return;
    }
    setExpandedRecentSessionIds((current) => (
      current.includes(currentRecentSessionSummary.session_id)
        ? current
        : [currentRecentSessionSummary.session_id, ...current]
    ));
  }, [currentRecentSessionSummary?.session_id]);

  useEffect(() => {
    if (!sessionRecoveryHydrated) {
      return;
    }
    if (!intakePlan) {
      clearStudioSessionRecovery();
      return;
    }
    saveStudioSessionRecovery({
      sessionId: intakePlan.session_id,
      outputRoot: sessionOutputRoot,
      rawprepJobId: rawprepJob?.job_id ?? null,
      studioJobId: studioJob?.job_id ?? null,
      directPath,
      comparePrimary,
      compareCandidate,
      sourceHistory,
      sourceHistoryIndex,
      savedVersions,
    });
  }, [
    compareCandidate,
    comparePrimary,
    directPath,
    intakePlan,
    rawprepJob?.job_id,
    savedVersions,
    sessionOutputRoot,
    sessionRecoveryHydrated,
    sourceHistory,
    sourceHistoryIndex,
    studioJob?.job_id,
  ]);

  useEffect(() => {
    const hasActiveWork = Boolean(
      rawprepBusy
      || studioJobBusy
      || opsSummary?.pending_queue
      || opsSummary?.delayed_queue
      || opsSummary?.running_queue,
    );
    if (!hasActiveWork) {
      return undefined;
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [opsSummary?.delayed_queue, opsSummary?.pending_queue, opsSummary?.running_queue, rawprepBusy, studioJobBusy]);

  useEffect(() => {
    if (!sourcePath) {
      return;
    }
    if (sourceHistoryCurrentPath === sourcePath) {
      return;
    }
    const trimmedHistory = sourceHistory.slice(0, sourceHistoryIndex + 1);
    if (trimmedHistory[trimmedHistory.length - 1] === sourcePath) {
      if (trimmedHistory.length !== sourceHistory.length) {
        setSourceHistory(trimmedHistory);
      }
      if (sourceHistoryIndex !== trimmedHistory.length - 1) {
        setSourceHistoryIndex(trimmedHistory.length - 1);
      }
      return;
    }
    setSourceHistory([...trimmedHistory, sourcePath]);
    setSourceHistoryIndex(trimmedHistory.length);
  }, [sourceHistory, sourceHistoryCurrentPath, sourceHistoryIndex, sourcePath]);

  useEffect(() => {
    if (!sessionRecoveryHydrated || !intakePlan?.session_id) {
      return;
    }
    void syncEditLinkageState({
      sessionId: intakePlan.session_id,
      outputRoot: sessionOutputRoot,
      currentSourcePath: sourcePath,
      activeTool: activeTool,
      studioJobId: studioJob?.job_id ?? null,
      sourceHistory,
      sourceHistoryIndex,
    });
  }, [
    activeTool,
    intakePlan?.session_id,
    selectionState?.updated_at,
    sessionOutputRoot,
    sessionRecoveryHydrated,
    sourceHistory,
    sourceHistoryIndex,
    sourcePath,
    studioJob?.job_id,
    studioJob?.updated_at,
  ]);

  useEffect(() => {
    if (!rawprepBusy || !rawprepJob?.job_id || !rawprepRequest) return;
    let cancelled = false;
    let timer: number | null = null;
    const jobId = rawprepJob.job_id;
    const outputRoot = rawprepRequest.output_root;
    function scheduleNext(status: string | undefined) {
      if (cancelled || !isRawprepActiveStatus(status)) return;
      timer = window.setTimeout(() => void poll(), rawprepPollDelay(status, documentHidden));
    }
    const poll = async () => {
      try {
        const response = await fetch(`/api/rawprep/jobs/${jobId}?output_root=${encodeURIComponent(outputRoot)}`);
        const payload = await parseJson<RawprepJobRecord>(response);
        if (cancelled) return;
        setRawprepJob(payload);
        if (payload.status === 'done') {
          setRawprepBusy(false);
          const recommended = rawprepRecommendedSource(payload);
          if (recommended) adoptWorkingSource(recommended);
        } else if (payload.status === 'cancelled') {
          setRawprepBusy(false);
        } else if (isRawprepFailureStatus(payload.status)) {
          setRawprepBusy(false);
          setError(payload.error ?? 'TriRaw 실행에 실패했습니다.');
        }
        scheduleNext(payload.status);
      } catch (pollError) {
        if (!cancelled) {
          setRawprepBusy(false);
          setError(pollError instanceof Error ? pollError.message : 'TriRaw 상태 조회에 실패했습니다.');
        }
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [documentHidden, rawprepBusy, rawprepJob?.job_id, rawprepRequest]);

  useEffect(() => {
    if (!rawprepJob?.job_id || rawprepJob.status !== 'done' || !rawprepRequest) {
      return;
    }
    const jobId = rawprepJob.job_id;
    const outputRoot = rawprepRequest.output_root;
    let cancelled = false;
    async function loadArtifacts() {
      try {
        const response = await fetch(`/api/rawprep/jobs/${jobId}/artifacts?output_root=${encodeURIComponent(outputRoot)}`);
        const payload = await parseJson<RawprepArtifactResponse>(response);
        if (!cancelled) {
          setRawprepArtifacts(payload);
        }
      } catch (_error) {
        if (!cancelled) {
          setRawprepArtifacts(null);
        }
      }
    }
    void loadArtifacts();
    return () => {
      cancelled = true;
    };
  }, [rawprepJob?.job_id, rawprepJob?.status, rawprepRequest]);

  useEffect(() => {
    if (!compareSources.length) {
      setComparePrimary(null);
      setCompareCandidate(null);
      return;
    }
    const singleRawComparePrimary = intakePlan?.entry_mode === 'direct_edit_raw'
      ? (
        singleRawSummary?.recoveryBaselinePath
        ?? singleRawSummary?.inputPreviewPath
        ?? sourcePath
        ?? compareSources[0].path
      )
      : (sourcePath ?? compareSources[0].path);
    const singleRawCompareCandidate = intakePlan?.entry_mode === 'direct_edit_raw'
      ? (singleRawSummary?.previewPath && singleRawSummary.previewPath !== singleRawComparePrimary
        ? singleRawSummary.previewPath
        : compareSources.find((item) => item.path !== singleRawComparePrimary)?.path ?? null)
      : (compareSources.find((item) => item.path !== (sourcePath ?? compareSources[0].path))?.path ?? null);
    setComparePrimary((current) => current && compareSources.some((item) => item.path === current) ? current : singleRawComparePrimary);
    setCompareCandidate((current) => {
      if (current && compareSources.some((item) => item.path === current) && current !== singleRawComparePrimary) {
        return current;
      }
      return singleRawCompareCandidate;
    });
  }, [compareSources, intakePlan?.entry_mode, singleRawSummary?.inputPreviewPath, singleRawSummary?.previewPath, sourcePath]);

  useEffect(() => {
    if (!sourcePath || !aiCapableTool || !sourcePreviewable) {
      setWorkflowPlan(null);
      setWorkflowBusy(false);
      return;
    }
    const cachedPlan = workflowPlanCacheRef.current.get(workflowPlanCacheKey);
    if (cachedPlan) {
      setWorkflowPlan(cachedPlan);
      setWorkflowBusy(false);
      return;
    }
    let cancelled = false;
    let timer: number | null = null;
    const controller = new AbortController();
    setWorkflowPlan(null);
    async function loadWorkflow() {
      if (cancelled || controller.signal.aborted) return;
      setWorkflowBusy(true);
      try {
        const response = await fetch('/api/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            tool: activeTool,
            seed_root: 'seed_bundle',
            session_id: intakePlan?.session_id,
            output_root: sessionOutputRoot,
          }),
        });
        const payload = await parseJson<WorkflowPlan>(response);
        if (!cancelled) {
          workflowPlanCacheRef.current.set(workflowPlanCacheKey, payload);
          setWorkflowPlan(payload);
        }
      } catch (workflowError) {
        if (cancelled || controller.signal.aborted) return;
        if (!cancelled) {
          setWorkflowPlan(null);
          setError(workflowError instanceof Error ? workflowError.message : '도구 워크플로 확인에 실패했습니다.');
        }
      } finally {
        if (!cancelled && !controller.signal.aborted) setWorkflowBusy(false);
      }
    }
    timer = window.setTimeout(() => void loadWorkflow(), workflowPlanDebounceDelay(documentHidden));
    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
      controller.abort();
    };
  }, [aiCapableTool, activeTool, documentHidden, intakePlan?.session_id, sessionOutputRoot, sourcePath, sourcePreviewable, workflowPlanCacheKey]);

  useEffect(() => {
    if (!studioJobBusy || !studioJob?.job_id) return;
    let cancelled = false;
    let timer: number | null = null;
    const jobId = studioJob.job_id;
    function scheduleNext(status: string | undefined) {
      if (cancelled || !isStudioJobActiveStatus(status)) return;
      timer = window.setTimeout(() => void poll(), studioJobPollDelay(status, documentHidden));
    }
    const poll = async () => {
      try {
        const response = await fetch(`/api/jobs/${jobId}?output_root=${encodeURIComponent(sessionOutputRoot)}`);
        const payload = await parseJson<StudioJobRecord>(response);
        if (cancelled) return;
        setStudioJob(payload);
        if (payload.status === 'done') {
          setStudioJobBusy(false);
          const firstOutput = payload.outputs.find((output) => isPreviewablePath(output.path));
          if (firstOutput) {
            setCompareCandidate(firstOutput.path);
          }
        } else if (payload.status === 'cancelled') {
          setStudioJobBusy(false);
        } else if (payload.status === 'error' || payload.status === 'blocked') {
          setStudioJobBusy(false);
          setError(payload.error ?? '이 AI 도구가 스튜디오 작업을 끝내지 못했습니다.');
        }
        scheduleNext(payload.status);
      } catch (pollError) {
        if (!cancelled) {
          setStudioJobBusy(false);
          setError(pollError instanceof Error ? pollError.message : 'AI 작업 상태를 새로 고치지 못했습니다.');
        }
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [documentHidden, sessionOutputRoot, studioJob?.job_id, studioJobBusy]);

  const toast = useMemo(() => {
    if (error) return { tone: 'error' as const, message: error };
    if (opsActionBusy) return { tone: 'info' as const, message: '운영 제어 변경을 적용하고 있습니다.' };
    if (packageBusy) return { tone: 'info' as const, message: '세션 패키지를 export 폴더로 정리하고 있습니다.' };
    if (exportBusy) return { tone: 'info' as const, message: '현재 결과물을 export 폴더로 저장하고 있습니다.' };
    if (intakeBusy) return { tone: 'info' as const, message: '입력 파일을 확인하고 있습니다.' };
    if (rawprepBusy) return { tone: 'info' as const, message: `TriRaw 실행 중입니다. 현재 단계: ${formatSessionStep(rawprepJob?.current_step) ?? '준비 중'}` };
    if (studioJobBusy) return { tone: 'info' as const, message: `${toolMeta.label} 작업을 실행 중입니다. 현재 단계: ${formatSessionStep(studioJob?.current_step) ?? '큐 대기 중'}` };
    if (studioJob?.status === 'done') return { tone: 'success' as const, message: `${toolMeta.label} 결과가 준비되었습니다.` };
    if (rawprepJob?.status === 'done') {
      const reason = rawprepJob.group_reports?.[0]?.fallback_reason;
      return { tone: 'success' as const, message: reason ? `TriRaw 완료: ${reason} 기준 결과를 선택했습니다.` : 'TriRaw 완료. 결과를 작업 소스로 사용할 수 있습니다.' };
    }
    if (lastPackagePath) return { tone: 'success' as const, message: `세션 패키지가 준비되었습니다: ${lastPackagePath}` };
    if (lastExportPath) return { tone: 'success' as const, message: `결과가 저장되었습니다: ${lastExportPath}` };
    if (intakePlan?.entry_mode === 'rawprep_bracket' && !sourcePath) {
      return { tone: 'info' as const, message: '3장 RAW 브라켓을 찾았습니다. TriRaw 또는 직접 보정을 선택하세요.' };
    }
    if (intakePlan?.entry_mode === 'direct_edit_raw' && singleRawSummary?.previewPath) {
      return { tone: 'success' as const, message: '단일 RAW 기본 결과가 준비되었습니다.' };
    }
    if (sourcePath) return { tone: 'success' as const, message: '작업 소스가 준비되었습니다.' };
    return { tone: 'info' as const, message: '사진을 올려 작업을 시작하세요.' };
  }, [error, exportBusy, intakeBusy, intakePlan?.entry_mode, lastExportPath, lastPackagePath, opsActionBusy, packageBusy, rawprepBusy, rawprepJob, singleRawSummary?.previewPath, sourcePath, studioJob, studioJobBusy, toolMeta.label]);

  const toolItems = useMemo<ToolRailItem[]>(() => tools.map((tool) => ({ ...tool, disabled: !sourcePath })), [sourcePath]);

  const sections = useMemo<PropertyPanelSection[]>(() => {
    const base: PropertyPanelSection[] = [
      {
        title: '세션 상태',
        description: '세션 상태를 확인하세요.',
        items: [
          { label: '단계', value: stages.find((stage) => stage.key === stageKey)?.label ?? stageKey },
          { label: '작업 소스', value: sourcePath ?? '아직 선택되지 않았습니다.', tone: sourcePath ? 'success' : 'warning' },
          { label: '선택 도구', value: toolMeta.label },
        ],
      },
    ];
    if (intakePlan) {
      base.push({
        title: '입력 분석 결과',
        description: '권장 시작 경로입니다.',
        items: [
          { label: '권장 진입 모드', value: sessionEntryLabel(intakePlan.entry_mode), tone: intakePlan.entry_mode === 'rawprep_bracket' ? 'success' : 'default' },
          { label: '대체 모드', value: intakePlan.alternate_modes.length ? intakePlan.alternate_modes.map(sessionEntryLabel).join(', ') : '없음' },
          { label: '세션 루트', value: intakePlan.session_root },
        ],
      });
    }
    if (singleRawSummary) {
      base.push({
        title: 'SingleRaw 처리 요약',
        description: '단일 RAW 기본 결과입니다.',
        items: [
          { label: '처리 상태', value: singleRawSummary.statusLabel, tone: singleRawSummary.statusTone },
          { label: '처리 모드', value: `${singleRawSummary.modeLabel} · ${singleRawSummary.qualityPresetLabel}` },
          { label: '런타임 프로파일', value: singleRawSummary.runtimeProfileLabel },
          { label: '입력 기준', value: singleRawSummary.inputPreviewPath ? basenameFromPath(singleRawSummary.inputPreviewPath) : '아직 없음', tone: singleRawSummary.inputPreviewPath ? 'default' : 'warning' },
          { label: '복원 기준', value: singleRawSummary.recoveryBaselinePath ? basenameFromPath(singleRawSummary.recoveryBaselinePath) : '아직 없음', tone: singleRawSummary.recoveryBaselinePath ? 'success' : 'default' },
          { label: '기본 결과', value: singleRawSummary.previewPath ? basenameFromPath(singleRawSummary.previewPath) : '아직 없음', tone: singleRawSummary.previewPath ? 'success' : 'warning' },
          { label: '노이즈 보기', value: singleRawSummary.noiseMapPath ? basenameFromPath(singleRawSummary.noiseMapPath) : '아직 없음', tone: singleRawSummary.noiseMapPath ? 'success' : 'default' },
          { label: '저조도 보기', value: singleRawSummary.lowlightMapPath ? basenameFromPath(singleRawSummary.lowlightMapPath) : '아직 없음', tone: singleRawSummary.lowlightMapPath ? 'success' : 'default' },
          { label: '처리 시간', value: singleRawSummary.timingSummary },
          { label: '복원 리포트', value: singleRawSummary.recoveryReportSummary },
          { label: '광학 보정 보기', value: singleRawSummary.opticalSummary },
          { label: '아티팩트 억제', value: singleRawSummary.artifactSuppressionSummary },
          { label: '안전 대체 경로', value: singleRawSummary.safetyFallbackSummary },
          { label: '처리 요약', value: `${singleRawSummary.modeSummary} ${singleRawSummary.processingSummary}` },
        ],
        actions: [
          {
            label: singleRawSummary.isCurrentSource ? '기본 결과를 작업 소스로 사용 중' : '기본 결과를 작업 소스로 사용',
            onClick: () => {
              if (singleRawSummary.previewPath) {
                adoptWorkingSource(singleRawSummary.previewPath);
              }
            },
            disabled: !singleRawSummary.previewPath || singleRawSummary.isCurrentSource,
          },
          {
            label: '입력 기준을 유지 후보로',
            onClick: () => {
              if (singleRawSummary.inputPreviewPath) {
                setComparePrimary(singleRawSummary.inputPreviewPath);
              }
            },
            disabled: !singleRawSummary.inputPreviewPath,
          },
          {
            label: '기본 결과를 대안 후보로',
            onClick: () => {
              if (singleRawSummary.previewPath) {
                setCompareCandidate(singleRawSummary.previewPath);
              }
            },
            disabled: !singleRawSummary.previewPath,
          },
          {
            label: '노이즈 보기를 대안 후보로',
            onClick: () => {
              if (singleRawSummary.noiseMapPath) {
                setCompareCandidate(singleRawSummary.noiseMapPath);
              }
            },
            disabled: !singleRawSummary.noiseMapPath,
          },
        ],
      });
    }
    if (rawprepJob?.group_reports?.[0]) {
      const report = rawprepJob.group_reports[0];
      const dreamispHandoff = report.dreamisp_handoff;
      base.push({
        title: 'TriRaw 실행 결과',
        description: 'TriRaw 결과와 진단입니다.',
        items: [
          { label: '현재 결과', value: formatTriRawRecommendedArtifact(report.recommended_artifact), tone: 'success' },
          { label: 'DreamISP 상태', value: formatSessionStep(dreamispHandoff?.materialization_status) ?? '없음', tone: dreamispHandoff?.materialization_status === 'preview_rendered' ? 'success' : 'default' },
          { label: 'DreamISP 편집 소스', value: dreamispHandoff?.recommended_editable_source_path ?? '없음' },
          { label: '합성 백엔드', value: report.merge_backend ?? '정보 없음' },
          {
            label: 'RAW 결과 목표',
            value: rawRestorationGoalLabel(normalizeRawRestorationGoal(report.restoration_goal, rawRestorationGoalOptions), rawRestorationGoalOptions),
            tone: propertyPanelTone(rawRestorationGoalOptions.find((option) => option.id === report.restoration_goal)?.tone),
          },
          { label: '공격 복원 후보', value: report.aggressive_restore_candidate_path ?? '없음', tone: report.aggressive_restore_candidate_path ? 'warning' : 'default' },
          { label: '카메라 프로파일', value: formatCameraProfileLabel(report.effective_camera_profile) },
          { label: '대체 이유', value: formatTriRawFallbackReason(report.fallback_reason), tone: report.fallback_reason ? 'warning' : 'default' },
        ],
      });
    }
    base.push({
      title: '도구 준비 상태',
      description: '선택한 도구의 실행 상태입니다.',
      items: [
    { label: '워크플로 상태', value: aiToolStatusText(workflowPlan, workflowBusy, activeTool, Boolean(sourcePath), sourcePreviewable, podStatus), tone: workflowPlan?.execution_ready && aiPodReady ? 'success' : sourcePath && aiCapableTool ? 'warning' : 'default' },
        { label: '즉시 로드 모델', value: workflowPlan?.warm_models?.length ? workflowPlan.warm_models.join(', ') : '없음' },
        { label: '추가 로드 모델', value: workflowPlan?.cold_models?.length ? workflowPlan.cold_models.join(', ') : '없음' },
      ],
    });
    base.push({
      title: '품질 자동화',
      description: 'Qwen 판단과 품질 검사 상태입니다.',
      items: qualityAutomationPolicy ? [
        { label: '판단 모델', value: qualityAutomationPolicy.primary_local_model, tone: 'success' },
        { label: '모델 저장소', value: qualityAutomationPolicy.primary_local_repo },
        { label: '클라우드 fallback', value: qualityAutomationPolicy.cloud_fallback_enabled ? '사용' : '사용 안 함', tone: qualityAutomationPolicy.cloud_fallback_enabled ? 'warning' : 'success' },
        { label: '판정', value: qualityAutomationPolicy.verdicts.join(', ') },
        { label: '자동화 레이어', value: qualityAutomationPolicy.runtime_layers.join(', ') },
        { label: '튜닝 루프', value: `${qualityAutomationPolicy.tuning_version} · 제안 전용`, tone: 'success' },
      ] : [
        { label: '정책 상태', value: qualityAutomationPolicyError ?? '백엔드 정책 확인 중', tone: qualityAutomationPolicyError ? 'warning' : 'default' },
      ],
    });
    if (studioJob) {
      base.push({
        title: 'AI 작업 상태',
        description: 'AI 작업 진행 상태입니다.',
        items: [
          { label: '작업 상태', value: formatSessionStep(studioJob.status) ?? studioJob.status, tone: studioJob.status === 'done' ? 'success' : studioJob.status === 'error' || studioJob.status === 'blocked' ? 'warning' : 'default' },
          { label: '현재 단계', value: formatSessionStep(studioJob.current_step) ?? '계획 수립' },
          { label: '생성 결과', value: `${studioJob.outputs.length}개 파일` },
          { label: '작업 소스', value: studioJob.source_path ?? '없음' },
        ],
      });
    }
    if (selectionState) {
      base.push({
        title: '현재 선택 기준',
        description: '선택 마스크를 조정합니다.',
        items: [
          { label: '기준 마스크', value: selectionSourceLabel(selectionState), tone: 'success' },
          { label: '선택 범위', value: selectionCoverageLabel(selectionState.coverage_ratio), tone: 'success' },
          { label: '미세 조정', value: `임계값 ${selectionControls.threshold} | 확장/수축 ${selectionControls.expandPixels >= 0 ? '+' : ''}${selectionControls.expandPixels}px | 경계 ${selectionControls.featherRadius}px` },
          { label: '기준 작업 소스', value: selectionState.source_asset_path ?? '없음', tone: selectionSourceMismatch ? 'warning' : 'default' },
          { label: '선택 요약', value: selectionSourceMismatch ?? selectionState.summary },
        ],
        actions: [
          {
            label: selectionBusy ? '선택 미리보기 갱신 중...' : '선택 미리보기 갱신',
            onClick: () => void applySelectionFromMask(selectionState.source_mask_path),
            disabled: selectionBusy || !sourcePath,
          },
        ],
      });
    }
    if (studioJob && (backgroundCutoutOutputs.length || generatedCandidateOutputs.length || reusableMaskOutputs.length)) {
      base.push({
        title: generatedCandidateGroupLabel,
        description: `${generatedCandidateGroupLabel} 후보를 비교하고 채택합니다.`,
        items: [
          { label: '최근 편집 도구', value: toolLabelFromKey(studioJob.tool), tone: 'success' },
          { label: '배경 분리 결과', value: backgroundCutoutOutputs.length ? `${backgroundCutoutOutputs.length}개` : '없음', tone: backgroundCutoutOutputs.length ? 'success' : 'default' },
          { label: generatedCandidateGroupLabel, value: generatedCandidateOutputs.length ? `${generatedCandidateOutputs.length}개` : '아직 없음', tone: generatedCandidateOutputs.length ? 'success' : 'default' },
          { label: '재사용 마스크', value: reusableMaskOutputs.length ? `${reusableMaskOutputs.length}개` : '아직 없음', tone: reusableMaskOutputs.length ? 'success' : 'default' },
          {
            label: '후보 비교',
            value: editCandidateCompareSourceCount
              ? `편집 후보 ${editCandidateCompareSourceCount}개를 비교 후보로 지정할 수 있습니다.`
              : '비교할 편집 후보가 아직 없습니다.',
          },
        ],
      });
    }
    if (sourcePath) {
      base.push({
        title: '편집 작업 흐름',
        description: '마스크, 생성 편집, 보정, 비교, 내보내기 상태입니다.',
        items: [
          { label: '현재 편집 단계', value: stageKey === 'finish' ? '검토 및 출력 단계' : '편집 작업 단계', tone: 'success' },
          {
            label: '마스크 자산',
            value: reusableMaskOutputs.length
              ? `재사용 가능한 마스크 ${reusableMaskOutputs.length}개 준비${selectionState ? ' | 현재 선택 기준 유지 중' : ''}`
              : '배경 제거 결과에서 만든 마스크를 재사용할 수 있습니다.',
            tone: reusableMaskOutputs.length ? 'success' : 'default',
          },
          { label: '생성 편집 경로', value: '배경 교체와 오브젝트 편집 뒤에도 같은 작업 소스로 리터치와 조명 보정 단계로 다시 돌아갈 수 있습니다.' },
          { label: '비교·기록·내보내기', value: `비교 소스 ${compareSources.length}개 | 저장된 버전 ${savedVersions.length}개 | 패키지 후보 ${exportPackageItems.length}개` },
        ],
      });
    }
    if (rawprepJob || studioJob) {
      base.push({
        title: '재시도 / 복구',
        description: '중단된 작업을 다시 실행합니다.',
        actions: [
          { label: 'TriRaw 다시 실행', onClick: () => void retryRawprep(), disabled: !rawprepJob || isRawprepActiveStatus(rawprepJob.status) },
          { label: 'AI 다시 실행', onClick: () => void retryStudioJob(), disabled: !studioJob || isStudioJobActiveStatus(studioJob.status) },
        ],
      });
    }
    if (intakePlan?.dreamisp_plan) {
      const dreamispPlan = intakePlan.dreamisp_plan as Record<string, unknown>;
      base.push({
        title: 'DreamISP 미리보기',
        description: 'DreamISP 미리보기 조정값입니다.',
        items: [
          {
            label: '렌더 상태',
            value: formatSessionStep(String(dreamispPlan.materialization_status ?? 'planned')) ?? '계획 수립',
            tone: String(dreamispPlan.materialization_status ?? '') === 'preview_rendered' ? 'success' : 'default',
          },
          { label: '렌더 백엔드', value: String(dreamispPlan.render_backend ?? 'dreamisp_lite_preview_v1') },
          { label: 'WB', value: `${dreamispControls.temperatureDelta.toFixed(0)} / ${dreamispControls.tintDelta.toFixed(0)}` },
          { label: '톤', value: `노출 ${dreamispControls.exposureEv.toFixed(1)}EV / 대비 ${dreamispControls.contrast.toFixed(0)}` },
          { label: '디테일', value: `선명도 ${dreamispControls.clarity.toFixed(0)}` },
          { label: '현재 편집 소스', value: intakePlan.editable_asset_path ?? '없음' },
        ],
        actions: [
          {
            label: dreamispBusy ? 'DreamISP 적용 중...' : 'DreamISP 미리보기 적용',
            onClick: () => void applyDreamispPreview(),
            disabled: dreamispBusy,
          },
        ],
      });
    }
    base.push({
      title: 'RAW 복원 정책',
      description: 'manifest에서 불러온 RAW 결과 목표입니다.',
      items: rawRestorationPolicy ? [
        { label: '계약', value: rawRestorationPolicy.contract_id, tone: 'success' },
        { label: '기본 목표', value: rawRestorationGoalLabel(rawRestorationPolicy.default_goal, rawRestorationGoalOptions), tone: 'success' },
        { label: '선택지', value: rawRestorationGoalOptions.map((option) => option.label).join(', ') },
        { label: '프레임', value: rawRestorationPolicy.accepted_frame_counts.length ? rawRestorationPolicy.accepted_frame_counts.join(', ') : '3, 9' },
      ] : [
        { label: '정책 상태', value: rawRestorationPolicyError ?? 'RAW 정책 확인 중', tone: rawRestorationPolicyError ? 'warning' : 'default' },
      ],
    });
    base.push({
      title: '작업 히스토리',
      description: '되돌리기와 버전 저장입니다.',
      items: [
        { label: '히스토리 깊이', value: sourceHistory.length ? `${sourceHistoryIndex + 1} / ${sourceHistory.length}` : '기록 없음' },
        { label: '저장된 버전', value: `${savedVersions.length}개` },
        { label: '패키지 후보 파일', value: `${exportPackageItems.length}개` },
      ],
      actions: [
        { label: '되돌리기', onClick: undoWorkingSource, disabled: !canUndoWorkingSource },
        { label: '다시 적용', onClick: redoWorkingSource, disabled: !canRedoWorkingSource },
        { label: '현재 버전 저장', onClick: saveCurrentVersion, disabled: !sourcePath },
      ],
    });
    base.push({
      title: '빠른 액션',
      description: '지금 실행할 수 있는 작업입니다.',
      actions: [
        { label: '입력 다시 분석', onClick: () => void analyze(), disabled: !files.length || intakeBusy },
        { label: 'TriRaw 실행', onClick: () => void runRawprep(), disabled: !rawprepRequest || rawprepBusy },
        { label: `${toolMeta.label} 실행`, onClick: () => void runStudioJob(), disabled: !canRunStudioJob },
        { label: '대안 후보를 작업 소스로 사용', onClick: () => void acceptCompareCandidate(), disabled: !compareCandidate || compareCandidate === sourcePath },
      ],
    });
    base.push({
      title: '최근 진행',
      description: '최근 작업 상태입니다.',
      items: [
        { label: '입력 분석', value: intakePlan ? `${sessionEntryLabel(intakePlan.entry_mode)}로 결정` : '아직 시작 전', tone: intakePlan ? 'success' : 'default' },
        { label: 'TriRaw 상태', value: rawprepJob ? (formatSessionStep(rawprepJob.status) ?? rawprepJob.status) : rawprepRequest ? '실행 대기' : '대상 없음', tone: rawprepJob?.status === 'done' ? 'success' : rawprepBusy ? 'warning' : 'default' },
        { label: 'AI 작업 상태', value: studioJob ? (formatSessionStep(studioJob.status) ?? studioJob.status) : aiCapableTool && sourcePath ? '실행 대기' : '아직 준비 전', tone: studioJob?.status === 'done' ? 'success' : studioJobBusy ? 'warning' : 'default' },
        { label: '비교 소스 수', value: `${compareSources.length}개` },
      ],
    });
    if (workspaceMode === 'advanced' && compareSources.length) {
      base.push({
        title: '비교 뷰',
        description: '기준 이미지와 후보 이미지입니다.',
        items: [
          { label: '유지 후보', value: comparePrimary ?? '아직 선택되지 않았습니다.' },
          { label: '대안 후보', value: compareCandidate ?? '비교 대상 없음' },
          { label: '비교 가능한 소스', value: `${compareSources.length}개` },
        ],
      });
    }
    return base;
  }, [activeTool, aiCapableTool, aiPodReady, backgroundCutoutOutputs.length, canRedoWorkingSource, canRunStudioJob, canUndoWorkingSource, compareCandidate, comparePrimary, compareSources.length, dreamispBusy, dreamispControls, editCandidateCompareSourceCount, exportPackageItems.length, files.length, generatedCandidateGroupLabel, generatedCandidateOutputs.length, intakeBusy, intakePlan, podStatus, qualityAutomationPolicy, qualityAutomationPolicyError, rawRestorationGoalOptions, rawRestorationPolicy, rawRestorationPolicyError, rawprepBusy, rawprepJob, rawprepRequest, reusableMaskOutputs.length, savedVersions.length, selectionBusy, selectionControls.expandPixels, selectionControls.featherRadius, selectionControls.threshold, selectionSourceMismatch, selectionState, sessionOutputRoot, singleRawSummary, sliders, sourceHistory.length, sourceHistoryIndex, sourcePath, sourcePreviewable, stageKey, studioJob, studioJobBusy, toolMeta.label, workflowBusy, workflowPlan, workspaceMode]);

  const propertySections = useMemo<PropertyPanelSection[]>(
    () => (
      isAdvancedWorkspace
        ? sections
        : sections.filter((section) => [
          '세션 상태',
          '입력 분석 결과',
          'SingleRaw 처리 요약',
          'TriRaw 실행 결과',
          '현재 선택 기준',
          generatedCandidateGroupLabel,
          '편집 작업 흐름',
          '도구 준비 상태',
          'RAW 복원 정책',
          '품질 자동화',
          'AI 작업 상태',
          '최근 진행',
        ].includes(section.title))
    ),
    [generatedCandidateGroupLabel, isAdvancedWorkspace, sections],
  );

  const focusHighlights = useMemo(
    () => [
      {
        label: '권장 진입',
        value: intakePlan ? sessionEntryLabel(intakePlan.entry_mode) : '입력 분석 전',
        tone: intakePlan?.entry_mode === 'rawprep_bracket' ? '#edf7f1' : '#f8fafc',
        border: intakePlan?.entry_mode === 'rawprep_bracket' ? '#b9ddc6' : '#dfe4eb',
      },
      {
        label: '작업 소스',
        value: sourcePath ? basenameFromPath(sourcePath) : '아직 미선택',
        tone: sourcePath ? '#eef4ff' : '#f8fafc',
        border: sourcePath ? '#c8d5ea' : '#dfe4eb',
      },
      intakePlan?.entry_mode === 'direct_edit_raw'
        ? {
          label: 'SingleRaw',
          value: singleRawSummary?.statusLabel ?? '기본 계획 준비 중',
          tone: singleRawSummary?.statusTone === 'success' ? '#edf7f1' : singleRawSummary?.statusTone === 'warning' ? '#fff7e8' : '#f8fafc',
          border: singleRawSummary?.statusTone === 'success' ? '#b9ddc6' : singleRawSummary?.statusTone === 'warning' ? '#f1dfc6' : '#dfe4eb',
        }
        : {
          label: 'TriRaw',
          value: rawprepJob ? (formatSessionStep(rawprepJob.status) ?? rawprepJob.status) : rawprepRequest ? '실행 가능' : '대상 없음',
          tone: rawprepJob?.status === 'done' ? '#edf7f1' : rawprepBusy ? '#fff7e8' : '#f8fafc',
          border: rawprepJob?.status === 'done' ? '#b9ddc6' : rawprepBusy ? '#f1dfc6' : '#dfe4eb',
        },
      {
        label: 'AI 실행',
        value: studioJob ? (formatSessionStep(studioJob.status) ?? studioJob.status) : canRunStudioJob ? '실행 가능' : aiCapableTool && sourcePath ? '준비 중' : '대기',
        tone: studioJob?.status === 'done' ? '#edf7f1' : studioJobBusy ? '#fff7e8' : '#f8fafc',
        border: studioJob?.status === 'done' ? '#b9ddc6' : studioJobBusy ? '#f1dfc6' : '#dfe4eb',
      },
    ],
    [aiCapableTool, canRunStudioJob, intakePlan, rawprepBusy, rawprepJob, rawprepRequest, singleRawSummary, sourcePath, studioJob, studioJobBusy],
  );
  const queueAttention = useMemo(() => {
    if (!opsSummary) {
      return null;
    }
    const queuedCount = opsSummary.queued_jobs + opsSummary.pending_queue + opsSummary.delayed_queue;
    if (opsSummary.worker_stop_requested_at && queuedCount > 0) {
      return {
        title: '처리 대기열이 일시중지된 상태입니다',
        description: `현재 ${queuedCount}개의 작업이 대기 상태로 남아 있습니다. ${opsSummary.worker_stop_requested_reason ?? '이전에 작업기 중지 요청이 들어와'} 자동 실행이 멈췄습니다.`,
        tone: '#fff7e8',
        border: '#f1dfc6',
        actionLabel: '대기열 재개',
      };
    }
    if (!opsSummary.active_queue_workers && queuedCount > 0) {
      return {
        title: '대기 작업이 있지만 작업기가 없습니다',
        description: `현재 ${queuedCount}개 작업이 대기 중입니다. 활성 작업기 신호가 없습니다.`,
        tone: '#fff5f5',
        border: '#f3c8c8',
        actionLabel: '작업기 시작',
      };
    }
    return null;
  }, [opsSummary]);

  useEffect(() => {
    if (!compareHotkeysEnabled) {
      return;
    }

    const paths = compareSources.map((item) => item.path);
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || isTypingTarget(event.target)) {
        return;
      }

      if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
        event.preventDefault();
        const direction = event.key === 'ArrowRight' ? 1 : -1;
        if (event.shiftKey) {
          setComparePrimary((current) => cycleComparePath(paths, current, direction, compareCandidate));
        } else {
          setCompareCandidate((current) => cycleComparePath(paths, current, direction, comparePrimary));
        }
        return;
      }

      const normalizedKey = event.key.toLowerCase();
      if (normalizedKey === 'a' && compareCandidate) {
        event.preventDefault();
        void acceptCompareCandidate();
        return;
      }
      if (normalizedKey === 's' && compareCandidate) {
        event.preventDefault();
        setComparePrimary(compareCandidate);
        return;
      }
      if (normalizedKey === 'x' && comparePrimary && compareCandidate) {
        event.preventDefault();
        setComparePrimary(compareCandidate);
        setCompareCandidate(comparePrimary);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [activeTool, compareCandidate, compareHotkeysEnabled, comparePrimary, compareSources, intakePlan?.session_id, sessionOutputRoot, workspaceMode]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) {
        return;
      }
      const isModifierPressed = event.ctrlKey || event.metaKey;
      if (!isModifierPressed) {
        return;
      }
      const normalizedKey = event.key.toLowerCase();
      if (normalizedKey === 'z' && !event.shiftKey) {
        if (!canUndoWorkingSource) {
          return;
        }
        event.preventDefault();
        undoWorkingSource();
        return;
      }
      if ((normalizedKey === 'z' && event.shiftKey) || normalizedKey === 'y') {
        if (!canRedoWorkingSource) {
          return;
        }
        event.preventDefault();
        redoWorkingSource();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [canRedoWorkingSource, canUndoWorkingSource, sourceHistory, sourceHistoryIndex]);

  function clearPipelineState() {
    setIntakePlan(null);
    setRawprepJob(null);
    setRawprepArtifacts(null);
    setWorkflowPlan(null);
    setStudioJob(null);
    setSelectionState(null);
    setEditLinkage(null);
    setDirectPath(null);
    setComparePrimary(null);
    setCompareCandidate(null);
    setSourceHistory([]);
    setSourceHistoryIndex(-1);
    setSavedVersions([]);
    setSelectionControls(defaultSelectionControls());
    setError(null);
    setIntakeBusy(false);
    setRawprepBusy(false);
    setWorkflowBusy(false);
    setStudioJobBusy(false);
    setSelectionBusy(false);
    setExportBusy(false);
    setLastExportPath(null);
    setPackageBusy(false);
    setLastPackagePath(null);
  }

  function applySelectedFiles(nextFiles: File[]) {
    const validFiles = dedupeUploadFiles(nextFiles.filter(isSupportedUploadFile));
    uploadDragDepthRef.current = 0;
    setUploadDragActive(false);
    setSessionOutputRootOverride(null);
    clearPipelineState();
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    if (!validFiles.length) {
      setFiles([]);
      setError('RAW, JPG, PNG, TIFF, WebP, HEIC 파일만 불러올 수 있습니다.');
      return;
    }
    setFiles(validFiles);
  }

  function removeSelectedFile(fileKey: string) {
    clearPipelineState();
    setFiles((current) => current.filter((file) => uploadFileKey(file) !== fileKey));
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }

  function handleUploadDragEnter(event: React.DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();
    uploadDragDepthRef.current += 1;
    setUploadDragActive(true);
  }

  function handleUploadDragOver(event: React.DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = 'copy';
  }

  function handleUploadDragLeave(event: React.DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();
    uploadDragDepthRef.current = Math.max(0, uploadDragDepthRef.current - 1);
    if (uploadDragDepthRef.current === 0) {
      setUploadDragActive(false);
    }
  }

  function handleUploadDrop(event: React.DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();
    applySelectedFiles(Array.from(event.dataTransfer.files ?? []));
  }

  async function analyze() {
    if (!files.length) {
      setError('RAW 또는 JPG 파일을 올려 주세요.');
      return;
    }
    setError(null);
    setIntakeBusy(true);
    setRawprepJob(null);
    setRawprepArtifacts(null);
    setStudioJob(null);
    setStudioJobBusy(false);
    setWorkflowPlan(null);
    setDirectPath(null);
    setComparePrimary(null);
    setCompareCandidate(null);
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file, file.name));
    formData.append('session_id', generateSessionId());
    formData.append('output_root', 'outputs');
    formData.append('entry_preference', entryPreference);
    formData.append('camera_profile', cameraProfile);
    formData.append('quality_preset', qualityPreset);
    formData.append('single_raw_mode_preference', singleRawModePreference);
    formData.append('restoration_goal', rawRestorationGoal);
    try {
      const response = await fetch('/api/studio/intake/upload', { method: 'POST', body: formData });
      const payload = await parseJson<IntakePlan>(response);
      setSessionOutputRootOverride('outputs');
      setIntakePlan(payload);
      if (!payload.rawprep_request && payload.editable_asset_path) setDirectPath(payload.editable_asset_path);
    } catch (analyzeError) {
      setIntakePlan(null);
      setError(analyzeError instanceof Error ? analyzeError.message : '입력 분석에 실패했습니다.');
    } finally {
      setIntakeBusy(false);
    }
  }

  async function runRawprep() {
    if (!rawprepRequest) {
      setError('TriRaw를 실행하려면 3장 RAW 세트가 필요합니다.');
      return;
    }
    setError(null);
    setRawprepBusy(true);
    try {
      const requestPayload = {
        ...rawprepRequest,
        restoration_goal: rawRestorationGoal,
      };
      const response = await fetch('/api/rawprep/jobs?execute=true', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload),
      });
      const payload = await parseJson<RawprepJobRecord>(response);
      setRawprepJob(payload);
      if (payload.missing_tools?.length) {
        setRawprepBusy(false);
        setError(`TriRaw 실행에 필요한 도구가 아직 없습니다: ${payload.missing_tools.join(', ')}`);
      }
    } catch (rawprepError) {
      setRawprepBusy(false);
      setError(rawprepError instanceof Error ? rawprepError.message : 'TriRaw 실행 시작에 실패했습니다.');
    }
  }

  async function cancelRawprep() {
    if (!rawprepJob?.job_id) {
      return;
    }
    setError(null);
    try {
      const response = await fetch(`/api/rawprep/jobs/${encodeURIComponent(rawprepJob.job_id)}/cancel?output_root=${encodeURIComponent(sessionOutputRoot)}`, {
        method: 'POST',
      });
      const payload = await parseJson<RawprepJobRecord>(response);
      setRawprepJob(payload);
      setRawprepBusy(isRawprepActiveStatus(payload.status));
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : 'TriRaw 작업을 중지하지 못했습니다.');
    }
  }

  function adoptWorkingSource(path: string) {
    setDirectPath(path);
    setComparePrimary(path);
    setCompareCandidate((current) => current === path ? null : current);
    setError(null);
  }

  async function applyDreamispPreview() {
    if (!intakePlan?.session_id || !intakePlan.dreamisp_plan) {
      return;
    }
    setError(null);
    setDreamispBusy(true);
    try {
      const payload = await applyDreamispPreviewAdjustments({
        sessionId: intakePlan.session_id,
        outputRoot: sessionOutputRoot,
        sliders,
        controls: dreamispControls,
      });
      setIntakePlan(payload);
      if (!payload.rawprep_request && payload.editable_asset_path) {
        setDirectPath(payload.editable_asset_path);
      }
    } catch (dreamispError) {
      setError(dreamispError instanceof Error ? dreamispError.message : 'DreamISP 미리보기 적용에 실패했습니다.');
    } finally {
      setDreamispBusy(false);
    }
  }

  async function applySelectionFromMask(sourceMaskPath: string) {
    if (!intakePlan?.session_id) {
      setError('세션을 시작한 뒤 선택 기준을 적용해 주세요.');
      return;
    }
    if (!sourcePath) {
      setError('현재 작업 소스가 없어서 선택 미리보기를 만들 수 없습니다.');
      return;
    }
    setError(null);
    setSelectionBusy(true);
    try {
      const payload = await applyStudioSelectionState({
        sessionId: intakePlan.session_id,
        outputRoot: sessionOutputRoot,
        sourceMaskPath,
        sourceAssetPath: sourcePath,
        controls: selectionControls,
      });
      setSelectionState(payload);
    } catch (selectionError) {
      setError(selectionError instanceof Error ? selectionError.message : '선택 기준 적용에 실패했습니다.');
    } finally {
      setSelectionBusy(false);
    }
  }

  function setRawprepReferencePolicy(value: RawprepReferencePolicy) {
    setIntakePlan((current) => {
      if (!current?.rawprep_request) {
        return current;
      }
      return {
        ...current,
        rawprep_request: {
          ...current.rawprep_request,
          groups: current.rawprep_request.groups.map((group, index) => (
            index === 0
              ? { ...group, reference_policy: value }
              : group
          )),
        },
      };
    });
    setError(null);
  }

  function updateRawRestorationGoal(value: RawRestorationGoal) {
    setRawRestorationGoal(value);
    setIntakePlan((current) => {
      if (!current?.rawprep_request) {
        return current;
      }
      return {
        ...current,
        rawprep_request: {
          ...current.rawprep_request,
          restoration_goal: value,
        },
      };
    });
    setError(null);
  }

  async function keepCompareSelect() {
    if (!comparePrimary) {
      return;
    }
    setError(null);
    if (intakePlan?.session_id && compareCandidate) {
      try {
        await recordStudioCompareDecision({
          sessionId: intakePlan.session_id,
          outputRoot: sessionOutputRoot,
          primaryPath: comparePrimary,
          candidatePath: compareCandidate,
          winnerPath: comparePrimary,
          tool: activeTool,
          action: 'keep_select',
        });
      } catch (compareError) {
        setError(compareError instanceof Error ? compareError.message : '비교 결정 기록에 실패했습니다.');
        return;
      }
    }
    adoptWorkingSource(comparePrimary);
  }

  async function acceptCompareCandidate() {
    if (!compareCandidate) {
      return;
    }
    setError(null);
    if (intakePlan?.session_id && comparePrimary) {
      try {
        await recordStudioCompareDecision({
          sessionId: intakePlan.session_id,
          outputRoot: sessionOutputRoot,
          primaryPath: comparePrimary,
          candidatePath: compareCandidate,
          winnerPath: compareCandidate,
          tool: activeTool,
          action: 'accept_candidate',
        });
      } catch (compareError) {
        setError(compareError instanceof Error ? compareError.message : '비교 결정 기록에 실패했습니다.');
        return;
      }
    }
    adoptWorkingSource(compareCandidate);
  }

  function applyWorkingSourceHistory(index: number) {
    const nextPath = sourceHistory[index];
    if (!nextPath) {
      return;
    }
    setSourceHistoryIndex(index);
    setDirectPath(nextPath);
    setComparePrimary(nextPath);
    setCompareCandidate((current) => current === nextPath ? null : current);
    setError(null);
  }

  function undoWorkingSource() {
    if (!canUndoWorkingSource) {
      return;
    }
    applyWorkingSourceHistory(sourceHistoryIndex - 1);
  }

  function redoWorkingSource() {
    if (!canRedoWorkingSource) {
      return;
    }
    applyWorkingSourceHistory(sourceHistoryIndex + 1);
  }

  function saveCurrentVersion() {
    if (!sourcePath) {
      return;
    }
    setSavedVersions((current) => {
      if (current.some((version) => version.path === sourcePath)) {
        return current;
      }
      return [
        {
          id: `${Date.now()}_${current.length + 1}`,
          label: buildSavedVersionLabel(sourcePath, current.length, toolMeta.label, compareSources),
          path: sourcePath,
          createdAt: new Date().toISOString(),
        },
        ...current,
      ].slice(0, 12);
    });
    setError(null);
  }

  function removeSavedVersion(versionId: string) {
    setSavedVersions((current) => current.filter((version) => version.id !== versionId));
  }

  async function exportAsset(path: string | null, label: string) {
    if (!path || !intakePlan) {
      return;
    }
    setError(null);
    setExportBusy(true);
    try {
      const response = await fetch('/api/studio/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: intakePlan.session_id,
          output_root: sessionOutputRoot,
          path,
          label,
        }),
      });
      const payload = await parseJson<StudioExportRecord>(response);
      setLastExportPath(payload.export_path);
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : '결과 저장에 실패했습니다.');
    } finally {
      setExportBusy(false);
    }
  }

  async function exportSessionPackage(options?: {
    label?: string;
    items?: ExportPackageItem[];
    metadata?: Record<string, unknown>;
  }) {
    const packageItems = options?.items ?? exportPackageItems;
    if (!intakePlan || !packageItems.length) {
      return;
    }
    setError(null);
    setPackageBusy(true);
    try {
      const response = await fetch('/api/studio/export/package', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: intakePlan.session_id,
          output_root: sessionOutputRoot,
          label: options?.label ?? 'delivery_package',
          items: packageItems,
          metadata: {
            tool: activeTool,
            prompt,
            entry_mode: intakePlan.entry_mode,
            compare_primary: comparePrimary,
            compare_candidate: compareCandidate,
            saved_version_count: savedVersions.length,
            ...options?.metadata,
          },
        }),
      });
      const payload = await parseJson<StudioExportPackageRecord>(response);
      setLastPackagePath(payload.archive_path);
    } catch (packageError) {
      setError(packageError instanceof Error ? packageError.message : '세션 패키지 저장에 실패했습니다.');
    } finally {
      setPackageBusy(false);
    }
  }

  async function exportDeliveryPresetPackage(
    preset: DeliveryPresetKey,
    options?: { label?: string; metadata?: Record<string, unknown> },
  ) {
    if (!intakePlan) {
      setError('세션을 시작해 주세요.');
      return;
    }
    setError(null);
    setPackageBusy(true);
    try {
      const response = await fetch('/api/studio/export/preset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: intakePlan.session_id,
          output_root: sessionOutputRoot,
          preset,
          label: options?.label ?? preset,
          metadata: {
            tool: activeTool,
            prompt,
            entry_mode: intakePlan.entry_mode,
            compare_primary: comparePrimary,
            compare_candidate: compareCandidate,
            saved_version_count: savedVersions.length,
            ...options?.metadata,
          },
        }),
      });
      const payload = await parseJson<StudioPresetExportResponse>(response);
      setLastPackagePath(payload.archive_path);
      await refreshOperations();
    } catch (packageError) {
      setError(packageError instanceof Error ? packageError.message : '납품 프리셋 저장에 실패했습니다.');
    } finally {
      setPackageBusy(false);
    }
  }

  async function exportBatchDelivery(preset: DeliveryPresetKey) {
    if (!selectedBatchSessionIds.length) {
      setError('배치 마감을 실행하려면 최근 세션을 하나 이상 선택해 주세요.');
      return;
    }
    setError(null);
    setBatchPackageBusy(true);
    try {
      const response = await fetch('/api/studio/export/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          output_root: sessionOutputRoot,
          session_ids: selectedBatchSessionIds,
          preset,
        }),
      });
      const payload = await parseJson<StudioBatchExportResponse>(response);
      setLastBatchReportPath(payload.report_path);
      await refreshOperations();
    } catch (batchError) {
      setError(batchError instanceof Error ? batchError.message : '배치 납품 패키지 저장에 실패했습니다.');
    } finally {
      setBatchPackageBusy(false);
    }
  }

  function downloadAssetFromRoot(path: string | null, outputRoot: string) {
    if (!path || typeof document === 'undefined') {
      return;
    }
    const anchor = document.createElement('a');
    anchor.href = `/api/studio/download?path=${encodeURIComponent(path)}&output_root=${encodeURIComponent(outputRoot)}`;
    anchor.download = '';
    anchor.rel = 'noopener';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  function downloadAsset(path: string | null) {
    downloadAssetFromRoot(path, sessionOutputRoot);
  }

  async function runStudioJob() {
    if (!sourcePath) {
      setError('AI 도구에 보낼 작업 소스를 선택해 주세요.');
      return;
    }
    if (!aiCapableTool) {
      setError('현재 도구는 검토/출력용입니다. AI 편집 도구를 선택해 주세요.');
      return;
    }
    if (!sourcePreviewable) {
      setError('AI 실행에는 TIFF/JPG/PNG/WebP 작업 소스가 필요합니다. TriRaw 결과나 직접 편집본을 선택해 주세요.');
      return;
    }
    if (!workflowPlan?.workflow_exists) {
      setError('이 AI 워크플로는 아직 현재 스튜디오 빌드에 연결되지 않았습니다.');
      return;
    }
    if (!aiPodReady) {
      setError(podStatus.reason);
      return;
    }
    setError(null);
    setStudioJobBusy(true);
    try {
      const response = await fetch('/api/jobs?execute=true', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool: activeTool,
          seed_root: 'seed_bundle',
          session_id: intakePlan?.session_id,
          output_root: sessionOutputRoot,
          source_path: sourcePath,
          prompt,
        }),
      });
      const payload = await parseJson<StudioJobRecord>(response);
      setStudioJob(payload);
    } catch (studioJobError) {
      setStudioJobBusy(false);
      const message = studioJobError instanceof Error ? studioJobError.message : 'AI 작업을 시작하지 못했습니다.';
      setError(
        message.includes('inside the configured output root')
          ? '현재 작업 소스 경로가 이 세션 출력 루트와 어긋나 있었습니다. 입력 분석을 다시 실행하거나, 현재 세션에서 생성된 소스를 다시 작업 소스로 선택해 주세요.'
          : message,
      );
    }
  }

  function resetSession() {
    const defaults = defaultWorkspacePreferences();
    const dreamispDefaults = defaultDreamispControls();
    setFiles([]);
    setEntryPreference(defaults.entryPreference);
    setCameraProfile(defaults.cameraProfile);
    setQualityPreset(defaults.qualityPreset);
    setSingleRawModePreference(defaults.singleRawModePreference);
    setRawRestorationGoal(defaults.rawRestorationGoal);
    setPrompt(defaults.prompt);
    setSliders(defaults.sliders);
    setDreamispControls(dreamispDefaults);
    uploadDragDepthRef.current = 0;
    setUploadDragActive(false);
    setSessionOutputRootOverride(null);
    clearPipelineState();
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }

  function applyWorkspacePreset(preset: WorkspacePreset) {
    setActiveTool(preset.activeTool);
    setWorkspaceMode(preset.workspaceMode);
    setEntryPreference(preset.entryPreference);
    setCameraProfile(preset.cameraProfile);
    setQualityPreset(preset.qualityPreset);
    setSingleRawModePreference(preset.singleRawModePreference);
    setRawRestorationGoal(normalizeRawRestorationGoal(preset.rawRestorationGoal, rawRestorationGoalOptions));
    setPrompt(preset.prompt);
    setSliders(preset.sliders);
    setError(null);
  }

  function saveCurrentWorkspacePreset() {
    const label = `${toolMeta.label} 프리셋 ${new Date().toLocaleTimeString()}`;
    const preset = currentWorkspacePresetSnapshot(currentWorkspacePreferences, label);
    setWorkspacePresets((current) => [preset, ...current].slice(0, 16));
    setError(null);
  }

  function removeWorkspacePreset(presetId: string) {
    setWorkspacePresets((current) => current.filter((preset) => preset.id !== presetId));
  }

  function exportWorkspacePreset(preset: WorkspacePreset) {
    exportJsonDownload(preset, `${preset.name.replace(/[^\w.-]+/g, '_') || 'workspace_preset'}.json`);
  }

  async function importWorkspacePreset(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    try {
      const raw = await file.text();
      const payload = JSON.parse(raw) as Partial<WorkspacePreset>;
      const imported: WorkspacePreset = {
        ...currentWorkspacePresetSnapshot(defaultWorkspacePreferences(), typeof payload.name === 'string' && payload.name.trim() ? payload.name.trim() : `가져온 프리셋 ${new Date().toLocaleTimeString()}`),
        ...currentWorkspacePreferences,
        ...payload,
        id: typeof payload.id === 'string' && payload.id ? payload.id : `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        createdAt: typeof payload.createdAt === 'string' ? payload.createdAt : new Date().toISOString(),
        activeTool: typeof payload.activeTool === 'string' ? payload.activeTool as ToolKey : currentWorkspacePreferences.activeTool,
        workspaceMode: payload.workspaceMode === 'advanced' ? 'advanced' : 'standard',
        entryPreference: payload.entryPreference === 'rawprep' || payload.entryPreference === 'direct_edit' ? payload.entryPreference : 'auto',
        cameraProfile: payload.cameraProfile === 'tz99'
          || payload.cameraProfile === 'eos_r8'
          || payload.cameraProfile === 'sony_a7c_ii'
          || payload.cameraProfile === 'nikon_zf'
          || payload.cameraProfile === 'fuji_x_s20'
          ? payload.cameraProfile
          : 'auto',
        qualityPreset: payload.qualityPreset === 'safe' ? 'safe' : 'balanced',
        singleRawModePreference: payload.singleRawModePreference === 'fast'
          || payload.singleRawModePreference === 'hq'
          || payload.singleRawModePreference === 'safe'
          ? payload.singleRawModePreference
          : 'auto',
        rawRestorationGoal: normalizeRawRestorationGoal(payload.rawRestorationGoal, rawRestorationGoalOptions),
        prompt: typeof payload.prompt === 'string' ? payload.prompt : '',
        sliders: {
          strength: typeof payload.sliders?.strength === 'number' ? Math.max(0, Math.min(100, Math.round(payload.sliders.strength))) : currentWorkspacePreferences.sliders.strength,
          realism: typeof payload.sliders?.realism === 'number' ? Math.max(0, Math.min(100, Math.round(payload.sliders.realism))) : currentWorkspacePreferences.sliders.realism,
          preserveTexture: typeof payload.sliders?.preserveTexture === 'number' ? Math.max(0, Math.min(100, Math.round(payload.sliders.preserveTexture))) : currentWorkspacePreferences.sliders.preserveTexture,
        },
      };
      setWorkspacePresets((current) => [imported, ...current.filter((preset) => preset.id !== imported.id)].slice(0, 16));
      setError(null);
    } catch {
      setError('프리셋 파일을 읽지 못했습니다.');
    } finally {
      if (presetImportInputRef.current) {
        presetImportInputRef.current.value = '';
      }
    }
  }

  async function cancelStudioJob() {
    if (!studioJob?.job_id) {
      return;
    }
    setError(null);
    try {
      const response = await fetch(`/api/jobs/${encodeURIComponent(studioJob.job_id)}/cancel?output_root=${encodeURIComponent(sessionOutputRoot)}`, {
        method: 'POST',
      });
      const payload = await parseJson<StudioJobRecord>(response);
      setStudioJob(payload);
      setStudioJobBusy(isStudioJobActiveStatus(payload.status));
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : 'AI 작업을 중지하지 못했습니다.');
    }
  }

  async function retryRawprep() {
    if (!rawprepJob?.job_id) {
      return;
    }
    setError(null);
    setRawprepBusy(true);
    try {
      const response = await fetch(`/api/rawprep/jobs/${encodeURIComponent(rawprepJob.job_id)}/retry?output_root=${encodeURIComponent(sessionOutputRoot)}`, {
        method: 'POST',
      });
      const payload = await parseJson<RawprepJobRecord>(response);
      setRawprepJob(payload);
      setRawprepArtifacts(null);
      setRawprepBusy(isRawprepActiveStatus(payload.status));
    } catch (retryError) {
      setRawprepBusy(false);
      setError(retryError instanceof Error ? retryError.message : 'TriRaw 작업을 다시 시작하지 못했습니다.');
    }
  }

  async function retryStudioJob() {
    if (!studioJob?.job_id) {
      return;
    }
    setError(null);
    setStudioJobBusy(true);
    try {
      const response = await fetch(`/api/jobs/${encodeURIComponent(studioJob.job_id)}/retry?output_root=${encodeURIComponent(sessionOutputRoot)}`, {
        method: 'POST',
      });
      const payload = await parseJson<StudioJobRecord>(response);
      setStudioJob(payload);
      setStudioJobBusy(isStudioJobActiveStatus(payload.status));
    } catch (retryError) {
      setStudioJobBusy(false);
      setError(retryError instanceof Error ? retryError.message : 'AI 작업을 다시 시작하지 못했습니다.');
    }
  }

  function downloadSessionReport() {
    if (typeof document === 'undefined') {
      return;
    }
    const reportPayload = {
      generated_at: new Date().toISOString(),
      session_id: intakePlan?.session_id ?? null,
      output_root: sessionOutputRoot,
      active_tool: activeTool,
      current_stage: stageKey,
      entry_mode: intakePlan?.entry_mode ?? null,
      source_path: sourcePath,
      latest_result_path: latestResultPath,
      compare_primary: comparePrimary,
      compare_candidate: compareCandidate,
      rawprep: rawprepJob ? {
        job_id: rawprepJob.job_id,
        status: rawprepJob.status,
        current_step: rawprepJob.current_step ?? null,
        started_at: rawprepJob.started_at ?? null,
        finished_at: rawprepJob.finished_at ?? null,
      } : null,
      ai_job: studioJob ? {
        job_id: studioJob.job_id,
        status: studioJob.status,
        current_step: studioJob.current_step ?? null,
        started_at: studioJob.started_at ?? null,
        finished_at: studioJob.finished_at ?? null,
        output_count: studioJob.outputs.length,
      } : null,
      saved_versions: savedVersions,
      telemetry: finishTelemetry,
    };
    const blob = new Blob([JSON.stringify(reportPayload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${intakePlan?.session_id ?? 'dreamcatcher_session'}_report.json`;
    anchor.rel = 'noopener';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  const topBar = (
    <TopBar
      title="DreamCatcher Studio"
      subtitle="사진 중심 편집 · AI 판단 · 결과 회수"
      sessionLabel={intakePlan?.session_id ?? '세션 미시작'}
      pipelineLabel={
        studioJobBusy
          ? `${toolMeta.label} 실행 중`
          : studioJob?.status === 'done'
            ? `${toolMeta.label} 결과 준비 완료`
            : rawprepBusy
              ? 'TriRaw 실행 중'
              : intakePlan?.entry_mode === 'direct_edit_raw' && singleRawSummary?.previewPath
                ? '단일 RAW 기본 결과 준비 완료'
              : sourcePath
                ? '작업 소스 준비 완료'
                : '입력 대기'
      }
      healthLabel={`${podStatus.label} · ${backendHealthy === false ? '백엔드 연결 문제' : summarizeRawprepHealth(rawprepHealth)}`}
      actions={[
        { label: '세션 초기화', onClick: () => { setActiveSurface('intake'); resetSession(); }, tone: 'quiet' },
        { label: '입력 다시 분석', onClick: () => { setActiveSurface('intake'); void analyze(); }, disabled: !files.length || intakeBusy, tone: 'primary' },
      ]}
    />
  );

  const rail = (
    <ToolRail
      title={isAdvancedWorkspace ? '도구 레일' : '현재 단계 도구'}
      items={toolItems}
      activeTool={activeTool}
      onSelectTool={(tool) => {
        const nextTool = tool as ToolKey;
        setActiveTool(nextTool);
        setActiveSurface(workSurfaceForTool(nextTool));
      }}
      dense={!isAdvancedWorkspace}
    />
  );

  const inspector = (
    <PropertyPanel
      title={isAdvancedWorkspace ? '판단 패널' : '작업 메모 · 판단 패널'}
      sections={propertySections}
      promptLabel="작업 메모 / 프롬프트"
      promptPlaceholder="예: 잡티는 최대한 자연스럽게 줄이고, 의상 질감은 살린 채 피부 결만 정리. 필요하면 RAW 준비는 건너뛰고 단일 RAW 기준으로 시작."
      promptValue={prompt}
      onPromptChange={setPrompt}
      sliders={[
        { key: 'strength', label: '보정 강도', min: 0, max: 100, value: sliders.strength, onChange: (value) => setSliders((current) => ({ ...current, strength: value })) },
        { key: 'realism', label: '자연스러움', min: 0, max: 100, value: sliders.realism, onChange: (value) => setSliders((current) => ({ ...current, realism: value })) },
        { key: 'preserveTexture', label: '질감 보존', min: 0, max: 100, value: sliders.preserveTexture, onChange: (value) => setSliders((current) => ({ ...current, preserveTexture: value })) },
        ...(selectionState ? [
          { key: 'selectionThreshold', label: '선택 임계값', min: 0, max: 255, value: selectionControls.threshold, onChange: (value: number) => setSelectionControls((current) => ({ ...current, threshold: value })) },
          { key: 'selectionExpand', label: '선택 확장/수축', min: -32, max: 32, value: selectionControls.expandPixels, onChange: (value: number) => setSelectionControls((current) => ({ ...current, expandPixels: value })) },
          { key: 'selectionFeather', label: '경계 부드럽게', min: 0, max: 32, value: selectionControls.featherRadius, onChange: (value: number) => setSelectionControls((current) => ({ ...current, featherRadius: value })) },
        ] : []),
        ...(intakePlan?.dreamisp_plan ? [
          { key: 'dreamispTemperature', label: 'WB 온도', min: -100, max: 100, value: dreamispControls.temperatureDelta, onChange: (value: number) => setDreamispControls((current) => ({ ...current, temperatureDelta: value })) },
          { key: 'dreamispTint', label: 'WB 틴트', min: -100, max: 100, value: dreamispControls.tintDelta, onChange: (value: number) => setDreamispControls((current) => ({ ...current, tintDelta: value })) },
          { key: 'dreamispExposure', label: '노출', min: -4, max: 4, step: 0.1, value: dreamispControls.exposureEv, onChange: (value: number) => setDreamispControls((current) => ({ ...current, exposureEv: value })) },
          { key: 'dreamispContrast', label: '콘트라스트', min: -100, max: 100, value: dreamispControls.contrast, onChange: (value: number) => setDreamispControls((current) => ({ ...current, contrast: value })) },
          { key: 'dreamispClarity', label: '클래리티', min: -100, max: 100, value: dreamispControls.clarity, onChange: (value: number) => setDreamispControls((current) => ({ ...current, clarity: value })) },
        ] : []),
      ]}
    />
  );

  const workflowStatusLabel = aiToolStatusText(
    workflowPlan,
    workflowBusy,
    activeTool,
    Boolean(sourcePath),
    sourcePreviewable,
    podStatus,
  );

  const finishDeliveryDesk = (
    <FinishDeliveryDesk
      intakeReady={Boolean(intakePlan)}
      packageBusy={packageBusy}
      batchPackageBusy={batchPackageBusy}
      optionGridTemplateColumns={optionGridTemplateColumns}
      deliveryPresetProfiles={deliveryPresetProfiles}
      finishExportPresets={finishExportPresets}
      finishTelemetry={finishTelemetry}
      selectedBatchSessions={selectedBatchSessions}
      selectedBatchSessionIds={selectedBatchSessionIds}
      recentSessionsCount={recentSessions.length}
      lastBatchReportPath={lastBatchReportPath}
      onImportProfiles={importDeliveryPresetProfiles}
      onExportLibrary={exportDeliveryPresetLibrary}
      onDownloadSessionReport={downloadSessionReport}
      onApplyDeliveryPresetProfile={applyDeliveryPresetProfile}
      onExportBatchDelivery={exportBatchDelivery}
      onExportDeliveryPresetPackage={exportDeliveryPresetPackage}
      onSaveDeliveryPresetProfile={saveDeliveryPresetProfile}
      onExportDeliveryPresetProfile={exportDeliveryPresetProfile}
      onRemoveDeliveryPresetProfile={removeDeliveryPresetProfile}
      onSelectAllBatch={selectAllRecentSessionsForBatch}
      onClearBatchSelection={clearBatchSessionSelection}
      onDownloadAsset={downloadAsset}
    />
  );

  const sessionSetupSurface = (
    <StudioSessionSetupSection
      stages={stages}
      stageKey={stageKey}
      workspaceModes={workspaceModes}
      workspaceMode={workspaceMode}
      toast={toast}
      queueAttention={queueAttention}
      focusHighlights={focusHighlights}
      optionGridTemplateColumns={optionGridTemplateColumns}
      intakeGridTemplateColumns={intakeGridTemplateColumns}
      toolMeta={toolMeta}
      fileInputRef={fileInputRef}
      files={files}
      uploadDragActive={uploadDragActive}
      entryPreference={entryPreference}
      cameraProfile={cameraProfile}
      qualityPreset={qualityPreset}
      singleRawModePreference={singleRawModePreference}
      rawRestorationGoal={rawprepRequest?.restoration_goal ?? rawRestorationGoal}
      rawRestorationGoalOptions={rawRestorationGoalOptions}
      rawprepReferencePolicy={rawprepRequest?.groups[0]?.reference_policy ?? 'auto'}
      intakePlan={intakePlan}
      singleRawSummary={singleRawSummary}
      intakeBusy={intakeBusy}
      rawprepBusy={rawprepBusy}
      opsActionBusy={opsActionBusy}
      onSelectWorkspaceMode={(mode) => setWorkspaceMode(mode as WorkspaceMode)}
      onResumeQueue={() => void startExternalWorker()}
      onAnalyze={() => void analyze()}
      onResetSession={resetSession}
      onRunRawprep={() => void runRawprep()}
      onAdoptWorkingSource={adoptWorkingSource}
      onFilesSelected={applySelectedFiles}
      onRemoveSelectedFile={removeSelectedFile}
      onSetEntryPreference={setEntryPreference}
      onSetCameraProfile={setCameraProfile}
      onSetQualityPreset={setQualityPreset}
      onSetSingleRawModePreference={setSingleRawModePreference}
      onSetRawRestorationGoal={updateRawRestorationGoal}
      onSetRawprepReferencePolicy={setRawprepReferencePolicy}
      onUploadDragEnter={handleUploadDragEnter}
      onUploadDragOver={handleUploadDragOver}
      onUploadDragLeave={handleUploadDragLeave}
      onUploadDrop={handleUploadDrop}
      sessionEntryLabel={sessionEntryLabel}
      uploadFileKey={uploadFileKey}
    />
  );

  const focusSurface = (
    <StudioFocusSection
      outputRoot={sessionOutputRoot}
      sourcePath={sourcePath}
      sourcePreviewUrl={sourcePreviewUrl}
      focusGridTemplateColumns={focusGridTemplateColumns}
      compareGridTemplateColumns={compareGridTemplateColumns}
      stageKey={stageKey}
      stages={stages}
      rawprepJob={rawprepJob}
      rawprepMotionOverlayPath={rawprepMotionOverlayPath}
      rawprepMotionOverlayUrl={rawprepMotionOverlayUrl}
      rawprepMotionOverlaySummary={rawprepMotionOverlaySummary}
      rawprepMotionOverlayCoverage={rawprepMotionOverlayCoverage}
      rawprepDiagnosticViews={rawprepDiagnosticViews}
      rawprepSelectedReference={rawprepSelectedReference}
      rawprepSelectedReferencePreviewPath={rawprepSelectedReferencePreviewPath}
      rawprepSelectedReferencePreviewUrl={rawprepSelectedReferencePreviewUrl}
      rawprepReferenceHighlightWatchPath={rawprepReferenceHighlightWatchPath}
      rawprepReferenceHighlightWatchUrl={rawprepReferenceHighlightWatchUrl}
      rawprepReferenceShadowWatchPath={rawprepReferenceShadowWatchPath}
      rawprepReferenceShadowWatchUrl={rawprepReferenceShadowWatchUrl}
      rawprepReferenceReviewItems={rawprepReferenceReviewItems}
      rawprepCandidateReviewItems={rawprepCandidateReviewItems}
      singleRawSummary={singleRawSummary}
      singleRawLensCorrection={singleRawLensCorrection}
      workflowPlan={workflowPlan}
      workflowStatusLabel={workflowStatusLabel}
      compareSources={compareSources}
      comparePrimary={comparePrimary}
      compareCandidate={compareCandidate}
      comparePrimaryUrl={comparePrimaryUrl}
      compareCandidateUrl={compareCandidateUrl}
      compareGuideTool={activeTool}
      savedVersionsCount={savedVersions.length}
      exportPackageItems={exportPackageItems}
      studioJob={studioJob}
      editLinkage={editLinkage}
      selectionState={selectionState}
      selectionPreviewUrl={selectionPreviewUrl}
      selectionSourceMismatch={selectionSourceMismatch}
      selectionBusy={selectionBusy}
      showCompareView={(activeSurface === 'review' || workspaceMode === 'advanced' || activeTool === 'compare') && compareSources.length > 0}
      formatSessionStep={formatSessionStep}
      onSelectComparePrimary={setComparePrimary}
      onSelectCompareCandidate={setCompareCandidate}
      onAdoptWorkingSource={adoptWorkingSource}
      onApplySelectionMask={applySelectionFromMask}
      onKeepCompareSelect={keepCompareSelect}
      onAcceptCompareCandidate={acceptCompareCandidate}
    />
  );

  const actionSurface = (
    <StudioActionRailSections
      isAdvancedWorkspace={isAdvancedWorkspace}
      optionGridTemplateColumns={optionGridTemplateColumns}
      standardSecondaryGridTemplateColumns={standardSecondaryGridTemplateColumns}
      filesCount={files.length}
      intakeBusy={intakeBusy}
      rawprepRequestAvailable={Boolean(rawprepRequest)}
      rawprepBusy={rawprepBusy}
      studioJobBusy={studioJobBusy}
      editableAssetPath={intakePlan?.editable_asset_path ?? null}
      canRunStudioJob={canRunStudioJob}
      rawprepJob={rawprepJob}
      studioJob={studioJob}
      canRetryRawprep={Boolean(rawprepJob) && !isRawprepActiveStatus(rawprepJob?.status)}
      canRetryStudioJob={Boolean(studioJob) && !isStudioJobActiveStatus(studioJob?.status)}
      toolLabel={toolMeta.label}
      canUndoWorkingSource={canUndoWorkingSource}
      canRedoWorkingSource={canRedoWorkingSource}
      sourcePath={sourcePath}
      sourcePreviewable={sourcePreviewable}
      exportBusy={exportBusy}
      intakeReady={Boolean(intakePlan)}
      latestResultPath={latestResultPath}
      exportPackageItemsCount={exportPackageItems.length}
      packageBusy={packageBusy}
      lastExportPath={lastExportPath}
      lastPackagePath={lastPackagePath}
      sourceHistory={sourceHistory}
      sourceHistoryIndex={sourceHistoryIndex}
      savedVersions={savedVersions}
      workspacePresets={workspacePresets}
      presetImportInputRef={presetImportInputRef}
      finishDeliveryDesk={finishDeliveryDesk}
      showFinishDeliveryDesk={activeSurface === 'deliver' || activeTool === 'finish' || stageKey === 'finish'}
      onOpenAdvancedWorkspace={() => setWorkspaceMode('advanced')}
      onAnalyze={() => void analyze()}
      onRunRawprep={() => void runRawprep()}
      onAdoptEditableAsset={() => {
        if (intakePlan?.editable_asset_path) {
          adoptWorkingSource(intakePlan.editable_asset_path);
        }
      }}
      onRunStudioJob={() => void runStudioJob()}
      onCancelRawprep={() => void cancelRawprep()}
      onCancelStudioJob={() => void cancelStudioJob()}
      onRetryRawprep={() => void retryRawprep()}
      onRetryStudioJob={() => void retryStudioJob()}
      onUndoWorkingSource={undoWorkingSource}
      onRedoWorkingSource={redoWorkingSource}
      onSaveCurrentVersion={saveCurrentVersion}
      onExportWorkingSource={() => {
        if (sourcePath) {
          void exportAsset(sourcePath, 'working_source');
        }
      }}
      onExportLatestResult={() => {
        if (latestResultPath) {
          void exportAsset(latestResultPath, 'latest_result');
        }
      }}
      onDownloadLatestResult={() => downloadAsset(latestResultPath)}
      onExportSessionPackage={() => void exportSessionPackage()}
      onSaveCurrentWorkspacePreset={saveCurrentWorkspacePreset}
      onImportWorkspacePreset={importWorkspacePreset}
      onApplyWorkspacePreset={applyWorkspacePreset}
      onExportWorkspacePreset={exportWorkspacePreset}
      onRemoveWorkspacePreset={removeWorkspacePreset}
      onApplyWorkingSourceHistory={applyWorkingSourceHistory}
      onUseSavedVersion={adoptWorkingSource}
      onDownloadSavedVersion={downloadAsset}
      onRemoveSavedVersion={removeSavedVersion}
      basenameFromPath={basenameFromPath}
    />
  );

  const recentSessionsSurface = (
    <RecentSessionsBoard
      recentSessions={recentSessions}
      recentSessionsLoading={recentSessionsLoading}
      currentSessionId={intakePlan?.session_id ?? null}
      expandedRecentSessionIds={expandedRecentSessionIds}
      selectedBatchSessionIds={selectedBatchSessionIds}
      compareGridTemplateColumns={compareGridTemplateColumns}
      onSelectAllRecentSessionsForBatch={selectAllRecentSessionsForBatch}
      onClearBatchSessionSelection={clearBatchSessionSelection}
      onRefreshRecentSessions={refreshRecentSessions}
      onToggleBatchSessionSelection={toggleBatchSessionSelection}
      onToggleRecentSessionExpanded={toggleRecentSessionExpanded}
      onOpenRecentSession={openRecentSession}
      onUpdateSessionCatalog={updateSessionCatalog}
      onApplyBatchCatalogUpdate={applyBatchCatalogUpdate}
      batchCatalogPickStatus={batchCatalogPickStatus}
      batchCatalogReviewStatus={batchCatalogReviewStatus}
      batchCatalogKeywords={batchCatalogKeywords}
      batchProofingProfile={batchProofingProfile}
      batchPrintProfile={batchPrintProfile}
      batchClientCollection={batchClientCollection}
      setBatchCatalogPickStatus={setBatchCatalogPickStatus}
      setBatchCatalogReviewStatus={setBatchCatalogReviewStatus}
      setBatchCatalogKeywords={setBatchCatalogKeywords}
      setBatchProofingProfile={setBatchProofingProfile}
      setBatchPrintProfile={setBatchPrintProfile}
      setBatchClientCollection={setBatchClientCollection}
      catalogBusyKey={catalogBusyKey}
      previewUrl={previewUrl}
      recentPreviewMaxEdge={previewMaxEdges.recent}
      formatSessionTimestamp={formatSessionTimestamp}
      formatSessionStep={formatSessionStep}
      sessionEntryLabel={sessionEntryLabel}
      sessionStatusTone={sessionStatusTone}
    />
  );

  const operationsSurface = (
    <StudioOperationsBoard
      opsSummary={opsSummary}
      opsRoots={opsRoots}
      groupedOpsEvents={groupedOpsEvents}
      opsLoading={opsLoading}
      opsActionBusy={opsActionBusy}
      opsEventSourceFilter={opsEventSourceFilter}
      opsEventStatusFilter={opsEventStatusFilter}
      opsEventQuery={opsEventQuery}
      optionGridTemplateColumns={optionGridTemplateColumns}
      sessionOutputRoot={sessionOutputRoot}
      podStatus={podStatus}
      onRefreshOperations={() => void refreshOperations()}
      onOpenPodAndContinue={() => void openPodAndContinue()}
      onCheckpointAndStopPod={() => void checkpointAndStopPod()}
      onStartExternalWorker={(outputRoots) => void startExternalWorker(outputRoots)}
      onStopWorkerQueue={(outputRoots) => void stopWorkerQueue(outputRoots)}
      onRetryVisibleDeadLetters={() => void retryVisibleDeadLetters()}
      onOpenDeadLetterSession={(deadLetter) => void openDeadLetterSession(deadLetter)}
      onUpdateDeadLetterInvestigation={(deadLetter, payload) => void updateDeadLetterInvestigation(deadLetter, payload)}
      onDownloadAssetFromRoot={downloadAssetFromRoot}
      onRetryDeadLetter={(deadLetter) => void retryDeadLetter(deadLetter)}
      onSetOpsEventSourceFilter={setOpsEventSourceFilter}
      onSetOpsEventStatusFilter={setOpsEventStatusFilter}
      onSetOpsEventQuery={setOpsEventQuery}
      formatSessionTimestamp={formatSessionTimestamp}
      formatSessionStep={formatSessionStep}
      formatWorkerModeLabel={formatWorkerModeLabel}
      formatProviderControlState={formatProviderControlState}
      outputRootLabel={outputRootLabel}
      deadLetterToolLabel={deadLetterToolLabel}
      deadLetterInvestigationLabel={deadLetterInvestigationLabel}
      formatTelemetryEventLabel={formatTelemetryEventLabel}
      telemetrySourceLabel={telemetrySourceLabel}
    />
  );

  const supportSurfaceHeader = (
    <div style={{ display: 'grid', gap: 4, padding: '0 4px' }}>
      <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>이어 작업 및 운영</strong>
      <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
        최근 세션과 운영 상태를 확인하세요.
      </span>
    </div>
  );

  const activeSurfaceLayout = (() => {
    switch (activeSurface) {
      case 'intake':
        return sessionSetupSurface;
      case 'raw':
        return (
          <section style={{ display: 'grid', gridTemplateColumns: isStackedLayout ? '1fr' : 'minmax(360px, 0.9fr) minmax(0, 1.1fr)', gap: 16, alignItems: 'start' }}>
            {sessionSetupSurface}
            {focusSurface}
          </section>
        );
      case 'review':
        return (
          <section style={{ display: 'grid', gridTemplateColumns: isStackedLayout ? '1fr' : 'minmax(0, 1.25fr) minmax(300px, 0.75fr)', gap: 16, alignItems: 'start' }}>
            {focusSurface}
            {actionSurface}
          </section>
        );
      case 'deliver':
        return (
          <section style={{ display: 'grid', gridTemplateColumns: supportDeckGridTemplateColumns, gap: 16, alignItems: 'start' }}>
            {finishDeliveryDesk}
            {recentSessionsSurface}
          </section>
        );
      case 'operate':
        return (
          <section style={{ display: 'grid', gap: 12 }}>
            {supportSurfaceHeader}
            <div style={{ display: 'grid', gridTemplateColumns: supportDeckGridTemplateColumns, gap: 16, alignItems: 'start' }}>
              {operationsSurface}
              {recentSessionsSurface}
            </div>
          </section>
        );
      case 'edit':
      default:
        return (
          <section style={{ display: 'grid', gridTemplateColumns: workAreaGridTemplateColumns, gap: 16, alignItems: 'start' }}>
            {focusSurface}
            <div style={{ display: 'grid', gap: 12 }}>{actionSurface}</div>
          </section>
        );
    }
  })();

  return (
    <StudioWorkspaceFrame
      topBar={topBar}
      rail={rail}
      inspector={inspector}
      sessionStrip={<EphemeralRunPodStrip />}
      shellGridTemplateColumns={shellGridTemplateColumns}
      isStackedLayout={isStackedLayout}
      main={(
        <main style={{ padding: isStackedLayout ? 14 : 18, display: 'grid', gap: 14, alignContent: 'start' }}>
          <StudioWorkSurfaceNav
            items={workSurfaceItems}
            activeKey={activeSurface}
            onSelect={(key) => setActiveSurface(key as WorkSurfaceKey)}
            compact={isPhoneLayout}
          />
          {activeSurfaceLayout}

        </main>
      )}
    />
  );
}
