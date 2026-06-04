import React from 'react';
import { buttonStyle, chipStyle, controlStyle, sectionCardStyle, studioTokens, tileStyle } from '../designTokens';
import type { CameraProfile, EntryPreference, IntakePlan, QualityPreset, RawprepReferencePolicy, RawRestorationGoal, RawRestorationGoalOption, SingleRawModePreference } from '../studioApi';
import { StatusToast } from './StatusToast';
import type {
  FocusHighlight,
  QueueAttention,
  SingleRawSummaryView,
  StageItem,
  ToolMetaView,
  WorkspaceModeOption,
} from './studioWorkspaceTypes';

interface ToastState {
  message: string;
  tone?: 'info' | 'success' | 'warning' | 'error';
}

interface StudioSessionSetupSectionProps {
  stages: ReadonlyArray<StageItem>;
  stageKey: string;
  workspaceModes: ReadonlyArray<WorkspaceModeOption>;
  workspaceMode: string;
  toast: ToastState;
  queueAttention: QueueAttention | null;
  focusHighlights: FocusHighlight[];
  optionGridTemplateColumns: string;
  intakeGridTemplateColumns: string;
  toolMeta: ToolMetaView;
  fileInputRef: React.MutableRefObject<HTMLInputElement | null>;
  files: File[];
  uploadDragActive: boolean;
  entryPreference: EntryPreference;
  cameraProfile: CameraProfile;
  qualityPreset: QualityPreset;
  singleRawModePreference: SingleRawModePreference;
  rawRestorationGoal: RawRestorationGoal;
  rawRestorationGoalOptions: ReadonlyArray<RawRestorationGoalOption>;
  rawprepReferencePolicy: RawprepReferencePolicy;
  intakePlan: IntakePlan | null;
  singleRawSummary: SingleRawSummaryView | null;
  intakeBusy: boolean;
  rawprepBusy: boolean;
  opsActionBusy: string | null;
  onSelectWorkspaceMode: (mode: string) => void;
  onResumeQueue: () => void;
  onAnalyze: () => void;
  onResetSession: () => void;
  onRunRawprep: () => void;
  onAdoptWorkingSource: (path: string) => void;
  onFilesSelected: (files: File[]) => void;
  onRemoveSelectedFile: (fileKey: string) => void;
  onSetEntryPreference: (value: EntryPreference) => void;
  onSetCameraProfile: (value: CameraProfile) => void;
  onSetQualityPreset: (value: QualityPreset) => void;
  onSetSingleRawModePreference: (value: SingleRawModePreference) => void;
  onSetRawRestorationGoal: (value: RawRestorationGoal) => void;
  onSetRawprepReferencePolicy: (value: RawprepReferencePolicy) => void;
  onUploadDragEnter: (event: React.DragEvent<HTMLElement>) => void;
  onUploadDragOver: (event: React.DragEvent<HTMLElement>) => void;
  onUploadDragLeave: (event: React.DragEvent<HTMLElement>) => void;
  onUploadDrop: (event: React.DragEvent<HTMLElement>) => void;
  sessionEntryLabel: (entryMode: string) => string;
  uploadFileKey: (file: File) => string;
}

function qualityPresetLabel(value: QualityPreset): string {
  return value === 'safe' ? '안전 우선' : '표준 복원';
}

function qualityPresetDescription(value: QualityPreset): string {
  if (value === 'safe') {
    return '움직임, 고스팅, 좁은 브라켓 상황에서 더 보수적으로 TriRaw를 운용합니다.';
  }
  return '일반적인 브라켓에서 HDR 이득과 디테일 회복을 균형 있게 노립니다.';
}

function singleRawModePreferenceLabel(value: SingleRawModePreference): string {
  switch (value) {
    case 'fast':
      return '고속 모드';
    case 'hq':
      return '정밀 모드';
    case 'safe':
      return '안전 모드';
    default:
      return '자동';
  }
}

function singleRawModePreferenceDescription(value: SingleRawModePreference): string {
  switch (value) {
    case 'fast':
      return '직접 RAW 기본 결과를 빠르게 만듭니다.';
    case 'hq':
      return '복원 여지와 하이라이트 보존을 더 우선하는 정밀 프로파일로 직접 RAW를 시작합니다.';
    case 'safe':
      return '과한 질감 상승과 경계 흔들림을 더 보수적으로 눌러 직접 RAW를 시작합니다.';
    default:
      return '직접 RAW는 품질 프리셋에 따라 자동으로 시작합니다.';
  }
}

