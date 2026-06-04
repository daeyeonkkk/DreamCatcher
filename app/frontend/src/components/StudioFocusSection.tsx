import React, { useState } from 'react';
import { buttonStyle, chipStyle, sectionCardStyle, studioTokens, tileStyle } from '../designTokens';
import type { RawprepCandidateScoreEntry, RawprepGroupReport, RawprepJobRecord, RawprepReferenceSelectionEntry, StudioEditLinkageState, StudioJobRecord, StudioSelectionState, ToolKey, WorkflowPlan } from '../studioApi';
import {
  localizeArtifactSummaryText,
  localizeBootstrapLabel,
  localizeBootstrapRule,
  localizeCommunityTakeaway,
  localizeDatasetLabel,
  localizeExecutionEngine,
  localizeRuntimeArtifactLabel,
  localizeRuntimeBundleLabel,
  localizeSelectionProfile,
  localizeWorkflowSource,
  summarizeWorkflowPath,
} from '../studioPriorLabels';
import type { CompareSource, ExportPackageItem, SingleRawSummaryView, StageItem } from './studioWorkspaceTypes';
import { CompareGuidanceDrawer } from './CompareGuidanceDrawer';

interface StudioFocusSectionProps {
  outputRoot: string;
  sourcePath: string | null;
  sourcePreviewUrl: string | null;
  focusGridTemplateColumns: string;
  compareGridTemplateColumns: string;
  stageKey: string;
  stages: ReadonlyArray<StageItem>;
  rawprepJob: RawprepJobRecord | null;
  rawprepMotionOverlayPath: string | null;
  rawprepMotionOverlayUrl: string | null;
  rawprepMotionOverlaySummary: string | null;
  rawprepMotionOverlayCoverage: number | null;
  rawprepDiagnosticViews: Array<{
    key: string;
    label: string;
    path: string;
    url: string | null;
    summary: string;
    note: string | null;
  }>;
  rawprepSelectedReference: RawprepReferenceSelectionEntry | null;
  rawprepSelectedReferencePreviewPath: string | null;
  rawprepSelectedReferencePreviewUrl: string | null;
  rawprepReferenceHighlightWatchPath: string | null;
  rawprepReferenceHighlightWatchUrl: string | null;
  rawprepReferenceShadowWatchPath: string | null;
  rawprepReferenceShadowWatchUrl: string | null;
  rawprepReferenceReviewItems: Array<RawprepReferenceSelectionEntry & {
    previewUrl: string | null;
    highlightWatchUrl: string | null;
    shadowWatchUrl: string | null;
    scoreDeltaToLeader: number;
    isSelected: boolean;
    isAutoLeader: boolean;
  }>;
  rawprepCandidateReviewItems: Array<RawprepCandidateScoreEntry & {
    previewUrl: string | null;
    scoreDeltaToLeader: number;
    isWinner: boolean;
    isLeader: boolean;
  }>;
  singleRawSummary: SingleRawSummaryView | null;
  singleRawLensCorrection: {
    cameraKey: string | null;
    lensKey: string | null;
    distortionModel: string | null;
    applyDistortion: boolean;
    applyVignette: boolean;
    applyLateralCa: boolean;
    cropMarginRatio: number | null;
    notes: string[];
  } | null;
  workflowPlan: WorkflowPlan | null;
  workflowStatusLabel: string;
  compareSources: CompareSource[];
  comparePrimary: string | null;
  compareCandidate: string | null;
  comparePrimaryUrl: string | null;
  compareCandidateUrl: string | null;
  compareGuideTool: ToolKey;
  savedVersionsCount: number;
  exportPackageItems: ExportPackageItem[];
  studioJob: StudioJobRecord | null;
  editLinkage: StudioEditLinkageState | null;
  selectionState: StudioSelectionState | null;
  selectionPreviewUrl: string | null;
  selectionSourceMismatch: string | null;
  selectionBusy: boolean;
  showCompareView: boolean;
  formatSessionStep: (value: string | null | undefined) => string | null;
  onSelectComparePrimary: (path: string) => void;
  onSelectCompareCandidate: (path: string) => void;
  onAdoptWorkingSource: (path: string) => void;
  onApplySelectionMask: (path: string) => Promise<void> | void;
  onKeepCompareSelect: () => Promise<void> | void;
  onAcceptCompareCandidate: () => Promise<void> | void;
}

function previewFrameStyle(): React.CSSProperties {
  return {
    width: '100%',
    aspectRatio: '4 / 3',
    objectFit: 'contain',
    borderRadius: studioTokens.radius.s,
    background: '#f3f5f8',
    border: `1px solid ${studioTokens.color.line}`,
  };
}

function basenameFromPath(path: string): string {
  const segments = path.split(/[\\/]/).filter(Boolean);
  return segments[segments.length - 1] ?? path;
}

function formatArtifactFootnote(recordCount?: number | null, sizeBytes?: number | null): string {
  const parts: string[] = [];
  if (typeof recordCount === 'number' && recordCount > 0) {
    parts.push(`${recordCount}개 항목`);
  }
  if (typeof sizeBytes === 'number' && sizeBytes > 0) {
    const megaBytes = sizeBytes / (1024 * 1024);
    parts.push(megaBytes >= 1 ? `${megaBytes.toFixed(1)} MB` : `${Math.max(1, Math.round(sizeBytes / 1024))} KB`);
  }
  return parts.join(' | ');
}

function formatFrontierActivationStage(stage: string | null | undefined): string {
  switch (stage) {
    case 'runtime_prior_active':
      return '런타임 prior 활성';
    case 'adapter_hook_active':
      return '어댑터 연결 가능';
    case 'model_contract_active':
      return '모델 계약 활성';
    case 'eval_guardrail_ready':
      return '평가 가드레일 준비';
    case 'license_review':
      return '라이선스 검토';
    case 'weights_pending':
      return '가중치 대기';
    case 'workflow_pending':
      return '워크플로 필요';
    case 'dataset_only':
      return '데이터셋 전용';
    case 'catalog_tracked':
      return '카탈로그 추적';
    default:
      return stage ? stage.replace(/_/g, ' ') : '상태 없음';
  }
}

function formatFrontierStudioUse(value: string): string {
  const labels: Record<string, string> = {
    runtime_prior: '런타임 prior',
    optional_learned_adapter: '선택 학습 어댑터',
    tri_raw_frontier_eval: 'TriRaw Frontier 평가',
    alignment_ghost_denoise_evidence: '정렬/고스트/디노이즈 근거',
    compare_guardrail: '비교 가드레일',
    retouch_reference_prior: '보정 레퍼런스',
    mask_boundary_eval: '마스크 경계 평가',
    cutout_model_evidence: '컷아웃 모델 근거',
    composition_guardrail: '합성 가드레일',
    subject_preservation_eval: '피사체 보존 평가',
    mask_distribution_regression: '마스크 분포 회귀',
    large_hole_fill_eval: '큰 영역 채움 평가',
  };
  return labels[value] ?? value.replace(/_/g, ' ');
}

function formatFallbackReason(reason: string | null | undefined): string {
  switch (reason) {
    case 'narrow_bracket':
      return '브라켓 폭이 좁아 기준 프레임 유지';
    case 'motion_guard':
      return '움직임이 커서 보수 병합 유지';
    case 'alignment_guard':
      return '정렬 압력이 커서 보수 병합 유지';
    case 'none':
    case undefined:
    case null:
      return '없음';
    default:
      return reason.replace(/_/g, ' ');
  }
}

function formatEditLinkageSourceKind(kind: string | null | undefined): string {
  switch (kind) {
    case 'generated_candidate':
      return '생성 편집 결과';
    case 'background_cutout':
      return '배경 분리 결과';
    case 'selection_preview':
      return '선택 미리보기';
    case 'working_source':
      return '현재 작업 소스';
    default:
      return '연결 대기';
  }
}

function formatLensCorrectionModel(model: string | null | undefined): string {
  if (model === 'brown_conrady') {
    return 'Brown-Conrady';
  }
  if (model === 'identity') {
    return '기본 계획';
  }
  return model ?? '미정';
}

function formatLensCorrectionNote(note: string): string {
  if (note === 'Lens metadata is unavailable; distortion correction falls back to an identity plan.') {
    return '렌즈 메타데이터가 없어 왜곡 보정은 기본 계획으로 둡니다.';
  }
  if (note === 'Wide-angle focal length detected; reserve additional crop margin for distortion correction.') {
    return '광각 초점거리로 판단되어 왜곡 보정을 위해 추가 크롭 여유를 둡니다.';
  }
  if (note === 'Fast aperture detected; keep vignette compensation available in the default plan.') {
    return '개방 조리개로 판단되어 비네팅 보정을 준비 상태로 둡니다.';
  }
  return note;
}

function emptyPreviewStyle(): React.CSSProperties {
  return {
    ...previewFrameStyle(),
    display: 'grid',
    placeItems: 'center',
    padding: 18,
    textAlign: 'center',
    fontSize: 12,
    color: studioTokens.color.muted,
    lineHeight: 1.55,
  };
}

function formatCaptureWarning(token: string): string {
  if (token === 'input_order_differs_from_ev_rank') {
    return '업로드 순서가 EV 순서와 다릅니다';
  }
  if (token === 'ev_spacing_irregular') {
    return 'EV 간격이 불규칙합니다';
  }
  if (token === 'ev_span_narrow') {
    return '완전한 TriRaw 복원에는 EV 범위가 좁을 수 있습니다';
  }
  if (token === 'missing_ev_metadata') {
    return '일부 EV 메타데이터가 비어 있습니다';
  }
  return token.replace(/_/g, ' ');
}

function formatEvSpacingQuality(token: string | null | undefined): string {
  switch (token) {
    case 'balanced':
      return '균형적';
    case 'irregular':
      return '불규칙';
    case 'narrow':
      return '좁음';
    case 'wide':
      return '넓음';
    default:
      return token ? token.replace(/_/g, ' ') : '자동';
  }
}

function formatCoverageQuality(token: string | null | undefined): string {
  switch (token) {
    case 'strong':
      return '넉넉함';
    case 'medium':
      return '보통';
    case 'narrow':
      return '좁음';
    default:
      return token ? token.replace(/_/g, ' ') : '정보 없음';
  }
}

function formatReferencePolicy(token: string | null | undefined): string {
  switch (token) {
    case 'auto':
      return '자동';
    case 'first':
      return '첫 프레임 우선';
    case 'middle':
      return '가운데 프레임 우선';
    case 'last':
      return '마지막 프레임 우선';
    default:
      return token ? token.replace(/_/g, ' ') : '자동';
  }
}

function formatTriRawRecommendedArtifact(path: string | null | undefined): string {
  if (!path) {
    return '아직 없음';
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

function formatCoverageSceneLabel(token: string): string {
  if (token === 'backlit_high_dr') {
    return '역광 고명암';
  }
  if (token === 'shadow_lift_hdr') {
    return '암부 복원 HDR';
  }
  if (token === 'high_iso_noise_limited') {
    return '고감도 노이즈 제한';
  }
  if (token === 'tele_detail') {
    return '망원 디테일';
  }
  if (token === 'general') {
    return '일반';
  }
  return token.replace(/_/g, ' ');
}

function formatRuntimeOverrideGroupLabel(token: string): string {
  const labels: Record<string, string> = {
    candidate_score_weights_delta: '후보 점수 편향',
    reference_score_weights_delta: '기준 프레임 편향',
    hdr_rescue_bonus_delta: 'HDR 복원 편향',
    hybrid_selection_delta: '대체 경로 게이트 편향',
    ghost_suppression_delta: '고스팅 억제 편향',
  };
  return labels[token] ?? token.replace(/_/g, ' ');
}

function formatRuntimeGuidanceEffectLabel(token: string): string {
  const labels: Record<string, string> = {
    support_current_bias: '현재 편향 강화',
    temper_current_bias: '현재 편향 완화',
    observe_more: '추가 근거 필요',
  };
  return labels[token] ?? token.replace(/_/g, ' ');
}

function formatReferenceReasonLabel(token: string): string {
  const labels: Record<string, string> = {
    highlight_watch_component: '하이라이트 감시',
    shadow_watch_component: '암부 감시',
    diagnostic_stability_component: '감시 안정성',
    motion_region_component: '움직임 안정성',
    region_stability_component: '영역 안정성',
    highlight_region_component: '하이라이트 복원',
    shadow_region_component: '암부 안전성',
    edge_component: '경계 디테일',
    entropy_component: '질감',
    exposure_component: 'EV 기준',
    luma_component: '중간톤 위치',
    clip_component: '클립 안전성',
    shadow_component: '암부 채도',
    edge_chroma_component: '경계 채도',
    position_component: '브라켓 위치',
    stability_component: '기본 안정성',
  };
  return labels[token] ?? token.replace(/_/g, ' ');
}

function referenceReasonSummary(entry: RawprepReferenceSelectionEntry): string {
  const scoreComponents = entry.score_components ?? {};
  const reasons = Object.entries(scoreComponents)
    .filter((value): value is [string, number] => typeof value[1] === 'number')
    .sort((a, b) => b[1] - a[1])
    .filter(([, value], index) => value >= 0.52 || index < 2)
    .slice(0, 3)
    .map(([key]) => formatReferenceReasonLabel(key));
  if (reasons.length) {
    return reasons.join(' | ');
  }
  if (entry.diagnostics?.summary?.highlight) {
    return '하이라이트 감시 준비됨';
  }
  return '기본 프로브 지표';
}

function formatReferenceScoreDelta(value: number): string {
  if (Math.abs(value) < 0.0005) {
    return '선두';
  }
  return `${value > 0 ? '+' : ''}${value.toFixed(3)}`;
}

function formatCandidateLabel(label: string): string {
  if (label === 'best_single') {
    return '기준 프레임 유지 경로';
  }
  if (label === 'merged') {
    return '병합 결과';
  }
  if (label === 'hybrid') {
    return '보수 프리뷰';
  }
  if (label === 'aggressive_restore') {
    return '공격적 복원 후보';
  }
  return label.replace(/_/g, ' ');
}

type InsightTag = {
  label: string;
  tone: 'default' | 'accent' | 'success' | 'warning';
};

function buildTriRawSummaryTags(
  rawprepGroupReport: RawprepGroupReport | null,
  motionOverlayCoverage: number | null,
): InsightTag[] {
  if (!rawprepGroupReport) {
    return [];
  }
  const tags: InsightTag[] = [];
  const coverage = rawprepGroupReport.bracket_coverage;
  if (coverage?.coverage_quality === 'narrow') {
    tags.push({ label: '좁은 브라켓', tone: 'warning' });
  } else if (coverage?.coverage_quality === 'strong') {
    tags.push({ label: '넉넉한 HDR 범위', tone: 'success' });
  }
  if ((coverage?.highlight_headroom_fraction ?? 0) >= 0.05) {
    tags.push({ label: '하이라이트 압박', tone: 'accent' });
  }
  if (coverage?.scene_class === 'high_iso_noise_limited') {
    tags.push({ label: '고감도 위험', tone: 'warning' });
  }
  if ((motionOverlayCoverage ?? 0) >= 0.10) {
    tags.push({ label: '움직임 많은 브라켓', tone: 'warning' });
  }
  if (rawprepGroupReport.fallback_reason && rawprepGroupReport.fallback_reason !== 'none') {
    tags.push({ label: '대체 경로 동작 중', tone: 'warning' });
  }
  if (rawprepGroupReport.capture_summary?.capture_warnings?.includes('ev_spacing_irregular')) {
    tags.push({ label: 'EV 간격 불규칙', tone: 'warning' });
  }
  return tags.slice(0, 4);
}

function buildReferenceTags(
  entry: RawprepReferenceSelectionEntry & {
    scoreDeltaToLeader: number;
    isSelected: boolean;
    isAutoLeader: boolean;
  },
): InsightTag[] {
  const metrics = entry.diagnostics?.metrics;
  const scoreComponents = entry.score_components ?? {};
  const tags: InsightTag[] = [];
  if ((metrics?.highlight_coverage ?? 0) >= 0.06 && (metrics?.highlight_preservation ?? 1) < 0.60) {
    tags.push({ label: '하이라이트 압박', tone: 'warning' });
  }
  if ((metrics?.shadow_coverage ?? 0) >= 0.12 && (metrics?.shadow_safety ?? 1) < 0.58) {
    tags.push({ label: '암부 노이즈 위험', tone: 'warning' });
  }
  if ((scoreComponents.motion_region_component ?? 1) < 0.58) {
    tags.push({ label: '움직임 많음', tone: 'warning' });
  }
  if ((scoreComponents.position_component ?? 1) < 0.45) {
    tags.push({ label: '기준 EV 이탈', tone: 'default' });
  }
  if ((metrics?.highlight_preservation ?? 0) >= 0.82) {
    tags.push({ label: '하이라이트 안전', tone: 'success' });
  }
  if ((metrics?.shadow_safety ?? 0) >= 0.78) {
    tags.push({ label: '암부 안전', tone: 'success' });
  }
  if (entry.scoreDeltaToLeader <= -0.10) {
    tags.push({ label: '선두와 차이 큼', tone: 'default' });
  }
  if (entry.isAutoLeader) {
    tags.push({ label: '자동 선호', tone: 'accent' });
  }
  const unique = tags.filter((tag, index) => tags.findIndex((item) => item.label === tag.label) === index);
  return unique.slice(0, 4);
}

function candidateReasonSummary(entry: RawprepCandidateScoreEntry): string {
  if (entry.requires_review) {
    return '검수 필요 | 디테일 복원 후보';
  }
  const scoreComponents = entry.score_components ?? {};
  const positiveKeys = [
    'hdr_rescue_bonus',
    'coverage_bonus',
    'region_bonus',
    'detail_component',
    'clip_component',
    'highlight_component',
    'motion_region_component',
  ] as const;
  const negativeKeys = [
    'coverage_penalty',
    'grain_penalty',
    'motion_region_penalty',
  ] as const;
  const positives = positiveKeys
    .map((key) => [key, scoreComponents[key] ?? -Infinity] as const)
    .filter(([, value]) => value > 0.04 || value > 0.65)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([key]) => {
      const labels: Record<string, string> = {
        hdr_rescue_bonus: 'HDR 복원',
        coverage_bonus: '범위 이득',
        region_bonus: '영역 복원',
        detail_component: '디테일 유지',
        clip_component: '클립 안전성',
        highlight_component: '하이라이트 디테일',
        motion_region_component: '움직임 안정성',
      };
      return labels[key];
    });
  const negatives = negativeKeys
    .map((key) => [key, scoreComponents[key] ?? 0] as const)
    .filter(([, value]) => value > 0.03)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 1)
    .map(([key]) => {
      const labels: Record<string, string> = {
        coverage_penalty: '좁은 브라켓 감점',
        grain_penalty: '입자 감점',
        motion_region_penalty: '움직임 감점',
      };
      return labels[key];
    });
  const combined = [...positives, ...negatives];
  if (combined.length) {
    return combined.join(' | ');
  }
  return '기본 후보 점수';
}