function rawprepReferencePolicyLabel(value: RawprepReferencePolicy): string {
  switch (value) {
    case 'first':
      return '1번 RAW 고정';
    case 'middle':
      return '2번 RAW 고정';
    case 'last':
      return '3번 RAW 고정';
    default:
      return '자동 선택';
  }
}

function rawRestorationGoalOption(
  value: RawRestorationGoal,
  options: ReadonlyArray<RawRestorationGoalOption>,
): RawRestorationGoalOption | undefined {
  return options.find((option) => option.id === value);
}

function rawRestorationGoalLabel(value: RawRestorationGoal, options: ReadonlyArray<RawRestorationGoalOption>): string {
  return rawRestorationGoalOption(value, options)?.label ?? value.replace(/_/g, ' ');
}

function rawRestorationGoalDescription(value: RawRestorationGoal, options: ReadonlyArray<RawRestorationGoalOption>): string {
  return rawRestorationGoalOption(value, options)?.summary ?? 'RAW 결과 목표 정책을 불러오는 중입니다.';
}

function basenameFromPath(path: string): string {
  const segments = path.split(/[\\/]/).filter(Boolean);
  return segments[segments.length - 1] ?? path;
}

export function StudioSessionSetupSection({
  stages,
  stageKey,
  workspaceModes,
  workspaceMode,
  toast,
  queueAttention,
  focusHighlights,
  optionGridTemplateColumns,
  intakeGridTemplateColumns,
  toolMeta,
  fileInputRef,
  files,
  uploadDragActive,
  entryPreference,
  cameraProfile,
  qualityPreset,
  singleRawModePreference,
  rawRestorationGoal,
  rawRestorationGoalOptions,
  rawprepReferencePolicy,
  intakePlan,
  singleRawSummary,
  intakeBusy,
  rawprepBusy,
  opsActionBusy,
  onSelectWorkspaceMode,
  onResumeQueue,
  onAnalyze,
  onResetSession,
  onRunRawprep,
  onAdoptWorkingSource,
  onFilesSelected,
  onRemoveSelectedFile,
  onSetEntryPreference,
  onSetCameraProfile,
  onSetQualityPreset,
  onSetSingleRawModePreference,
  onSetRawRestorationGoal,
  onSetRawprepReferencePolicy,
  onUploadDragEnter,
  onUploadDragOver,
  onUploadDragLeave,
  onUploadDrop,
  sessionEntryLabel,
  uploadFileKey,
}: StudioSessionSetupSectionProps) {
  const rawprepGroups = intakePlan?.rawprep_request?.groups ?? [];
  const showAdvancedTriRawControls = workspaceMode === 'advanced' && rawprepGroups.length > 0;
  const currentStage = stages.find((stage) => stage.key === stageKey);
  const activeWorkspaceMode = workspaceModes.find((mode) => mode.key === workspaceMode) ?? workspaceModes[0];
  const selectedRawRestorationGoal = rawRestorationGoalOption(rawRestorationGoal, rawRestorationGoalOptions);
  const hasFiles = files.length > 0;
  const hasIntakePlan = intakePlan !== null;
  const selectedFileSummary = hasFiles ? `${files.length}개 파일 준비됨` : '원본 대기';
  const sessionEntrySummary = intakePlan ? sessionEntryLabel(intakePlan.entry_mode) : '입력 분석 대기 중';
  const bracketSummary = rawprepGroups.length ? `${rawprepGroups.length}개 브라켓 세트 감지` : '브라켓 세트 없음';
  const routeDetail = rawprepGroups.length
    ? '3장 RAW 브라켓을 TriRaw로 준비합니다.'
    : singleRawSummary
      ? '단일 RAW 기본 결과를 편집 소스로 사용할 수 있습니다.'
      : intakePlan?.editable_asset_path
        ? '현재 파일을 바로 편집 소스로 열 수 있습니다.'
        : '입력 분석 후 시작 경로를 자동으로 고릅니다.';
  const nextActionLabel = intakePlan
    ? (intakePlan.entry_mode === 'rawprep_bracket' ? 'TriRaw 실행' : '편집 소스로 열기')
    : '입력 분석';
  const nextActionDetail = intakePlan
    ? routeDetail
    : hasFiles
      ? '파일이 준비되었습니다. 분석을 시작하세요.'
      : 'RAW/JPG/TIFF 파일을 추가하세요.';
  const workspaceSummaryItems = [
    {
      label: '원본',
      value: selectedFileSummary,
      note: hasFiles ? '분석 가능' : '파일 추가 필요',
    },
    {
      label: '시작 경로',
      value: sessionEntrySummary,
      note: routeDetail,
    },
    {
      label: 'RAW 모드',
      value: qualityPresetLabel(qualityPreset),
      note: rawprepGroups.length ? rawRestorationGoalLabel(rawRestorationGoal, rawRestorationGoalOptions) : '단일 RAW/이미지 대기',
    },
    {
      label: '다음',
      value: nextActionLabel,
      note: nextActionDetail,
    },
  ];
  const workflowSteps = [
    {
      label: '원본',
      value: hasFiles ? `${files.length}개` : '대기',
      active: !hasFiles,
      done: hasFiles,
    },
    {
      label: '분석',
      value: hasIntakePlan ? '완료' : hasFiles ? '준비' : '대기',
      active: hasFiles && !hasIntakePlan,
      done: hasIntakePlan,
    },
    {
      label: '시작',
      value: nextActionLabel,
      active: hasIntakePlan,
      done: Boolean(rawprepGroups.length || singleRawSummary || intakePlan?.editable_asset_path),
    },
  ];

  return (
    <>
      <section
        style={{
          ...sectionCardStyle('warm'),
          gap: 18,
          padding: 26,
          background: studioTokens.color.surface,
          border: `1px solid ${studioTokens.color.line}`,
        }}
      >
        <div style={{ display: 'grid', gridTemplateColumns: intakeGridTemplateColumns, gap: 20, alignItems: 'start' }}>
          <div style={{ display: 'grid', gap: 12 }}>
            <span style={{ ...chipStyle('accent'), width: 'fit-content' }}>{currentStage?.label ?? '입력 분석'}</span>
            <div style={{ display: 'grid', gap: 8 }}>
              <h1 style={{ margin: 0, fontSize: 30, lineHeight: 1.05, color: studioTokens.color.accent }}>시작할 사진을 준비하세요</h1>
              <p style={{ margin: 0, maxWidth: 720, color: studioTokens.color.inkSoft, lineHeight: 1.7 }}>
                파일을 올리면 SingleRaw, TriRaw, 일반 편집 경로를 바로 나눕니다.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span style={chipStyle()}>{selectedFileSummary}</span>
              <span style={chipStyle('accent')}>{sessionEntrySummary}</span>
              <span style={chipStyle(rawprepGroups.length ? 'success' : 'default')}>{bracketSummary}</span>
              <span style={chipStyle(qualityPreset === 'safe' ? 'warning' : 'default')}>{qualityPresetLabel(qualityPreset)}</span>
              <span style={chipStyle(selectedRawRestorationGoal?.tone ?? 'default')}>{rawRestorationGoalLabel(rawRestorationGoal, rawRestorationGoalOptions)}</span>
            </div>
          </div>

          <div
            style={{
              ...sectionCardStyle('default'),
              gap: 12,
              padding: 18,
              background: studioTokens.color.panel,
              boxShadow: 'none',
            }}
          >
            <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>세션 흐름</strong>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
              {workspaceSummaryItems.map((item) => (
                <div
                  key={item.label}
                  style={{
                    ...tileStyle('default'),
                    gap: 4,
                    background: studioTokens.color.surface,
                  }}
                >
                  <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: studioTokens.color.muted }}>{item.label}</span>
                  <strong style={{ fontSize: 15, color: studioTokens.color.ink }}>{item.value}</strong>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>{item.note}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10 }}>
          {workflowSteps.map((step, index) => {
            const isActive = step.active;
            return (
              <article
                key={step.label}
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'auto minmax(0, 1fr)',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 12px',
                  borderRadius: studioTokens.radius.m,
                  background: isActive ? studioTokens.color.accent : step.done ? studioTokens.color.successSoft : studioTokens.color.surface,
                  border: isActive ? `1px solid ${studioTokens.color.accent}` : `1px solid ${studioTokens.color.line}`,
                  color: isActive ? studioTokens.color.surface : studioTokens.color.ink,
                }}
              >
                <span
                  style={{
                    width: 26,
                    height: 26,
                    display: 'grid',
                    placeItems: 'center',
                    borderRadius: studioTokens.radius.pill,
                    fontSize: 11,
                    fontWeight: 900,
                    background: isActive ? 'rgba(255, 255, 255, 0.15)' : studioTokens.color.surface,
                    color: isActive ? studioTokens.color.surface : step.done ? studioTokens.color.success : studioTokens.color.muted,
                    border: isActive ? '1px solid rgba(255, 255, 255, 0.20)' : `1px solid ${studioTokens.color.line}`,
                  }}
                >
                  {index + 1}
                </span>
                <span style={{ display: 'grid', gap: 2, minWidth: 0 }}>
                  <strong style={{ fontSize: 13, fontWeight: 800 }}>{step.label}</strong>
                  <span
                    style={{
                      fontSize: 11,
                      color: isActive ? 'rgba(255, 255, 255, 0.78)' : studioTokens.color.muted,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {step.value}
                  </span>
                </span>
              </article>
            );
          })}
        </section>

        <section style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 12, fontWeight: 800, color: studioTokens.color.inkSoft }}>보기 범위</span>
          {workspaceModes.map((mode) => (
            <button
              key={mode.key}
              type="button"
              style={buttonStyle(mode.key === workspaceMode)}
              onClick={() => onSelectWorkspaceMode(mode.key)}
            >
              {mode.label}
            </button>
          ))}
          <span style={{ color: studioTokens.color.muted, fontSize: 12, lineHeight: 1.5 }}>
            {activeWorkspaceMode.description}
          </span>
        </section>
      </section>

      <StatusToast message={toast.message} tone={toast.tone} />

      {queueAttention ? (
        <section
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: 16,
            flexWrap: 'wrap',
            alignItems: 'center',
            padding: '14px 16px',
            borderRadius: studioTokens.radius.xl,
            border: `1px solid ${queueAttention.border}`,
            background: queueAttention.tone,
          }}
        >
          <div style={{ display: 'grid', gap: 4 }}>
            <strong style={{ fontSize: 14, color: studioTokens.color.accent }}>{queueAttention.title}</strong>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.6 }}>{queueAttention.description}</span>
          </div>
          <button
            type="button"
            style={buttonStyle(false, Boolean(opsActionBusy))}
            onClick={onResumeQueue}
            disabled={Boolean(opsActionBusy)}
          >
            {queueAttention.actionLabel}
          </button>
        </section>
      ) : null}

      <section style={{ display: 'grid', gridTemplateColumns: optionGridTemplateColumns, gap: 12 }}>
        {focusHighlights.map((item) => (
          <article
            key={item.label}
            style={{
              ...tileStyle(),
              gap: 6,
              background: item.tone,
              border: `1px solid ${item.border}`,
            }}
          >
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: studioTokens.color.muted }}>{item.label}</span>
            <strong style={{ fontSize: 15, color: studioTokens.color.ink, lineHeight: 1.4 }}>{item.value}</strong>
          </article>
        ))}
      </section>

      <section
        style={{
          ...sectionCardStyle('soft'),
          gap: 18,
        }}
      >
        <header style={{ display: 'grid', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ display: 'grid', gap: 4 }}>
              <strong style={{ fontSize: 15, color: studioTokens.color.ink }}>세션 준비 작업대</strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.6 }}>
                원본을 추가하고 시작 경로를 선택하세요.
              </span>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span style={chipStyle()}>{selectedFileSummary}</span>
              <span style={chipStyle('accent')}>{sessionEntrySummary}</span>
              <span style={chipStyle(rawprepGroups.length ? 'success' : 'default')}>{bracketSummary}</span>
            </div>
          </div>
        </header>

        <div style={{ display: 'grid', gridTemplateColumns: intakeGridTemplateColumns, gap: 16 }}>
          <section
            style={{
              ...sectionCardStyle('default'),
              gap: 14,
              background: studioTokens.color.surface,
              boxShadow: 'none',
            }}
          >
            <div style={{ display: 'grid', gap: 4 }}>
              <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>원본 추가</strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                RAW, JPG, TIFF 파일을 추가하세요.
              </span>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".rw2,.cr3,.dng,.nef,.arw,.orf,.raf,.jpg,.jpeg,.png,.tif,.tiff,.webp,.heic"
              style={{ display: 'none' }}
              onChange={(event) => onFilesSelected(Array.from(event.target.files ?? []))}
            />
            <div
              role="button"
              tabIndex={0}
              onClick={() => fileInputRef.current?.click()}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  fileInputRef.current?.click();
                }
              }}
              onDragEnter={onUploadDragEnter}
              onDragOver={onUploadDragOver}
              onDragLeave={onUploadDragLeave}
              onDrop={onUploadDrop}
              style={{
                display: 'grid',
                gap: 8,
                padding: 18,
                borderRadius: studioTokens.radius.xl,
                border: uploadDragActive ? `1px solid ${studioTokens.color.accent}` : '1px dashed #b8c4d3',
                background: uploadDragActive ? studioTokens.color.surfaceTint : studioTokens.color.surface,
                cursor: 'pointer',
                transition: 'background 120ms ease, border-color 120ms ease',
              }}
            >
              <strong style={{ fontSize: 14, color: studioTokens.color.accent }}>
                {uploadDragActive ? '여기에 파일을 놓으면 교체됩니다.' : 'RAW/JPG/TIFF 세트를 여기로 드래그하거나 클릭해서 선택해 주세요.'}
              </strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                3장 RAW 브라켓, 단일 RAW, JPG/TIFF/PNG/WebP/HEIC를 지원합니다.
              </span>
            </div>
            <button type="button" style={buttonStyle(false)} onClick={() => fileInputRef.current?.click()}>
              파일 선택
            </button>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>현재 선택: {files.length ? `${files.length}개 파일` : '선택된 파일 없음'}</span>
              {files.length ? (
                <button type="button" style={buttonStyle(false)} onClick={onResetSession}>
                  모두 비우기
                </button>
              ) : null}
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              {files.map((file) => (
                <div
                  key={uploadFileKey(file)}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 12,
                    padding: '10px 12px',
                    borderRadius: studioTokens.radius.m,
                    background: studioTokens.color.surface,
                    border: `1px solid ${studioTokens.color.line}`,
                    fontSize: 13,
                    alignItems: 'center',
                  }}
                >
                  <div style={{ display: 'grid', gap: 2, minWidth: 0 }}>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</span>
                    <span style={{ color: studioTokens.color.muted, fontSize: 12 }}>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                  </div>
                  <button type="button" style={buttonStyle(false)} onClick={() => onRemoveSelectedFile(uploadFileKey(file))}>
                    제외
                  </button>
                </div>
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: optionGridTemplateColumns, gap: 12 }}>
              <label style={{ display: 'grid', gap: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: studioTokens.color.inkSoft }}>진입 선호</span>
                <select style={controlStyle} value={entryPreference} onChange={(event) => onSetEntryPreference(event.target.value as EntryPreference)}>
                  <option value="auto">자동 판단</option>
                  <option value="direct_edit">직접 보정 우선</option>
                </select>
              </label>
              <label style={{ display: 'grid', gap: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: studioTokens.color.inkSoft }}>카메라 프로파일</span>
                <select style={controlStyle} value={cameraProfile} onChange={(event) => onSetCameraProfile(event.target.value as CameraProfile)}>
                  <option value="auto">자동 감지</option>
                  <option value="tz99">TZ99</option>
                  <option value="eos_r8">EOS R8</option>
                  <option value="sony_a7c_ii">Sony A7C II</option>
                  <option value="nikon_zf">Nikon Zf</option>
                  <option value="fuji_x_s20">Fuji X-S20</option>
                </select>
              </label>
              <div style={{ display: 'grid', gap: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: studioTokens.color.inkSoft }}>TriRaw 운영 모드</span>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
                  {(['balanced', 'safe'] as QualityPreset[]).map((preset) => {
                    const active = qualityPreset === preset;
                    return (
                      <button
                        key={preset}
                        type="button"
                        style={{
                          ...tileStyle(active ? 'accent' : 'soft'),
                          textAlign: 'left',
                          gap: 6,
                          cursor: 'pointer',
                          border: active ? `1px solid ${studioTokens.color.accent}` : `1px solid ${studioTokens.color.line}`,
                          background: active ? studioTokens.color.accentSoft : studioTokens.color.surface,
                        }}
                        onClick={() => onSetQualityPreset(preset)}
                      >
                        <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>{qualityPresetLabel(preset)}</strong>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          {qualityPresetDescription(preset)}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div style={{ display: 'grid', gap: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: studioTokens.color.inkSoft }}>RAW 결과 목표</span>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
                  {rawRestorationGoalOptions.map((option) => {
                    const goal = option.id;
                    const active = rawRestorationGoal === goal;
                    return (
                      <button
                        key={goal}
                        type="button"
                        style={{
                          ...tileStyle(active ? 'accent' : 'soft'),
                          textAlign: 'left',
                          gap: 6,
                          cursor: 'pointer',
                          border: active ? `1px solid ${studioTokens.color.accent}` : `1px solid ${studioTokens.color.line}`,
                          background: active ? studioTokens.color.accentSoft : studioTokens.color.surface,
                        }}
                        onClick={() => onSetRawRestorationGoal(goal)}
                      >
                        <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>{option.label}</strong>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          {option.summary}
                        </span>
                        {option.requires_human_review ? (
                          <span style={{ ...chipStyle('warning'), width: 'fit-content' }}>검수 필요</span>
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div style={{ display: 'grid', gap: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: studioTokens.color.inkSoft }}>SingleRaw 처리 모드</span>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
                  {(['auto', 'fast', 'hq', 'safe'] as SingleRawModePreference[]).map((mode) => {
                    const active = singleRawModePreference === mode;
                    return (
                      <button
                        key={mode}
                        type="button"
                        style={{
                          ...tileStyle(active ? 'accent' : 'soft'),
                          textAlign: 'left',
                          gap: 6,
                          cursor: 'pointer',
                          border: active ? `1px solid ${studioTokens.color.accent}` : `1px solid ${studioTokens.color.line}`,
                          background: active ? studioTokens.color.accentSoft : studioTokens.color.surface,
                        }}
                        onClick={() => onSetSingleRawModePreference(mode)}
                      >
                        <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>{singleRawModePreferenceLabel(mode)}</strong>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          {singleRawModePreferenceDescription(mode)}
                        </span>
                      </button>
                    );
                  })}
                </div>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                  직접 RAW 세션에 적용됩니다. TriRaw 브라켓은 TriRaw 품질 프리셋을 따릅니다.
                </span>
              </div>
              {showAdvancedTriRawControls ? (
                <label style={{ display: 'grid', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: studioTokens.color.inkSoft }}>TriRaw 기준 프레임 고정</span>
                  <select
                    style={controlStyle}
                    value={rawprepReferencePolicy}
                    onChange={(event) => onSetRawprepReferencePolicy(event.target.value as RawprepReferencePolicy)}
                    disabled={!rawprepGroups.length}
                  >
                    <option value="auto">자동 선택</option>
                    <option value="first">1번 RAW 고정</option>
                    <option value="middle">2번 RAW 고정</option>
                    <option value="last">3번 RAW 고정</option>
                  </select>
                </label>
              ) : (
                <div style={{ display: 'grid', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: studioTokens.color.inkSoft }}>TriRaw 기준 프레임</span>
                  <div style={tileStyle('soft')}>
                    <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>자동 선택 사용 중</strong>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                      기준 프레임 고정은 확장 작업 공간에서 사용할 수 있습니다.
                    </span>
                  </div>
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button type="button" style={buttonStyle(true, !files.length || intakeBusy)} onClick={onAnalyze} disabled={!files.length || intakeBusy}>
                입력 분석 시작
              </button>
              <button type="button" style={buttonStyle(false)} onClick={onResetSession}>
                초기화
              </button>
            </div>
          </section>

          <section
            style={{
              ...sectionCardStyle('default'),
              gap: 14,
              background: 'rgba(255, 255, 255, 0.78)',
              boxShadow: 'none',
            }}
          >
            <div style={{ display: 'grid', gap: 4 }}>
              <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>다음 작업</strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                현재 파일 상태에서 바로 이어갈 작업입니다.
              </span>
            </div>
            <span style={{ fontSize: 13, color: studioTokens.color.muted, lineHeight: 1.55 }}>
              {nextActionDetail}
            </span>
            {intakePlan ? (
              <>
                <div
                  style={{
                    ...tileStyle(intakePlan.entry_mode === 'rawprep_bracket' ? 'accent' : 'default'),
                    background: intakePlan.entry_mode === 'rawprep_bracket' ? studioTokens.color.accentSoft : studioTokens.color.surfaceSoft,
                  }}
                >
                  <strong style={{ color: studioTokens.color.ink }}>{sessionEntryLabel(intakePlan.entry_mode)}</strong>
                </div>
                {intakePlan.entry_mode === 'direct_edit_raw' && singleRawSummary ? (
                  <div
                    style={{
                      ...tileStyle('accent'),
                      gap: 10,
                      background: studioTokens.color.surfaceTint,
                      border: `1px solid ${studioTokens.color.line}`,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                      <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>SingleRaw 기본 결과</strong>
                      <span style={chipStyle(singleRawSummary.statusTone)}>{singleRawSummary.statusLabel}</span>
                    </div>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.6 }}>
                      기본 결과, 장면 선형 마스터, 노이즈 보기를 준비했습니다.
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                      입력 기준: {singleRawSummary.inputPreviewPath ? basenameFromPath(singleRawSummary.inputPreviewPath) : '아직 없음'}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                      기본 결과: {singleRawSummary.previewPath ? basenameFromPath(singleRawSummary.previewPath) : '아직 없음'}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                      처리 모드: {singleRawSummary.modeLabel} · {singleRawSummary.qualityPresetLabel}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                      런타임 프로파일: {singleRawSummary.runtimeProfileLabel}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                      장면 선형: {singleRawSummary.sceneLinearLabel}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                      노이즈 보기: {singleRawSummary.noiseMapPath ? basenameFromPath(singleRawSummary.noiseMapPath) : '아직 없음'}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.6 }}>
                      모드 요약: {singleRawSummary.modeSummary}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.6 }}>
                      처리 요약: {singleRawSummary.processingSummary}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.6 }}>
                      노이즈 리포트: {singleRawSummary.noiseReportSummary}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.6 }}>
                      가드레일: {singleRawSummary.artifactGuardrailSummary}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.6 }}>
                      비교 후보: 입력 기준, 기본 결과
                    </span>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        style={buttonStyle(false, !singleRawSummary.previewPath || singleRawSummary.isCurrentSource)}
                        onClick={() => singleRawSummary.previewPath ? onAdoptWorkingSource(singleRawSummary.previewPath) : undefined}
                        disabled={!singleRawSummary.previewPath || singleRawSummary.isCurrentSource}
                      >
                        {singleRawSummary.isCurrentSource ? '기본 결과 사용 중' : '기본 결과로 시작'}
                      </button>
                    </div>
                  </div>
                ) : null}
                {rawprepGroups.length ? (
                  <div style={{ display: 'grid', gap: 10 }}>
                    {rawprepGroups.map((group, index) => (
                      <div
                        key={group.bracket_id}
                        style={{
                          ...tileStyle('accent'),
                          gap: 8,
                          background: studioTokens.color.surfaceTint,
                          border: `1px solid ${studioTokens.color.line}`,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                          <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>
                            브라켓 {index + 1} · {group.bracket_id}
                          </strong>
                          <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                            {group.raw_files.length}장 RAW · {qualityPresetLabel(qualityPreset)} · {rawRestorationGoalLabel(rawRestorationGoal, rawRestorationGoalOptions)}
                          </span>
                        </div>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          {rawRestorationGoalDescription(rawRestorationGoal, rawRestorationGoalOptions)}
                        </span>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                          기준 프레임 전략: {showAdvancedTriRawControls ? rawprepReferencePolicyLabel(rawprepReferencePolicy) : '자동 선택'}
                        </span>
                        <div style={{ display: 'grid', gap: 6 }}>
                          {group.raw_files.map((path, fileIndex) => (
                            <div key={`${group.bracket_id}_${fileIndex}_${path}`} style={tileStyle()}>
                              <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>프레임 {fileIndex + 1}</strong>
                              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>{basenameFromPath(path)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  intakePlan.staged_assets.map((asset) => (
                    <div key={asset.staged_path} style={tileStyle()}>
                      <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>{asset.file_name}</strong>
                      <span style={{ fontSize: 12, color: studioTokens.color.muted }}>{asset.staged_path}</span>
                    </div>
                  ))
                )}
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  {intakePlan.rawprep_request ? (
                    <button type="button" style={buttonStyle(true, rawprepBusy)} onClick={onRunRawprep} disabled={rawprepBusy}>
                      TriRaw 실행
                    </button>
                  ) : null}
                  {intakePlan.editable_asset_path ? (
                    <button type="button" style={buttonStyle(false)} onClick={() => onAdoptWorkingSource(intakePlan.editable_asset_path as string)}>
                      직접 보정으로 열기
                    </button>
                  ) : null}
                </div>
              </>
            ) : null}
          </section>
        </div>
      </section>
    </>
  );
}