function buildCandidateTags(
  entry: RawprepCandidateScoreEntry & {
    scoreDeltaToLeader: number;
    isWinner: boolean;
    isLeader: boolean;
  },
): InsightTag[] {
  const scoreComponents = entry.score_components ?? {};
  const tags: InsightTag[] = [];
  if (entry.requires_review) {
    tags.push({ label: '검수 필요', tone: 'warning' });
  }
  if (entry.label === 'aggressive_restore') {
    tags.push({ label: '공격 복원', tone: 'accent' });
  }
  if ((scoreComponents.hdr_rescue_bonus ?? 0) >= 0.05) {
    tags.push({ label: 'HDR 복원', tone: 'accent' });
  }
  if ((scoreComponents.coverage_bonus ?? 0) >= 0.03) {
    tags.push({ label: '범위 이득', tone: 'success' });
  }
  if ((scoreComponents.region_bonus ?? 0) >= 0.03) {
    tags.push({ label: '영역 이득', tone: 'accent' });
  }
  if ((scoreComponents.coverage_penalty ?? 0) >= 0.03) {
    tags.push({ label: '좁은 브라켓 감점', tone: 'warning' });
  }
  if ((scoreComponents.grain_penalty ?? 0) >= 0.04) {
    tags.push({ label: '입자 위험', tone: 'warning' });
  }
  if ((scoreComponents.motion_region_penalty ?? 0) >= 0.04) {
    tags.push({ label: '움직임 감점', tone: 'warning' });
  }
  if ((scoreComponents.detail_component ?? 0) >= 0.82) {
    tags.push({ label: '디테일 안전', tone: 'success' });
  }
  if ((scoreComponents.clip_component ?? 0) >= 0.88) {
    tags.push({ label: '클립 안전', tone: 'success' });
  }
  if (entry.isWinner) {
    tags.push({ label: '선택됨', tone: 'accent' });
  }
  const unique = tags.filter((tag, index) => tags.findIndex((item) => item.label === tag.label) === index);
  return unique.slice(0, 4);
}

function editOutcomeSectionTitle(tool: string | null | undefined): string {
  switch (tool) {
    case 'removeBg':
      return '배경 분리 결과';
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

function editOutcomeSectionDescription(tool: string | null | undefined): string {
  switch (tool) {
    case 'removeBg':
      return '피사체와 마스크 결과를 확인하세요.';
    case 'replaceBg':
      return '배경 교체 후보를 비교하고 선택하세요.';
    case 'replaceObject':
      return '채우기 후보를 비교하고 선택하세요.';
    case 'expandCanvas':
      return '확장 후보의 가장자리와 구도를 확인하세요.';
    default:
      return '생성 편집 결과를 후보 스트립으로 분리해 비교하고 현재 작업 소스로 채택합니다.';
  }
}

function editOutcomeSourceGroups(tool: string | null | undefined): string[] {
  switch (tool) {
    case 'removeBg':
      return ['배경 분리 결과'];
    case 'replaceBg':
      return ['배경 분리 결과', '배경 교체 후보', '생성 편집 후보'];
    case 'replaceObject':
      return ['배경 분리 결과', '선택 영역 채우기 후보', '생성 편집 후보'];
    case 'expandCanvas':
      return ['화면 확장 후보', '생성 편집 후보'];
    default:
      return ['배경 분리 결과', '생성 편집 후보'];
  }
}

export function StudioFocusSection({
  outputRoot,
  sourcePath,
  sourcePreviewUrl,
  focusGridTemplateColumns,
  compareGridTemplateColumns,
  stageKey,
  stages,
  rawprepJob,
  rawprepMotionOverlayPath,
  rawprepMotionOverlayUrl,
  rawprepMotionOverlaySummary,
  rawprepMotionOverlayCoverage,
  rawprepDiagnosticViews,
  rawprepSelectedReference,
  rawprepSelectedReferencePreviewPath,
  rawprepSelectedReferencePreviewUrl,
  rawprepReferenceHighlightWatchPath,
  rawprepReferenceHighlightWatchUrl,
  rawprepReferenceShadowWatchPath,
  rawprepReferenceShadowWatchUrl,
  rawprepReferenceReviewItems,
  rawprepCandidateReviewItems,
  singleRawSummary,
  singleRawLensCorrection,
  workflowPlan,
  workflowStatusLabel,
  compareSources,
  comparePrimary,
  compareCandidate,
  comparePrimaryUrl,
  compareCandidateUrl,
  compareGuideTool,
  savedVersionsCount,
  exportPackageItems,
  studioJob,
  editLinkage,
  selectionState,
  selectionPreviewUrl,
  selectionSourceMismatch,
  selectionBusy,
  showCompareView,
  formatSessionStep,
  onSelectComparePrimary,
  onSelectCompareCandidate,
  onAdoptWorkingSource,
  onApplySelectionMask,
  onKeepCompareSelect,
  onAcceptCompareCandidate,
}: StudioFocusSectionProps) {
  const [showAllCompareSources, setShowAllCompareSources] = useState(false);
  const compact = typeof window !== 'undefined' && window.innerWidth < studioTokens.breakpoint.laptop;
  const currentStage = stages.find((stage) => stage.key === stageKey);
  const comparePreviewLimit = compact ? 3 : 4;
  const visibleCompareSources = showAllCompareSources ? compareSources : compareSources.slice(0, comparePreviewLimit);
  const hiddenCompareSourcesCount = Math.max(compareSources.length - visibleCompareSources.length, 0);
  const rawprepGroupReport = rawprepJob?.group_reports?.[0] ?? null;
  const runtimeOverrideSummary = rawprepGroupReport?.runtime_overrides ?? null;
  const runtimeOverrideGroups = Object.keys(runtimeOverrideSummary?.combined ?? {});
  const runtimeBenchmarkGuidance = runtimeOverrideSummary?.benchmark_guidance ?? null;
  const runtimeGuidanceEffects = Object.entries(runtimeBenchmarkGuidance?.combined_effect_counts ?? {});
  const runtimeGuidanceScales = Object.entries(runtimeBenchmarkGuidance?.combined_group_scales ?? {});
  const triRawSummaryTags = buildTriRawSummaryTags(rawprepGroupReport, rawprepMotionOverlayCoverage);
  const editOutcomeCompareSources = compareSources.filter((item) => editOutcomeSourceGroups(studioJob?.tool).includes(item.group));
  const maskAssetCompareSources = compareSources.filter((item) => item.group === '마스크 자산');
  const editOutcomeTitle = editOutcomeSectionTitle(studioJob?.tool);
  const editOutcomeDescription = editOutcomeSectionDescription(studioJob?.tool);
  const featuredEditOutcomeSource = editOutcomeCompareSources.find((item) => item.path === sourcePath)
    ?? editOutcomeCompareSources.find((item) => item.path === comparePrimary)
    ?? editOutcomeCompareSources.find((item) => item.path === compareCandidate)
    ?? editOutcomeCompareSources[0]
    ?? null;
  const remainingEditOutcomeSources = featuredEditOutcomeSource
    ? editOutcomeCompareSources.filter((item) => item.path !== featuredEditOutcomeSource.path)
    : editOutcomeCompareSources;
  const featuredCompareSource = compareSources.find((item) => item.path === sourcePath)
    ?? compareSources.find((item) => item.path === comparePrimary)
    ?? compareSources.find((item) => item.path === compareCandidate)
    ?? compareSources[0]
    ?? null;
  const showExplainableDiagnostics = Boolean(
    rawprepSelectedReference
    || rawprepReferenceReviewItems.length
    || rawprepCandidateReviewItems.length
    || rawprepDiagnosticViews.length,
  );
  const editOutcomeSummaryGridTemplateColumns = compact ? '1fr' : 'repeat(auto-fit, minmax(220px, 1fr))';
  const editOutcomeBoardGridTemplateColumns = compact ? '1fr' : 'minmax(0, 0.94fr) minmax(280px, 1.06fr)';
  const maskAssetGridTemplateColumns = compact ? '1fr' : 'repeat(auto-fit, minmax(176px, 1fr))';
  const compareSummaryGridTemplateColumns = compact ? '1fr' : 'repeat(auto-fit, minmax(220px, 1fr))';
  const compareSourceBoardGridTemplateColumns = compact ? '1fr' : 'minmax(0, 0.92fr) minmax(280px, 1.08fr)';
  const comparePairGridTemplateColumns = compact ? '1fr' : compareGridTemplateColumns;

  return (
    <section
      style={{
        ...sectionCardStyle('warm'),
        gap: 18,
        padding: 24,
        background: studioTokens.color.surface,
        border: `1px solid ${studioTokens.color.line}`,
      }}
    >
      <div style={{ display: 'grid', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <strong style={{ fontSize: 18, color: studioTokens.color.ink }}>현재 작업 공간</strong>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <span style={chipStyle('accent')}>{currentStage?.label ?? stageKey}</span>
            <span style={chipStyle(compareSources.length ? 'success' : 'default')}>비교 소스 {compareSources.length}개</span>
            <span style={chipStyle(savedVersionsCount ? 'default' : 'warning')}>저장 버전 {savedVersionsCount}개</span>
          </div>
        </div>
        <span style={{ fontSize: 13, color: studioTokens.color.muted, lineHeight: 1.6 }}>
          사진, 후보, 품질 상태를 확인하세요.
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: focusGridTemplateColumns, gap: 14, alignItems: 'start' }}>
        <div
          style={{
            minHeight: 260,
            borderRadius: studioTokens.radius.xl,
            border: `1px solid rgba(36, 52, 62, 0.18)`,
            background: `linear-gradient(180deg, ${studioTokens.color.canvasDark} 0%, #12171c 100%)`,
            padding: 18,
            display: 'grid',
            gap: 12,
            boxShadow: 'none',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <span
              style={{
                padding: '6px 10px',
                borderRadius: studioTokens.radius.pill,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: '0.08em',
                background: 'rgba(255, 255, 255, 0.10)',
                color: '#f8fafc',
              }}
            >
              {rawprepGroupReport ? 'RAW 워크벤치' : '편집 스튜디오'}
            </span>
            <span
              style={{
                padding: '6px 10px',
                borderRadius: studioTokens.radius.pill,
                fontSize: 11,
                fontWeight: 700,
                background: sourcePath ? 'rgba(217, 236, 238, 0.16)' : 'rgba(245, 230, 208, 0.16)',
                color: '#f8fafc',
              }}
            >
              {sourcePath ? '현재 작업 소스 고정' : '작업 소스 대기 중'}
            </span>
          </div>
          <div style={{ display: 'grid', gap: 4 }}>
            <strong style={{ fontSize: 13, color: '#f8fafc' }}>현재 작업 원본</strong>
            <span style={{ fontSize: 13, color: 'rgba(248, 250, 252, 0.78)', lineHeight: 1.6 }}>
              {sourcePath ?? '결과를 고르거나 TriRaw 단계를 마치면 현재 작업 원본이 여기서 고정됩니다.'}
            </span>
          </div>
          {sourcePreviewUrl ? (
            <img
              src={sourcePreviewUrl}
              alt="현재 작업 원본 미리보기"
              decoding="async"
              style={{
                width: '100%',
                maxHeight: 420,
                objectFit: 'contain',
                borderRadius: studioTokens.radius.l,
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.10)',
              }}
            />
          ) : (
            <div
              style={{
                minHeight: 220,
                display: 'grid',
                placeItems: 'center',
                borderRadius: studioTokens.radius.l,
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px dashed rgba(255, 255, 255, 0.16)',
                padding: 18,
                textAlign: 'center',
                color: 'rgba(248, 250, 252, 0.76)',
                lineHeight: 1.6,
              }}
            >
              입력 분석이나 TriRaw가 미리보기 가능한 이미지를 만들면 현재 작업 원본이 여기 나타납니다.
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ ...chipStyle('accent'), background: 'rgba(217, 236, 238, 0.18)', color: '#f8fafc', border: '1px solid rgba(217, 236, 238, 0.22)' }}>
              워크플로 상태: {workflowStatusLabel}
            </span>
            {singleRawSummary ? (
              <span style={{ ...chipStyle(singleRawSummary.statusTone), background: 'rgba(255, 255, 255, 0.10)', color: '#f8fafc', border: '1px solid rgba(255, 255, 255, 0.10)' }}>
                {singleRawSummary.statusLabel}
              </span>
            ) : null}
            {rawprepGroupReport?.fallback_reason && rawprepGroupReport.fallback_reason !== 'none' ? (
              <span style={{ ...chipStyle('warning'), background: 'rgba(245, 230, 208, 0.16)', color: '#f8fafc', border: '1px solid rgba(245, 230, 208, 0.18)' }}>
                {formatFallbackReason(rawprepGroupReport.fallback_reason)}
              </span>
            ) : null}
          </div>
        </div>

        <section style={sectionCardStyle('soft')}>
          <div style={{ display: 'grid', gap: 4 }}>
            <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>판단 보드</strong>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
              RAW 결과와 실행 상태를 확인하세요.
            </span>
          </div>

          {rawprepGroupReport ? (
            <div style={tileStyle('accent')}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>TriRaw 요약</strong>
              <span style={{ fontSize: 13, color: studioTokens.color.accent, lineHeight: 1.5 }}>
                현재 산출물: {formatTriRawRecommendedArtifact(rawprepGroupReport.recommended_artifact)}
              </span>
              {triRawSummaryTags.length ? (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {triRawSummaryTags.map((tag) => (
                    <span key={tag.label} style={chipStyle(tag.tone)}>
                      {tag.label}
                    </span>
                  ))}
                </div>
              ) : null}
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>병합 백엔드: {rawprepGroupReport.merge_backend ?? '아직 없음'}</span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>기준 프레임 정책: {formatReferencePolicy(rawprepGroupReport.requested_reference_policy)}</span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>대체 경로 사유: {formatFallbackReason(rawprepGroupReport.fallback_reason)}</span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>대체 기준 RAW: {rawprepGroupReport.selected_single_raw ?? '아직 없음'}</span>
              {rawprepGroupReport.capture_summary?.ev_spacing_quality ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                  촬영 간격: {formatEvSpacingQuality(rawprepGroupReport.capture_summary?.ev_spacing_quality)}
                </span>
              ) : null}
              {typeof rawprepGroupReport.capture_summary?.anchor_index_hint === 'number' ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                  자동 기준 프레임 힌트: {rawprepGroupReport.capture_summary.anchor_index_hint + 1}번 프레임
                </span>
              ) : null}
              {rawprepGroupReport.capture_summary?.capture_warnings?.length ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  촬영 메모: {rawprepGroupReport.capture_summary.capture_warnings.map(formatCaptureWarning).join(', ')}
                </span>
              ) : null}
              {rawprepGroupReport.bracket_coverage?.coverage_quality ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                  HDR 범위: {formatCoverageQuality(rawprepGroupReport.bracket_coverage.coverage_quality)}
                </span>
              ) : null}
              {rawprepGroupReport.bracket_coverage?.scene_class ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                  장면 프로필: {formatCoverageSceneLabel(rawprepGroupReport.bracket_coverage.scene_class)}
                </span>
              ) : null}
              {rawprepGroupReport.bracket_coverage?.scene_traits?.length ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  장면 특징: {rawprepGroupReport.bracket_coverage.scene_traits.map(formatCoverageSceneLabel).join(', ')}
                </span>
              ) : null}
              {typeof rawprepGroupReport.bracket_coverage?.highlight_headroom_fraction === 'number' ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                  하이라이트 여유: {(rawprepGroupReport.bracket_coverage.highlight_headroom_fraction * 100).toFixed(1)}%
                </span>
              ) : null}
              {rawprepGroupReport.bracket_coverage?.coverage_notes?.[0] ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  범위 메모: {rawprepGroupReport.bracket_coverage.coverage_notes[0]}
                </span>
              ) : null}
              {runtimeOverrideSummary?.notes?.[0] ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  런타임 보정: {runtimeOverrideSummary.notes[0]}
                </span>
              ) : null}
              {runtimeOverrideGroups.length ? (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {runtimeOverrideGroups.map((group) => (
                    <span key={group} style={chipStyle('ink')}>
                      {formatRuntimeOverrideGroupLabel(group)}
                    </span>
                  ))}
                </div>
              ) : null}
              {runtimeGuidanceEffects.length ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  벤치마크 피드백: {runtimeGuidanceEffects.map(([effect, count]) => `${formatRuntimeGuidanceEffectLabel(effect)} x${count}`).join(', ')}
                </span>
              ) : null}
              {runtimeGuidanceScales.length ? (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {runtimeGuidanceScales.map(([group, scale]) => (
                    <span key={group} style={chipStyle(scale > 1 ? 'success' : scale < 1 ? 'warning' : 'ink')}>
                      {formatRuntimeOverrideGroupLabel(group)} {scale > 1 ? '강화' : scale < 1 ? '완화' : '유지'}
                    </span>
                  ))}
                </div>
              ) : null}
              {rawprepCandidateReviewItems.length ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  후보 판정: {candidateReasonSummary(rawprepCandidateReviewItems.find((item) => item.isWinner) ?? rawprepCandidateReviewItems[0])}
                </span>
              ) : null}
            </div>
          ) : null}

          {singleRawSummary ? (
            <div style={tileStyle()}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>SingleRaw 처리 요약</strong>
                <span style={chipStyle(singleRawSummary.statusTone)}>{singleRawSummary.statusLabel}</span>
              </div>
              <span style={{ fontSize: 13, color: studioTokens.color.accent, lineHeight: 1.5 }}>
                기본 품질 결과가 준비되었습니다.
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                입력 기준: {singleRawSummary.inputPreviewPath ? basenameFromPath(singleRawSummary.inputPreviewPath) : '아직 없음'}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                복원 기준: {singleRawSummary.recoveryBaselinePath ? basenameFromPath(singleRawSummary.recoveryBaselinePath) : '아직 없음'}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                기본 결과: {singleRawSummary.previewPath ? basenameFromPath(singleRawSummary.previewPath) : '아직 없음'}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                비교 후보: 입력 기준, 기본 결과, 노이즈 보기
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                처리 모드: {singleRawSummary.modeLabel} · {singleRawSummary.qualityPresetLabel}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                런타임 프로파일: {singleRawSummary.runtimeProfileLabel}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                장면 선형 마스터: {singleRawSummary.sceneLinearLabel}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                런타임: {singleRawSummary.runtimeBackendLabel}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                메타데이터: {singleRawSummary.metadataSourceLabel}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                모드 요약: {singleRawSummary.modeSummary}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                처리 요약: {singleRawSummary.processingSummary}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                처리 시간: {singleRawSummary.timingSummary}
              </span>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  노이즈 리포트: {singleRawSummary.noiseReportSummary}
                </span>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  복원 리포트: {singleRawSummary.recoveryReportSummary}
                </span>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  가드레일: {singleRawSummary.artifactGuardrailSummary}
                </span>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  아티팩트 억제: {singleRawSummary.artifactSuppressionSummary}
                </span>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  안전 대체 경로: {singleRawSummary.safetyFallbackSummary}
                </span>
                {singleRawSummary.note ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                    세션 메모: {singleRawSummary.note}
                </span>
              ) : null}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {singleRawSummary.inputPreviewPath ? (
                  <button type="button" style={buttonStyle(comparePrimary === singleRawSummary.inputPreviewPath)} onClick={() => onSelectComparePrimary(singleRawSummary.inputPreviewPath as string)}>
                    입력 기준을 유지 후보로
                  </button>
                ) : null}
                {singleRawSummary.recoveryBaselinePath ? (
                  <button type="button" style={buttonStyle(comparePrimary === singleRawSummary.recoveryBaselinePath)} onClick={() => onSelectComparePrimary(singleRawSummary.recoveryBaselinePath as string)}>
                    복원 기준을 유지 후보로
                  </button>
                ) : null}
                {singleRawSummary.previewPath ? (
                  <button
                    type="button"
                    style={buttonStyle(singleRawSummary.isCurrentSource, singleRawSummary.isCurrentSource)}
                    onClick={() => onAdoptWorkingSource(singleRawSummary.previewPath as string)}
                    disabled={singleRawSummary.isCurrentSource}
                  >
                    {singleRawSummary.isCurrentSource ? '기본 결과 사용 중' : '기본 결과를 작업 소스로 사용'}
                  </button>
                ) : null}
                {singleRawSummary.previewPath ? (
                  <button type="button" style={buttonStyle(comparePrimary === singleRawSummary.previewPath)} onClick={() => onSelectComparePrimary(singleRawSummary.previewPath as string)}>
                    유지 후보로 보기
                  </button>
                ) : null}
                {singleRawSummary.previewPath ? (
                  <button type="button" style={buttonStyle(compareCandidate === singleRawSummary.previewPath)} onClick={() => onSelectCompareCandidate(singleRawSummary.previewPath as string)}>
                    대안 후보로 보기
                  </button>
                ) : null}
                {singleRawSummary.noiseMapPath ? (
                  <button type="button" style={buttonStyle(compareCandidate === singleRawSummary.noiseMapPath)} onClick={() => onSelectCompareCandidate(singleRawSummary.noiseMapPath as string)}>
                    노이즈 보기를 대안 후보로
                  </button>
                ) : null}
                {singleRawSummary.lowlightMapPath ? (
                  <button type="button" style={buttonStyle(compareCandidate === singleRawSummary.lowlightMapPath)} onClick={() => onSelectCompareCandidate(singleRawSummary.lowlightMapPath as string)}>
                    저조도 보기를 대안 후보로
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}

          {singleRawSummary?.recoveryBaselinePath ? (
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>복원 기준 보기</strong>
              {singleRawSummary.recoveryBaselineUrl ? (
                <img src={singleRawSummary.recoveryBaselineUrl} alt="SingleRaw 복원 기준 보기" decoding="async" style={previewFrameStyle()} />
              ) : (
                <div style={emptyPreviewStyle()}>복원 기준 이미지를 아직 준비하지 못했습니다.</div>
              )}
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                정밀 모드가 복원 우선 단계로 넘어가기 직전의 보수 기준 결과입니다.
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                파일: {basenameFromPath(singleRawSummary.recoveryBaselinePath)}
              </span>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" style={buttonStyle(comparePrimary === singleRawSummary.recoveryBaselinePath)} onClick={() => onSelectComparePrimary(singleRawSummary.recoveryBaselinePath as string)}>
                  유지 후보로 보기
                </button>
                <button type="button" style={buttonStyle(compareCandidate === singleRawSummary.recoveryBaselinePath)} onClick={() => onSelectCompareCandidate(singleRawSummary.recoveryBaselinePath as string)}>
                  대안 후보로 보기
                </button>
              </div>
            </div>
          ) : null}

          {singleRawSummary?.noiseMapPath ? (
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>노이즈 보기</strong>
              {singleRawSummary.noiseMapUrl ? (
                <img src={singleRawSummary.noiseMapUrl} alt="SingleRaw 노이즈 보기" decoding="async" style={previewFrameStyle()} />
              ) : (
                <div style={emptyPreviewStyle()}>노이즈 진단 이미지를 아직 준비하지 못했습니다.</div>
              )}
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                노이즈가 남은 세부 구역입니다.
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                진단 요약: {singleRawSummary.noiseReportSummary}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                파일: {basenameFromPath(singleRawSummary.noiseMapPath)}
              </span>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" style={buttonStyle(comparePrimary === singleRawSummary.noiseMapPath)} onClick={() => onSelectComparePrimary(singleRawSummary.noiseMapPath as string)}>
                  유지 후보로 보기
                </button>
                <button type="button" style={buttonStyle(compareCandidate === singleRawSummary.noiseMapPath)} onClick={() => onSelectCompareCandidate(singleRawSummary.noiseMapPath as string)}>
                  대안 후보로 보기
                </button>
              </div>
            </div>
          ) : null}

          {singleRawSummary?.lowlightMapPath ? (
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>저조도 복원 보기</strong>
              {singleRawSummary.lowlightMapUrl ? (
                <img src={singleRawSummary.lowlightMapUrl} alt="SingleRaw 저조도 복원 보기" decoding="async" style={previewFrameStyle()} />
              ) : (
                <div style={emptyPreviewStyle()}>저조도 복원 진단 이미지를 아직 준비하지 못했습니다.</div>
              )}
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                어두운 영역의 밝기와 디테일 변화입니다.
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                진단 요약: {singleRawSummary.recoveryReportSummary}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                파일: {basenameFromPath(singleRawSummary.lowlightMapPath)}
              </span>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" style={buttonStyle(comparePrimary === singleRawSummary.lowlightMapPath)} onClick={() => onSelectComparePrimary(singleRawSummary.lowlightMapPath as string)}>
                  주요 후보로 보기
                </button>
                <button type="button" style={buttonStyle(compareCandidate === singleRawSummary.lowlightMapPath)} onClick={() => onSelectCompareCandidate(singleRawSummary.lowlightMapPath as string)}>
                  대안 후보로 보기
                </button>
              </div>
            </div>
          ) : null}

          {singleRawLensCorrection ? (
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>광학 보정 보기</strong>
              <span style={{ fontSize: 13, color: studioTokens.color.accent, lineHeight: 1.5 }}>
                왜곡 모델: {formatLensCorrectionModel(singleRawLensCorrection.distortionModel)}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                렌즈 키: {singleRawLensCorrection.lensKey ?? '미확인'}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                왜곡 보정: {singleRawLensCorrection.applyDistortion ? '적용 계획 있음' : '기본 계획 유지'}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                비네팅 보정: {singleRawLensCorrection.applyVignette ? '준비됨' : '없음'}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                색수차 보정: {singleRawLensCorrection.applyLateralCa ? '준비됨' : '없음'}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                크롭 여유: {typeof singleRawLensCorrection.cropMarginRatio === 'number'
                  ? `${(singleRawLensCorrection.cropMarginRatio * 100).toFixed(1)}%`
                  : '없음'}
              </span>
              {singleRawSummary?.opticalSummary ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  실제 적용: {singleRawSummary.opticalSummary}
                </span>
              ) : null}
              {singleRawLensCorrection.notes.length ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  계획 메모: {formatLensCorrectionNote(singleRawLensCorrection.notes[0])}
                </span>
              ) : null}
            </div>
          ) : null}

          {showExplainableDiagnostics ? (
            <section style={sectionCardStyle()}>
              <div style={{ display: 'grid', gap: 4 }}>
                <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>RAW 진단</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  기준 프레임, 후보, 진단 맵을 확인하세요.
                </span>
              </div>

              {rawprepSelectedReference ? (
                <div style={tileStyle('accent')}>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>기준 프레임 감시</strong>
                  <span style={{ fontSize: 13, color: studioTokens.color.accent, lineHeight: 1.5 }}>
                    기준 프로브: {rawprepSelectedReference.raw_path}
                  </span>
                  {typeof rawprepSelectedReference.total_score === 'number' ? (
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                      자동 점수: {rawprepSelectedReference.total_score.toFixed(3)}
                    </span>
                  ) : null}
                  {rawprepSelectedReferencePreviewUrl ? (
                    <img src={rawprepSelectedReferencePreviewUrl} alt="선택된 기준 프로브" decoding="async" style={previewFrameStyle()} />
                  ) : (
                    <div style={emptyPreviewStyle()}>기준 프로브 미리보기를 아직 만들지 못했습니다.</div>
                  )}
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                    미리보기 파일: {rawprepSelectedReferencePreviewPath ?? '아직 없음'}
                  </span>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
                    <div style={{ display: 'grid', gap: 8 }}>
                      <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>하이라이트 감시</strong>
                      {rawprepReferenceHighlightWatchUrl ? (
                        <img src={rawprepReferenceHighlightWatchUrl} alt="기준 프로브 하이라이트 감시" decoding="async" style={previewFrameStyle()} />
                      ) : (
                        <div style={emptyPreviewStyle()}>하이라이트 감시 이미지를 아직 만들지 못했습니다.</div>
                      )}
                      <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                        {rawprepSelectedReference.diagnostics?.summary?.highlight ?? '하이라이트 보존 상태입니다.'}
                      </span>
                      {typeof rawprepSelectedReference.diagnostics?.metrics?.highlight_preservation === 'number' ? (
                        <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                          보존율: {(rawprepSelectedReference.diagnostics.metrics.highlight_preservation * 100).toFixed(1)}%
                        </span>
                      ) : null}
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        {rawprepReferenceHighlightWatchPath ? (
                          <>
                            <button type="button" style={buttonStyle(comparePrimary === rawprepReferenceHighlightWatchPath)} onClick={() => onSelectComparePrimary(rawprepReferenceHighlightWatchPath)}>
                              유지 후보로
                            </button>
                            <button type="button" style={buttonStyle(compareCandidate === rawprepReferenceHighlightWatchPath)} onClick={() => onSelectCompareCandidate(rawprepReferenceHighlightWatchPath)}>
                              대안 후보로
                            </button>
                          </>
                        ) : null}
                      </div>
                    </div>
                    <div style={{ display: 'grid', gap: 8 }}>
                      <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>암부 감시</strong>
                      {rawprepReferenceShadowWatchUrl ? (
                        <img src={rawprepReferenceShadowWatchUrl} alt="기준 프로브 암부 감시" decoding="async" style={previewFrameStyle()} />
                      ) : (
                        <div style={emptyPreviewStyle()}>암부 감시 이미지를 아직 만들지 못했습니다.</div>
                      )}
                      <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                        {rawprepSelectedReference.diagnostics?.summary?.shadow ?? '암부 신호 보존 상태입니다.'}
                      </span>
                      {typeof rawprepSelectedReference.diagnostics?.metrics?.shadow_safety === 'number' ? (
                        <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                          암부 안전성: {(rawprepSelectedReference.diagnostics.metrics.shadow_safety * 100).toFixed(1)}%
                        </span>
                      ) : null}
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        {rawprepReferenceShadowWatchPath ? (
                          <>
                            <button type="button" style={buttonStyle(comparePrimary === rawprepReferenceShadowWatchPath)} onClick={() => onSelectComparePrimary(rawprepReferenceShadowWatchPath)}>
                              유지 후보로
                            </button>
                            <button type="button" style={buttonStyle(compareCandidate === rawprepReferenceShadowWatchPath)} onClick={() => onSelectCompareCandidate(rawprepReferenceShadowWatchPath)}>
                              대안 후보로
                            </button>
                          </>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}

              {rawprepReferenceReviewItems.length ? (
                <div style={tileStyle()}>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>기준 프레임 스트립</strong>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                    촬영 순서대로 각 프로브를 훑으면서 점수 차이와 자동 기준 프레임이 왜 특정 장면을 택했는지 확인합니다.
                  </span>
                  <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 4 }}>
                    {rawprepReferenceReviewItems.map((entry, index) => (
                      <div
                        key={`${entry.raw_path}_${index}`}
                        style={{
                          minWidth: 188,
                          maxWidth: 188,
                          display: 'grid',
                          gap: 8,
                          padding: 10,
                          borderRadius: studioTokens.radius.l,
                          border: `1px solid ${entry.isSelected ? studioTokens.color.accent : studioTokens.color.line}`,
                          background: entry.isSelected ? '#f4f9f7' : studioTokens.color.surface,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                          <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>프레임 {entry.metadata_index + 1}</strong>
                          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                            {entry.isSelected ? <span style={chipStyle('success')}>현재 기준</span> : null}
                            {entry.isAutoLeader ? <span style={chipStyle('accent')}>자동 선두</span> : null}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {buildReferenceTags(entry).map((tag) => (
                            <span key={tag.label} style={chipStyle(tag.tone)}>
                              {tag.label}
                            </span>
                          ))}
                        </div>
                        {entry.previewUrl ? (
                          <img src={entry.previewUrl} alt={`기준 프로브 ${entry.metadata_index + 1}`} decoding="async" style={previewFrameStyle()} />
                        ) : (
                          <div style={emptyPreviewStyle()}>프로브 미리보기를 아직 만들지 못했습니다.</div>
                        )}
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          점수: {(entry.total_score ?? 0).toFixed(3)} | 차이: {formatReferenceScoreDelta(entry.scoreDeltaToLeader)}
                        </span>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          주요 근거: {referenceReasonSummary(entry)}
                        </span>
                        {typeof entry.diagnostics?.metrics?.highlight_preservation === 'number' || typeof entry.diagnostics?.metrics?.shadow_safety === 'number' ? (
                          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                            감시 지표: {typeof entry.diagnostics?.metrics?.highlight_preservation === 'number'
                              ? `하이라이트 ${(entry.diagnostics.metrics.highlight_preservation * 100).toFixed(0)}%`
                              : '하이라이트 --'}
                            {' / '}
                            {typeof entry.diagnostics?.metrics?.shadow_safety === 'number'
                              ? `암부 ${(entry.diagnostics.metrics.shadow_safety * 100).toFixed(0)}%`
                              : '암부 --'}
                          </span>
                        ) : null}
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <button type="button" style={buttonStyle(comparePrimary === entry.preview_path)} onClick={() => onSelectComparePrimary(entry.preview_path)}>
                            유지 후보로
                          </button>
                          <button type="button" style={buttonStyle(compareCandidate === entry.preview_path)} onClick={() => onSelectCompareCandidate(entry.preview_path)}>
                            대안 후보로
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {rawprepCandidateReviewItems.length ? (
                <div style={tileStyle()}>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>후보 스트립</strong>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                    노이즈, 움직임, 범위 가드가 적용된 뒤 최종 후보가 왜 병합 결과, 보수 프리뷰, 기준 프레임 유지 경로로 정리됐는지 확인합니다.
                  </span>
                  <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 4 }}>
                    {rawprepCandidateReviewItems.map((entry, index) => (
                      <div
                        key={`${entry.label}_${index}`}
                        style={{
                          minWidth: 188,
                          maxWidth: 188,
                          display: 'grid',
                          gap: 8,
                          padding: 10,
                          borderRadius: studioTokens.radius.l,
                          border: `1px solid ${entry.isWinner ? studioTokens.color.accent : studioTokens.color.line}`,
                          background: entry.isWinner ? '#f4f9f7' : studioTokens.color.surface,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                          <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>{formatCandidateLabel(entry.label)}</strong>
                          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                            {entry.isWinner ? <span style={chipStyle('accent')}>최종 선택</span> : null}
                            {!entry.isWinner && entry.isLeader ? <span style={chipStyle('success')}>점수 선두</span> : null}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {buildCandidateTags(entry).map((tag) => (
                            <span key={tag.label} style={chipStyle(tag.tone)}>
                              {tag.label}
                            </span>
                          ))}
                        </div>
                        {entry.previewUrl ? (
                          <img src={entry.previewUrl} alt={`${formatCandidateLabel(entry.label)} 미리보기`} decoding="async" style={previewFrameStyle()} />
                        ) : (
                          <div style={emptyPreviewStyle()}>후보 미리보기를 아직 만들지 못했습니다.</div>
                        )}
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          점수: {(entry.total_score ?? 0).toFixed(3)} | 차이: {formatReferenceScoreDelta(entry.scoreDeltaToLeader)}
                        </span>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          판정 근거: {candidateReasonSummary(entry)}
                        </span>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <button type="button" style={buttonStyle(comparePrimary === entry.path)} onClick={() => onSelectComparePrimary(entry.path)}>
                            유지 후보로
                          </button>
                          <button type="button" style={buttonStyle(compareCandidate === entry.path)} onClick={() => onSelectCompareCandidate(entry.path)}>
                            대안 후보로
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {rawprepDiagnosticViews.length ? (
                <div style={tileStyle()}>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>TriRaw 진단</strong>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                    움직임, 하이라이트, 암부, 신뢰도, 고스팅 위험, 억제 맵을 확인하세요.
                  </span>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(158px, 1fr))', gap: 10 }}>
                    {rawprepDiagnosticViews.map((item) => (
                      <div key={item.key} style={{ display: 'grid', gap: 8 }}>
                        <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>{item.label}</strong>
                        {item.url ? (
                          <img src={item.url} alt={item.label} decoding="async" style={previewFrameStyle()} />
                        ) : (
                          <div style={emptyPreviewStyle()}>진단 미리보기를 아직 만들지 못했습니다.</div>
                        )}
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          {item.summary}
                        </span>
                        {item.note ? (
                          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                            {item.note}
                          </span>
                        ) : null}
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <button type="button" style={buttonStyle(comparePrimary === item.path)} onClick={() => onSelectComparePrimary(item.path)}>
                            유지 후보로
                          </button>
                          <button type="button" style={buttonStyle(compareCandidate === item.path)} onClick={() => onSelectCompareCandidate(item.path)}>
                            대안 후보로
                          </button>
                        </div>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          파일: {basenameFromPath(item.path)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </section>
          ) : null}

          <div style={tileStyle()}>
            <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>워크플로 준비 상태</strong>
            <span style={{ fontSize: 13, color: studioTokens.color.inkSoft, lineHeight: 1.5 }}>{workflowStatusLabel}</span>
            {workflowPlan ? (
              <>
                {workflowPlan.model_family ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.muted }}>모델 계열: {workflowPlan.model_family}</span>
                ) : null}
                {workflowPlan.selection_profile ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                    선택 프로필: {localizeSelectionProfile(workflowPlan.selection_profile)}
                  </span>
                ) : null}
                {workflowPlan.execution_engine ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                    실행 엔진: {localizeExecutionEngine(workflowPlan.execution_engine)}
                  </span>
                ) : null}
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                  워크플로 소스: {localizeWorkflowSource(workflowPlan.workflow_source)}
                </span>
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                  워크플로 파일: {summarizeWorkflowPath(workflowPlan.workflow_path)}
                </span>
                {workflowPlan.watch_models?.length ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                    감시 목록: {workflowPlan.watch_models.join(', ')}
                  </span>
                ) : null}
                {workflowPlan.public_priors?.length ? (
                  <div style={{ display: 'grid', gap: 6 }}>
                    <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>공개 기준 묶음</strong>
                    {workflowPlan.public_priors.slice(0, 4).map((prior) => (
                      <span key={prior.dataset_id} style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                        {localizeDatasetLabel(prior.label)}: {prior.bootstraps.map(localizeBootstrapLabel).join(', ')}
                      </span>
                    ))}
                  </div>
                ) : null}
                {workflowPlan.bootstrap_rules?.length ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                    부트스트랩 규칙: {localizeBootstrapRule(workflowPlan.bootstrap_rules[0])}
                  </span>
                ) : null}
                {workflowPlan.runtime_prior_bundle ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                    런타임 묶음: {localizeRuntimeBundleLabel(workflowPlan.runtime_prior_bundle.label)}
                  </span>
                ) : null}
                {workflowPlan.runtime_prior_artifacts?.length ? (
                  <div style={{ display: 'grid', gap: 6 }}>
                    <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>로컬 런타임 기준</strong>
                    {workflowPlan.runtime_prior_artifacts.slice(0, 4).map((artifact) => (
                      <span key={artifact.artifact_id} style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                        {localizeRuntimeArtifactLabel(artifact.label)}: {artifact.source_datasets.map(localizeDatasetLabel).join(', ') || artifact.kind}
                        {formatArtifactFootnote(artifact.record_count, artifact.size_bytes)
                          ? ` (${formatArtifactFootnote(artifact.record_count, artifact.size_bytes)})`
                          : ''}
                        {artifact.summary_text ? ` - ${localizeArtifactSummaryText(artifact.summary_text)}` : ''}
                      </span>
                    ))}
                  </div>
                ) : null}
                {workflowPlan.frontier_dataset_activation ? (
                  <div style={{ display: 'grid', gap: 6 }}>
                    <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>Frontier 데이터 활성화</strong>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                      {workflowPlan.frontier_dataset_activation.active_count}/{workflowPlan.frontier_dataset_activation.dataset_count}개 근거 사용 가능 · 로컬 캐시 {workflowPlan.frontier_dataset_activation.local_cache_ready_count}개
                    </span>
                    {workflowPlan.frontier_dataset_items?.slice(0, 4).map((item) => (
                      <span key={item.dataset_id} style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                        {localizeDatasetLabel(item.label)}: {formatFrontierActivationStage(item.activation_stage)}
                        {item.studio_use.length ? ` · ${item.studio_use.slice(0, 2).map(formatFrontierStudioUse).join(', ')}` : ''}
                      </span>
                    ))}
                  </div>
                ) : null}
                {workflowPlan.community_takeaways?.length ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                    최근 신호: {localizeCommunityTakeaway(workflowPlan.community_takeaways[0])}
                  </span>
                ) : null}
              </>
            ) : null}
          </div>

          <div style={tileStyle()}>
            <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>세션 스냅샷</strong>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
              비교 소스 {compareSources.length}개 | 저장 버전 {savedVersionsCount}개 | 내보내기 항목 {exportPackageItems.length}개
            </span>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
              현재 단계 {stages.find((stage) => stage.key === stageKey)?.label ?? stageKey}
            </span>
          </div>

          {studioJob ? (
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>최근 AI 작업</strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>상태: {formatSessionStep(studioJob.status) ?? studioJob.status}</span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>단계: {formatSessionStep(studioJob.current_step) ?? '계획 수립'}</span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>산출물: {studioJob.outputs.length}</span>
              {studioJob.error ? <span style={{ fontSize: 12, color: studioTokens.color.warning }}>오류: {studioJob.error}</span> : null}
            </div>
          ) : null}
        </section>
      </div>

      {studioJob && (editOutcomeCompareSources.length || maskAssetCompareSources.length || selectionState || editLinkage) ? (
        <section style={sectionCardStyle('soft')}>
          <div style={{ display: 'grid', gap: 4 }}>
            <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>{editOutcomeTitle}</strong>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
              {editOutcomeDescription}
            </span>
          </div>

          {editOutcomeCompareSources.length ? (
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>결과 후보 스트립</strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                대표 후보를 확인하고 필요한 결과를 채택하세요.
              </span>
              <div style={{ display: 'grid', gridTemplateColumns: editOutcomeSummaryGridTemplateColumns, gap: 10 }}>
                <div style={tileStyle('accent')}>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>현재 결과 기준</strong>
                  <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>
                    {sourcePath
                      ? `현재 작업 소스는 ${basenameFromPath(sourcePath)}입니다.`
                      : '아직 현재 작업 소스를 정하지 않았습니다.'}
                  </span>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                    결과 후보 {editOutcomeCompareSources.length}개 중 필요한 후보만 유지 후보, 대안 후보, 작업 소스로 올립니다.
                  </span>
                </div>
                {featuredEditOutcomeSource ? (
                  <div style={tileStyle()}>
                    <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>대표 후보</strong>
                    <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>
                      {featuredEditOutcomeSource.label}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                      {featuredEditOutcomeSource.note ?? featuredEditOutcomeSource.group}
                    </span>
                  </div>
                ) : null}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: editOutcomeBoardGridTemplateColumns, gap: 10, alignItems: 'start' }}>
                <div style={tileStyle('accent')}>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>대표 결과 후보</strong>
                  {featuredEditOutcomeSource?.previewUrl ? (
                    <img src={featuredEditOutcomeSource.previewUrl} alt={`${featuredEditOutcomeSource.label} 대표 미리보기`} decoding="async" style={previewFrameStyle()} />
                  ) : (
                    <div style={emptyPreviewStyle()}>대표 후보 미리보기를 아직 만들지 못했습니다.</div>
                  )}
                  <div style={{ display: 'grid', gap: 4 }}>
                    <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>
                      {featuredEditOutcomeSource?.label ?? '대표 후보가 아직 없습니다.'}
                    </strong>
                    {featuredEditOutcomeSource ? (
                      <>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          {featuredEditOutcomeSource.group} · {basenameFromPath(featuredEditOutcomeSource.path)}
                        </span>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                          {featuredEditOutcomeSource.note ?? '현재 작업 소스와 가장 가까운 후보입니다.'}
                        </span>
                      </>
                    ) : null}
                  </div>
                  {featuredEditOutcomeSource ? (
                    <>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {sourcePath === featuredEditOutcomeSource.path ? <span style={chipStyle('success')}>현재 작업 소스</span> : null}
                        {comparePrimary === featuredEditOutcomeSource.path ? <span style={chipStyle('success')}>유지 후보</span> : null}
                        {compareCandidate === featuredEditOutcomeSource.path ? <span style={chipStyle('accent')}>대안 후보</span> : null}
                      </div>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <button type="button" style={buttonStyle(comparePrimary === featuredEditOutcomeSource.path)} onClick={() => onSelectComparePrimary(featuredEditOutcomeSource.path)}>
                          유지 후보로
                        </button>
                        <button type="button" style={buttonStyle(compareCandidate === featuredEditOutcomeSource.path)} onClick={() => onSelectCompareCandidate(featuredEditOutcomeSource.path)}>
                          대안 후보로
                        </button>
                        <button
                          type="button"
                          style={buttonStyle(false, sourcePath === featuredEditOutcomeSource.path)}
                          onClick={() => onAdoptWorkingSource(featuredEditOutcomeSource.path)}
                          disabled={sourcePath === featuredEditOutcomeSource.path}
                        >
                          작업 소스로
                        </button>
                      </div>
                    </>
                  ) : null}
                </div>

                <div style={tileStyle()}>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>나머지 결과 후보</strong>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                    후보를 유지, 대안, 작업 소스로 지정하세요.
                  </span>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {remainingEditOutcomeSources.length ? remainingEditOutcomeSources.map((item) => (
                      <div
                        key={item.key}
                        style={{
                          display: 'grid',
                          gap: 8,
                          padding: compact ? '10px 12px' : '12px 14px',
                          borderRadius: studioTokens.radius.l,
                          border: `1px solid ${sourcePath === item.path ? studioTokens.color.accent : studioTokens.color.line}`,
                          background: sourcePath === item.path ? '#f4f9f7' : studioTokens.color.surface,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                          <div style={{ display: 'grid', gap: 3 }}>
                            <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>{item.label}</strong>
                            <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                              {item.group} · {basenameFromPath(item.path)}
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                            {sourcePath === item.path ? <span style={chipStyle('success')}>현재 작업 소스</span> : null}
                            {comparePrimary === item.path ? <span style={chipStyle('success')}>유지 후보</span> : null}
                            {compareCandidate === item.path ? <span style={chipStyle('accent')}>대안 후보</span> : null}
                          </div>
                        </div>
                        {item.note ? (
                          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>{item.note}</span>
                        ) : null}
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <button type="button" style={buttonStyle(comparePrimary === item.path)} onClick={() => onSelectComparePrimary(item.path)}>
                            유지 후보로
                          </button>
                          <button type="button" style={buttonStyle(compareCandidate === item.path)} onClick={() => onSelectCompareCandidate(item.path)}>
                            대안 후보로
                          </button>
                          <button
                            type="button"
                            style={buttonStyle(false, sourcePath === item.path)}
                            onClick={() => onAdoptWorkingSource(item.path)}
                            disabled={sourcePath === item.path}
                          >
                            작업 소스로
                          </button>
                        </div>
                      </div>
                    )) : (
                      <div style={{ ...tileStyle(), padding: compact ? '10px 12px' : '12px 14px' }}>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                          대표 후보 외에 비교할 추가 결과는 아직 없습니다.
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          {maskAssetCompareSources.length ? (
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>마스크 자산</strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                배경 분리 마스크를 확인하세요.
              </span>
              <div style={{ display: 'grid', gridTemplateColumns: maskAssetGridTemplateColumns, gap: 10 }}>
                {maskAssetCompareSources.map((item) => (
                  <div key={item.key} style={{ display: 'grid', gap: 8 }}>
                    {item.previewUrl ? (
                      <img src={item.previewUrl} alt={`${item.label} 미리보기`} decoding="async" style={previewFrameStyle()} />
                    ) : (
                      <div style={emptyPreviewStyle()}>마스크 미리보기를 아직 만들지 못했습니다.</div>
                    )}
                    <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>{item.label}</strong>
                    {item.note ? (
                      <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>{item.note}</span>
                    ) : null}
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <button type="button" style={buttonStyle(comparePrimary === item.path)} onClick={() => onSelectComparePrimary(item.path)}>
                        유지 후보로
                      </button>
                      <button type="button" style={buttonStyle(compareCandidate === item.path)} onClick={() => onSelectCompareCandidate(item.path)}>
                        대안 후보로
                      </button>
                      <button
                        type="button"
                        style={buttonStyle(selectionState?.source_mask_path === item.path && !selectionSourceMismatch, selectionBusy)}
                        onClick={() => void onApplySelectionMask(item.path)}
                        disabled={selectionBusy}
                      >
                        {selectionBusy && selectionState?.source_mask_path === item.path ? '선택 기준 적용 중...' : '선택 기준으로'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {selectionState ? (
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>현재 선택 기준</strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                자동 선택 마스크를 현재 작업 소스 기준으로 다듬은 뒤, 다음 생성 편집 판단 기준으로 유지합니다.
              </span>
              {selectionPreviewUrl ? (
                <img src={selectionPreviewUrl} alt="현재 선택 미리보기" decoding="async" style={previewFrameStyle()} />
              ) : (
                <div style={emptyPreviewStyle()}>선택 미리보기를 아직 만들지 못했습니다.</div>
              )}
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                {selectionSourceMismatch ?? selectionState.summary}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                기준 마스크: {selectionState.source_mask_path.split(/[\\/]/).pop() ?? selectionState.source_mask_path}
              </span>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" style={buttonStyle(comparePrimary === selectionState.preview_path)} onClick={() => onSelectComparePrimary(selectionState.preview_path)}>
                  유지 후보로
                </button>
                <button type="button" style={buttonStyle(compareCandidate === selectionState.preview_path)} onClick={() => onSelectCompareCandidate(selectionState.preview_path)}>
                  대안 후보로
                </button>
                <button
                  type="button"
                  style={buttonStyle(false, selectionBusy)}
                  onClick={() => void onApplySelectionMask(selectionState.source_mask_path)}
                  disabled={selectionBusy}
                >
                  {selectionBusy ? '선택 미리보기 갱신 중...' : '선택 다시 적용'}
                </button>
              </div>
            </div>
          ) : null}

          {editLinkage ? (
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>DreamGen 연결 상태</strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                {editLinkage.summary}
              </span>
              <div style={{ display: 'grid', gap: 8, gridTemplateColumns: compact ? '1fr' : 'repeat(2, minmax(0, 1fr))' }}>
                <div style={{ display: 'grid', gap: 4 }}>
                  <span style={{ fontSize: 11, color: studioTokens.color.muted }}>현재 작업 소스</span>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>
                    {editLinkage.current_source_path
                      ? `${formatEditLinkageSourceKind(editLinkage.current_source_kind)} · ${editLinkage.current_source_path.split(/[\\/]/).pop() ?? editLinkage.current_source_path}`
                      : '아직 미선택'}
                  </strong>
                </div>
                <div style={{ display: 'grid', gap: 4 }}>
                  <span style={{ fontSize: 11, color: studioTokens.color.muted }}>최근 생성 편집</span>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>
                    {editLinkage.latest_tool
                      ? `${editOutcomeSectionTitle(editLinkage.latest_tool)} · 후보 ${editLinkage.latest_generated_candidate_paths.length}개`
                      : '아직 생성 편집 전'}
                  </strong>
                </div>
                <div style={{ display: 'grid', gap: 4 }}>
                  <span style={{ fontSize: 11, color: studioTokens.color.muted }}>마스크 연결</span>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>
                    {editLinkage.mask_ready
                      ? `준비됨 · ${editLinkage.latest_linked_mask_paths.length || (editLinkage.selection_current_mask_path ? 1 : 0)}개 자산`
                      : '아직 준비 전'}
                  </strong>
                </div>
                <div style={{ display: 'grid', gap: 4 }}>
                  <span style={{ fontSize: 11, color: studioTokens.color.muted }}>다음 단계</span>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>{editLinkage.next_step}</strong>
                </div>
              </div>
              {editLinkage.latest_prompt ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  최근 프롬프트: {editLinkage.latest_prompt}
                </span>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      {showCompareView && compareSources.length ? (
        <section style={sectionCardStyle('soft')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ display: 'grid', gap: 4 }}>
              <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>비교 / 채택</strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                유지 후보와 대안 후보를 비교하고 채택 메모를 확인하세요.
              </span>
            </div>
            <CompareGuidanceDrawer
              outputRoot={outputRoot}
              comparePrimary={comparePrimary}
              compareCandidate={compareCandidate}
              comparePrimaryUrl={comparePrimaryUrl}
              compareCandidateUrl={compareCandidateUrl}
              motionOverlayPath={rawprepMotionOverlayPath}
              motionOverlayUrl={rawprepMotionOverlayUrl}
              motionOverlaySummary={rawprepMotionOverlaySummary}
              motionOverlayCoverage={rawprepMotionOverlayCoverage}
              tool={compareGuideTool}
              onKeepSelect={onKeepCompareSelect}
              onAcceptCandidate={onAcceptCompareCandidate}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: compareSummaryGridTemplateColumns, gap: 10 }}>
            <div style={tileStyle('accent')}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>현재 채택 결과</strong>
              <span style={{ fontSize: 13, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>
                {sourcePath ? basenameFromPath(sourcePath) : '아직 현재 작업 소스를 정하지 않았습니다.'}
              </span>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {sourcePath && comparePrimary === sourcePath ? <span style={chipStyle('success')}>유지 후보와 동일</span> : null}
                {sourcePath && compareCandidate === sourcePath ? <span style={chipStyle('accent')}>대안 후보와 동일</span> : null}
                {!sourcePath ? <span style={chipStyle('warning')}>채택 전</span> : null}
              </div>
            </div>
            <div style={tileStyle('accent')}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>현재 비교 쌍</strong>
              <span style={{ fontSize: 13, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>
                유지 후보 {comparePrimary ? basenameFromPath(comparePrimary) : '미선택'} / 대안 후보 {compareCandidate ? basenameFromPath(compareCandidate) : '미선택'}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                비교 소스 {compareSources.length}개 중 {visibleCompareSources.length}개 표시
              </span>
            </div>
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>빠른 조작</strong>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {['방향키: 대안 후보 이동', 'Shift + 방향키: 유지 후보 이동', 'S: 대안 후보를 유지 후보로', 'A: 대안 후보 채택', 'X: 두 후보 맞바꾸기'].map((hint) => (
                  <span key={hint} style={chipStyle()}>
                    {hint}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: comparePairGridTemplateColumns, gap: 12 }}>
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>유지 후보</strong>
              {comparePrimaryUrl ? (
                <img src={comparePrimaryUrl} alt="유지 후보 미리보기" decoding="async" style={previewFrameStyle()} />
              ) : (
                <div style={emptyPreviewStyle()}>미리보기를 아직 만들지 못했습니다.</div>
              )}
              <span style={{ fontSize: 13, lineHeight: 1.5, color: studioTokens.color.inkSoft }}>
                {comparePrimary ? basenameFromPath(comparePrimary) : '아직 유지 후보를 고르지 않았습니다.'}
              </span>
            </div>
            <div style={tileStyle()}>
              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>대안 후보</strong>
              {compareCandidateUrl ? (
                <img src={compareCandidateUrl} alt="대안 후보 미리보기" decoding="async" style={previewFrameStyle()} />
              ) : (
                <div style={emptyPreviewStyle()}>미리보기를 아직 만들지 못했습니다.</div>
              )}
              <span style={{ fontSize: 13, lineHeight: 1.5, color: studioTokens.color.inkSoft }}>
                {compareCandidate ? basenameFromPath(compareCandidate) : '아직 대안 후보를 고르지 않았습니다.'}
              </span>
            </div>
          </div>

          <div style={{ display: 'grid', gap: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ display: 'grid', gap: 3 }}>
                <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>비교 소스 보드</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                  기준 후보와 대안 후보를 선택하세요.
                </span>
              </div>
              <span style={chipStyle()}>{visibleCompareSources.length} / {compareSources.length}개 표시</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: compareSourceBoardGridTemplateColumns, gap: 10, alignItems: 'start' }}>
              <div style={tileStyle('accent')}>
                <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>대표 비교 소스</strong>
                {featuredCompareSource?.previewUrl ? (
                  <img src={featuredCompareSource.previewUrl} alt={`${featuredCompareSource.label} 대표 미리보기`} decoding="async" style={previewFrameStyle()} />
                ) : (
                  <div style={emptyPreviewStyle()}>대표 비교 미리보기를 아직 만들지 못했습니다.</div>
                )}
                <div style={{ display: 'grid', gap: 4 }}>
                  <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>
                    {featuredCompareSource?.label ?? '대표 비교 소스가 아직 없습니다.'}
                  </strong>
                  {featuredCompareSource ? (
                    <>
                      <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                        {featuredCompareSource.group} · {basenameFromPath(featuredCompareSource.path)}
                      </span>
                      <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                        {featuredCompareSource.note ?? '현재 작업 소스와 가장 가까운 비교 항목입니다.'}
                      </span>
                    </>
                  ) : null}
                </div>
                {featuredCompareSource ? (
                  <>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {comparePrimary === featuredCompareSource.path ? <span style={chipStyle('success')}>유지 후보</span> : null}
                      {compareCandidate === featuredCompareSource.path ? <span style={chipStyle('accent')}>대안 후보</span> : null}
                      {sourcePath === featuredCompareSource.path ? <span style={chipStyle('default')}>현재 작업 원본</span> : null}
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <button type="button" style={buttonStyle(comparePrimary === featuredCompareSource.path)} onClick={() => onSelectComparePrimary(featuredCompareSource.path)}>
                        유지 후보로
                      </button>
                      <button type="button" style={buttonStyle(compareCandidate === featuredCompareSource.path)} onClick={() => onSelectCompareCandidate(featuredCompareSource.path)}>
                        대안 후보로
                      </button>
                      <button
                        type="button"
                        style={buttonStyle(false, sourcePath === featuredCompareSource.path)}
                        onClick={() => onAdoptWorkingSource(featuredCompareSource.path)}
                        disabled={sourcePath === featuredCompareSource.path}
                      >
                        작업 원본으로
                      </button>
                    </div>
                  </>
                ) : null}
              </div>

              <div style={tileStyle()}>
                <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>비교 소스 목록</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  후보를 유지, 대안, 작업 원본으로 지정하세요.
                </span>
                <div style={{ display: 'grid', gap: 8 }}>
                  {visibleCompareSources.map((item) => (
                    <div
                      key={item.key}
                      style={{
                        display: 'grid',
                        gap: 8,
                        padding: compact ? '10px 12px' : '12px 14px',
                        borderRadius: studioTokens.radius.l,
                        border: `1px solid ${featuredCompareSource?.path === item.path ? studioTokens.color.accent : studioTokens.color.line}`,
                        background: featuredCompareSource?.path === item.path ? '#f4f9f7' : studioTokens.color.surface,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                        <div style={{ display: 'grid', gap: 3 }}>
                          <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>{item.label}</strong>
                          <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                            {item.group} · {basenameFromPath(item.path)}
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                          {featuredCompareSource?.path === item.path ? <span style={chipStyle('default')}>대표</span> : null}
                          {comparePrimary === item.path ? <span style={chipStyle('success')}>유지 후보</span> : null}
                          {compareCandidate === item.path ? <span style={chipStyle('accent')}>대안 후보</span> : null}
                        </div>
                      </div>
                      {item.note ? (
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>{item.note}</span>
                      ) : null}
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <button type="button" style={buttonStyle(comparePrimary === item.path)} onClick={() => onSelectComparePrimary(item.path)}>
                          유지 후보로
                        </button>
                        <button type="button" style={buttonStyle(compareCandidate === item.path)} onClick={() => onSelectCompareCandidate(item.path)}>
                          대안 후보로
                        </button>
                        <button
                          type="button"
                          style={buttonStyle(false, sourcePath === item.path)}
                          onClick={() => onAdoptWorkingSource(item.path)}
                          disabled={sourcePath === item.path}
                        >
                          작업 원본으로
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            {compareSources.length > 4 ? (
              <button
                type="button"
                style={buttonStyle(false)}
                onClick={() => setShowAllCompareSources((current) => !current)}
              >
                {showAllCompareSources ? '추가 버전 접기' : `${hiddenCompareSourcesCount}개 버전 더 보기`}
              </button>
            ) : null}
          </div>
        </section>
      ) : null}
    </section>
  );
}
