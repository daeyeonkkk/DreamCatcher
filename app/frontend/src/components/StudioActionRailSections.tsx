import React from 'react';
import { buttonStyle, chipStyle, sectionCardStyle, studioTokens, tileStyle } from '../designTokens';
import type { RawprepJobRecord, StudioJobRecord } from '../studioApi';
import type { WorkspacePreset } from '../workspacePresetLibrary';
import type { StudioSavedVersionSnapshot } from '../studioSessionRecovery';

interface StudioActionRailSectionsProps {
  isAdvancedWorkspace: boolean;
  optionGridTemplateColumns: string;
  standardSecondaryGridTemplateColumns: string;
  filesCount: number;
  intakeBusy: boolean;
  rawprepRequestAvailable: boolean;
  rawprepBusy: boolean;
  studioJobBusy: boolean;
  editableAssetPath: string | null;
  canRunStudioJob: boolean;
  rawprepJob: RawprepJobRecord | null;
  studioJob: StudioJobRecord | null;
  canRetryRawprep: boolean;
  canRetryStudioJob: boolean;
  toolLabel: string;
  canUndoWorkingSource: boolean;
  canRedoWorkingSource: boolean;
  sourcePath: string | null;
  sourcePreviewable: boolean;
  exportBusy: boolean;
  intakeReady: boolean;
  latestResultPath: string | null;
  exportPackageItemsCount: number;
  packageBusy: boolean;
  lastExportPath: string | null;
  lastPackagePath: string | null;
  sourceHistory: string[];
  sourceHistoryIndex: number;
  savedVersions: StudioSavedVersionSnapshot[];
  workspacePresets: WorkspacePreset[];
  presetImportInputRef: React.MutableRefObject<HTMLInputElement | null>;
  finishDeliveryDesk: React.ReactNode;
  showFinishDeliveryDesk: boolean;
  onOpenAdvancedWorkspace: () => void;
  onAnalyze: () => void;
  onRunRawprep: () => void;
  onAdoptEditableAsset: () => void;
  onRunStudioJob: () => void;
  onCancelRawprep: () => void;
  onCancelStudioJob: () => void;
  onRetryRawprep: () => void;
  onRetryStudioJob: () => void;
  onUndoWorkingSource: () => void;
  onRedoWorkingSource: () => void;
  onSaveCurrentVersion: () => void;
  onExportWorkingSource: () => void;
  onExportLatestResult: () => void;
  onDownloadLatestResult: () => void;
  onExportSessionPackage: () => void;
  onSaveCurrentWorkspacePreset: () => void;
  onImportWorkspacePreset: (event: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  onApplyWorkspacePreset: (preset: WorkspacePreset) => void;
  onExportWorkspacePreset: (preset: WorkspacePreset) => void;
  onRemoveWorkspacePreset: (presetId: string) => void;
  onApplyWorkingSourceHistory: (index: number) => void;
  onUseSavedVersion: (path: string) => void;
  onDownloadSavedVersion: (path: string) => void;
  onRemoveSavedVersion: (versionId: string) => void;
  basenameFromPath: (path: string) => string;
}

const workspacePresetToolLabels: Record<WorkspacePreset['activeTool'], string> = {
  removeBg: '배경 제거',
  replaceBg: '배경 교체',
  relight: '조명 보정',
  replaceObject: '오브젝트 편집',
  expandCanvas: '화면 확장',
  retouch: '리터치',
  enhance: '품질 개선',
  finish: '최종 출력',
  compare: '비교 보기',
};

function formatWorkspacePresetToolLabel(value: WorkspacePreset['activeTool']): string {
  return workspacePresetToolLabels[value] ?? value;
}

function formatWorkspacePresetQualityLabel(value: WorkspacePreset['qualityPreset']): string {
  return value === 'safe' ? '안전 우선' : '표준 복원';
}

function formatWorkspacePresetSingleRawModeLabel(value: WorkspacePreset['singleRawModePreference']): string {
  switch (value) {
    case 'fast':
      return 'SingleRaw 고속';
    case 'hq':
      return 'SingleRaw 정밀';
    case 'safe':
      return 'SingleRaw 안전';
    default:
      return 'SingleRaw 자동';
  }
}

function formatWorkspacePresetModeLabel(value: WorkspacePreset['workspaceMode']): string {
  return value === 'advanced' ? '확장 작업 공간' : '기본 작업 공간';
}

function formatWorkspacePresetName(name: string): string {
  const generatedMatch = /^(removeBg|replaceBg|relight|replaceObject|expandCanvas|retouch|enhance|finish|compare) preset (.+)$/.exec(name);
  if (generatedMatch) {
    return `${formatWorkspacePresetToolLabel(generatedMatch[1] as WorkspacePreset['activeTool'])} 프리셋 ${generatedMatch[2]}`;
  }
  const importedMatch = /^Imported preset (.+)$/.exec(name);
  if (importedMatch) {
    return `가져온 프리셋 ${importedMatch[1]}`;
  }
  return name;
}

function pickActionHighlights<T extends { key: string }>(actions: T[], primaryActionKeys: string[]): { primary: T[]; secondary: T[] } {
  const primary = primaryActionKeys
    .map((key) => actions.find((action) => action.key === key) ?? null)
    .filter((action): action is T => action !== null);
  const fallbackPrimary = primary.length ? primary : actions.slice(0, Math.min(actions.length, 2));
  const secondary = actions.filter((action) => !fallbackPrimary.some((primaryAction) => primaryAction.key === action.key));
  return { primary: fallbackPrimary, secondary };
}

export function StudioActionRailSections({
  isAdvancedWorkspace,
  optionGridTemplateColumns: _optionGridTemplateColumns,
  standardSecondaryGridTemplateColumns,
  filesCount,
  intakeBusy,
  rawprepRequestAvailable,
  rawprepBusy,
  studioJobBusy,
  editableAssetPath,
  canRunStudioJob,
  rawprepJob,
  studioJob,
  canRetryRawprep,
  canRetryStudioJob,
  toolLabel,
  canUndoWorkingSource,
  canRedoWorkingSource,
  sourcePath,
  sourcePreviewable,
  exportBusy,
  intakeReady,
  latestResultPath,
  exportPackageItemsCount,
  packageBusy,
  lastExportPath,
  lastPackagePath,
  sourceHistory,
  sourceHistoryIndex,
  savedVersions,
  workspacePresets,
  presetImportInputRef,
  finishDeliveryDesk,
  showFinishDeliveryDesk,
  onOpenAdvancedWorkspace,
  onAnalyze,
  onRunRawprep,
  onAdoptEditableAsset,
  onRunStudioJob,
  onCancelRawprep,
  onCancelStudioJob,
  onRetryRawprep,
  onRetryStudioJob,
  onUndoWorkingSource,
  onRedoWorkingSource,
  onSaveCurrentVersion,
  onExportWorkingSource,
  onExportLatestResult,
  onDownloadLatestResult,
  onExportSessionPackage,
  onSaveCurrentWorkspacePreset,
  onImportWorkspacePreset,
  onApplyWorkspacePreset,
  onExportWorkspacePreset,
  onRemoveWorkspacePreset,
  onApplyWorkingSourceHistory,
  onUseSavedVersion,
  onDownloadSavedVersion,
  onRemoveSavedVersion,
  basenameFromPath,
}: StudioActionRailSectionsProps) {
  const compact = typeof window !== 'undefined' && window.innerWidth < studioTokens.breakpoint.laptop;
  const actionGridTemplateColumns = compact ? '1fr' : standardSecondaryGridTemplateColumns;
  const actionButtonGridTemplateColumns = compact ? '1fr' : 'repeat(auto-fit, minmax(156px, 1fr))';
  const workflowSteps = [
    {
      key: 'intake',
      label: '입력 확인',
      tone: filesCount ? 'accent' : 'default',
    },
    {
      key: 'rawprep',
      label: 'RAW 준비',
      tone: rawprepRequestAvailable ? 'accent' : 'default',
    },
    {
      key: 'edit',
      label: '편집 작업',
      tone: editableAssetPath ? 'success' : 'default',
    },
    {
      key: 'tool',
      label: toolLabel,
      tone: canRunStudioJob ? 'warning' : 'default',
    },
  ] as const;

  const standardActionGroups = [
    {
      key: 'prepare',
      eyebrow: '준비 흐름',
      title: '입력 확인과 RAW 준비',
      description: '입력 파일과 RAW 준비 상태입니다.',
      summary: rawprepRequestAvailable
        ? 'TriRaw 실행이 가능한 입력입니다.'
        : '일반 이미지를 편집할 수 있습니다.',
      tone: 'accent' as const,
      actions: [
        {
          key: 'analyze',
          label: '입력 분석 다시 실행',
          primary: true,
          disabled: !filesCount || intakeBusy,
          onClick: onAnalyze,
        },
        {
          key: 'rawprep',
          label: 'TriRaw 실행',
          primary: false,
          disabled: !rawprepRequestAvailable || rawprepBusy,
          onClick: onRunRawprep,
        },
      ],
    },
    {
      key: 'edit',
      eyebrow: '편집 흐름',
      title: '작업 소스 채택과 현재 도구 실행',
      description: '작업 소스를 선택하고 도구를 실행합니다.',
      summary: editableAssetPath
        ? '편집 기준 소스가 준비되어 있습니다.'
        : '작업 소스를 선택해 주세요.',
      tone: 'default' as const,
      actions: [
        {
          key: 'direct',
          label: '편집 작업으로 진입',
          primary: false,
          disabled: !editableAssetPath,
          onClick: onAdoptEditableAsset,
        },
        {
          key: 'ai',
          label: `${toolLabel} 실행`,
          primary: false,
          disabled: !canRunStudioJob,
          onClick: onRunStudioJob,
        },
      ],
    },
  ];

  const advancedActionGroups = [
    {
      key: 'execution',
      title: '실행 제어',
      description: '입력 분석, TriRaw, 도구 실행, 중지, 재시도.',
      summary: rawprepBusy
        ? 'TriRaw 실행 중입니다.'
        : editableAssetPath && sourcePath !== editableAssetPath
          ? '편집 기준 소스를 선택하세요.'
          : canRunStudioJob
            ? '도구를 실행할 수 있습니다.'
            : '입력 파일을 확인하세요.',
      tone: 'accent' as const,
      primaryActionKeys: rawprepBusy
        ? ['rawprep-cancel', 'analyze']
        : editableAssetPath && sourcePath !== editableAssetPath
          ? ['direct', 'studio-run']
          : canRunStudioJob
            ? ['studio-run', 'analyze']
            : rawprepRequestAvailable
              ? ['rawprep', 'analyze']
              : ['analyze', 'direct'],
      actions: [
        {
          key: 'analyze',
          label: '입력 분석 다시 실행',
          primary: true,
          disabled: !filesCount || intakeBusy,
          onClick: onAnalyze,
        },
        {
          key: 'rawprep',
          label: 'TriRaw 실행',
          primary: false,
          disabled: !rawprepRequestAvailable || rawprepBusy,
          onClick: onRunRawprep,
        },
        {
          key: 'direct',
          label: '직접 보정으로 진입',
          primary: false,
          disabled: !editableAssetPath,
          onClick: onAdoptEditableAsset,
        },
        {
          key: 'studio-run',
          label: `${toolLabel} 실행`,
          primary: false,
          disabled: !canRunStudioJob,
          onClick: onRunStudioJob,
        },
        {
          key: 'rawprep-cancel',
          label: 'TriRaw 중지',
          primary: false,
          disabled: !rawprepJob?.job_id || !rawprepBusy,
          onClick: onCancelRawprep,
        },
        {
          key: 'studio-cancel',
          label: `${toolLabel} 중지`,
          primary: false,
          disabled: !studioJob?.job_id || !studioJobBusy,
          onClick: onCancelStudioJob,
        },
        {
          key: 'rawprep-retry',
          label: 'TriRaw 재시도',
          primary: false,
          disabled: !canRetryRawprep,
          onClick: onRetryRawprep,
        },
        {
          key: 'studio-retry',
          label: `${toolLabel} AI 재시도`,
          primary: false,
          disabled: !canRetryStudioJob,
          onClick: onRetryStudioJob,
        },
      ],
    },
    {
      key: 'delivery',
      title: '버전과 결과물',
      description: '버전 저장, 결과 저장, 세션 패키지.',
      summary: latestResultPath
        ? '결과 저장과 세션 패키지를 만들 수 있습니다.'
        : sourcePath
          ? '현재 버전을 저장할 수 있습니다.'
          : '작업 소스를 선택해 주세요.',
      tone: 'default' as const,
      primaryActionKeys: latestResultPath
        ? ['save-version', 'export-latest', 'export-package']
        : sourcePath
          ? ['save-version', 'export-working']
          : ['save-version', 'undo'],
      actions: [
        {
          key: 'undo',
          label: '원본함 되돌리기',
          primary: false,
          disabled: !canUndoWorkingSource,
          onClick: onUndoWorkingSource,
        },
        {
          key: 'redo',
          label: '원본함 다시 적용',
          primary: false,
          disabled: !canRedoWorkingSource,
          onClick: onRedoWorkingSource,
        },
        {
          key: 'save-version',
          label: '현재 버전 저장',
          primary: false,
          disabled: !sourcePath,
          onClick: onSaveCurrentVersion,
        },
        {
          key: 'export-working',
          label: '작업 소스 저장',
          primary: false,
          disabled: !sourcePath || exportBusy || !intakeReady,
          onClick: onExportWorkingSource,
        },
        {
          key: 'export-latest',
          label: '결과 저장',
          primary: false,
          disabled: !latestResultPath || exportBusy || !intakeReady,
          onClick: onExportLatestResult,
        },
        {
          key: 'download-latest',
          label: '결과 다운로드',
          primary: false,
          disabled: !latestResultPath,
          onClick: onDownloadLatestResult,
        },
        {
          key: 'export-package',
          label: '세션 패키지 저장',
          primary: false,
          disabled: !intakeReady || !exportPackageItemsCount || packageBusy,
          onClick: onExportSessionPackage,
        },
      ],
    },
  ];

  const nextAction = (() => {
    if (!filesCount) {
      return {
        title: '원본 추가부터 시작',
        description: 'RAW나 편집용 이미지를 추가하세요.',
        tone: 'default' as const,
        actionLabel: null,
        actionDisabled: true,
        onClick: undefined,
      };
    }
    if (intakeBusy) {
      return {
        title: '입력 분석 진행 중',
        description: '입력 파일을 확인하고 있습니다.',
        tone: 'accent' as const,
        actionLabel: null,
        actionDisabled: true,
        onClick: undefined,
      };
    }
    if (rawprepBusy) {
      return {
        title: 'TriRaw 준비 진행 중',
        description: '브라켓을 병합하고 있습니다.',
        tone: 'accent' as const,
        actionLabel: null,
        actionDisabled: true,
        onClick: undefined,
      };
    }
    if (rawprepRequestAvailable && !editableAssetPath) {
      return {
        title: 'TriRaw 실행 필요',
        description: '브라켓 입력입니다. TriRaw 결과를 만든 뒤 편집하세요.',
        tone: 'accent' as const,
        actionLabel: 'TriRaw 실행',
        actionDisabled: !rawprepRequestAvailable,
        onClick: onRunRawprep,
      };
    }
    if (editableAssetPath && sourcePath !== editableAssetPath) {
      return {
        title: '편집 기준 소스를 채택',
        description: '이 결과를 작업 소스로 사용하세요.',
        tone: 'success' as const,
        actionLabel: '편집 작업으로 진입',
        actionDisabled: !editableAssetPath,
        onClick: onAdoptEditableAsset,
      };
    }
    if (canRunStudioJob) {
      return {
        title: `${toolLabel} 실행 준비 완료`,
        description: '현재 도구를 실행할 수 있습니다.',
        tone: 'warning' as const,
        actionLabel: `${toolLabel} 실행`,
        actionDisabled: !canRunStudioJob,
        onClick: onRunStudioJob,
      };
    }
    if (sourcePath) {
      return {
        title: '결과 확인',
        description: '작업 소스와 저장 버전을 확인하세요.',
        tone: 'default' as const,
        actionLabel: null,
        actionDisabled: true,
        onClick: undefined,
      };
    }
    return {
      title: '대기 중',
      description: '파일을 추가하거나 작업 소스를 선택하세요.',
      tone: 'default' as const,
      actionLabel: null,
      actionDisabled: true,
      onClick: undefined,
    };
  })();

  return (
    <>
      <section style={sectionCardStyle()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div style={{ display: 'grid', gap: 4 }}>
            <strong style={{ fontSize: 15, color: studioTokens.color.ink }}>다음 액션</strong>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
              {isAdvancedWorkspace
                ? '운영, 복구, 저장까지 관리합니다.'
                : '필요한 작업만 표시합니다.'}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {workflowSteps.map((step) => (
            <span key={step.key} style={chipStyle(step.tone)}>
              {step.label}
            </span>
          ))}
        </div>

        <article
          style={{
            ...tileStyle(nextAction.tone),
            gap: 10,
            padding: compact ? '14px 16px' : '16px 18px',
          }}
        >
          <div style={{ display: 'grid', gap: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: studioTokens.color.muted }}>
              지금 할 일
            </span>
            <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>{nextAction.title}</strong>
            <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>{nextAction.description}</span>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {nextAction.actionLabel && nextAction.onClick ? (
              <button
                type="button"
                style={buttonStyle(nextAction.tone === 'accent' || nextAction.tone === 'warning', nextAction.actionDisabled)}
                onClick={nextAction.onClick}
                disabled={nextAction.actionDisabled}
              >
                {nextAction.actionLabel}
              </button>
            ) : null}
            {!isAdvancedWorkspace ? (
              <button type="button" style={buttonStyle(false)} onClick={onOpenAdvancedWorkspace}>
                확장 작업 공간 열기
              </button>
            ) : null}
          </div>
        </article>

        {isAdvancedWorkspace ? (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: actionGridTemplateColumns, gap: 12 }}>
              {advancedActionGroups.map((group) => (
                (() => {
                  const highlighted = pickActionHighlights(group.actions, group.primaryActionKeys);
                  return (
                    <article
                      key={group.key}
                      style={{
                        ...tileStyle(group.tone),
                        gap: 12,
                        padding: '16px 18px',
                      }}
                    >
                      <div style={{ display: 'grid', gap: 4 }}>
                        <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{group.title}</strong>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>{group.description}</span>
                      </div>
                      <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>{group.summary}</span>
                      <div style={{ display: 'grid', gap: 6 }}>
                        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: studioTokens.color.muted }}>
                          핵심 액션
                        </span>
                        <div style={{ display: 'grid', gridTemplateColumns: actionButtonGridTemplateColumns, gap: 8 }}>
                          {highlighted.primary.map((action) => (
                            <button
                              key={action.key}
                              type="button"
                              style={buttonStyle(true, action.disabled)}
                              onClick={action.onClick}
                              disabled={action.disabled}
                            >
                              {action.label}
                            </button>
                          ))}
                        </div>
                      </div>
                      {highlighted.secondary.length ? (
                        <div style={{ display: 'grid', gap: 6 }}>
                          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: studioTokens.color.muted }}>
                            보조 제어
                          </span>
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            {highlighted.secondary.map((action) => (
                              <button
                                key={action.key}
                                type="button"
                                style={buttonStyle(false, action.disabled)}
                                onClick={action.onClick}
                                disabled={action.disabled}
                              >
                                {action.label}
                              </button>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </article>
                  );
                })()
              ))}
            </div>

            {lastExportPath ? <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5, wordBreak: 'break-all' }}>마지막 저장: {lastExportPath}</span> : null}
            {lastPackagePath ? <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5, wordBreak: 'break-all' }}>패키지: {lastPackagePath}</span> : null}
          </>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: actionGridTemplateColumns, gap: 12 }}>
              {standardActionGroups.map((group) => (
                <article
                  key={group.key}
                  style={{
                    ...tileStyle(group.tone),
                    gap: 12,
                    padding: '16px 18px',
                  }}
                >
                  <div style={{ display: 'grid', gap: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: studioTokens.color.muted }}>
                      {group.eyebrow}
                    </span>
                    <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{group.title}</strong>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>{group.description}</span>
                  </div>
                  <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.5 }}>{group.summary}</span>
                  <div style={{ display: 'grid', gridTemplateColumns: actionButtonGridTemplateColumns, gap: 8 }}>
                    {group.actions.map((action) => (
                      <button
                        key={action.key}
                        type="button"
                        style={buttonStyle(action.primary, action.disabled)}
                        onClick={action.onClick}
                        disabled={action.disabled}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                </article>
              ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: actionGridTemplateColumns, gap: 12 }}>
              <article style={tileStyle()}>
                <div style={{ display: 'grid', gap: 4 }}>
                  <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>버전 & 복구</strong>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                    작업 소스를 되돌리거나, 중요한 순간을 저장해 다음 단계 기준점으로 씁니다.
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button type="button" style={buttonStyle(false, !canUndoWorkingSource)} onClick={onUndoWorkingSource} disabled={!canUndoWorkingSource}>되돌리기</button>
                  <button type="button" style={buttonStyle(false, !canRedoWorkingSource)} onClick={onRedoWorkingSource} disabled={!canRedoWorkingSource}>다시 적용</button>
                  <button type="button" style={buttonStyle(false, !sourcePath)} onClick={onSaveCurrentVersion} disabled={!sourcePath}>현재 버전 저장</button>
                </div>
                <div style={{ display: 'grid', gap: 4 }}>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted }}>히스토리 {sourceHistory.length ? `${sourceHistoryIndex + 1} / ${sourceHistory.length}` : '기록 없음'}</span>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted }}>저장 버전 {savedVersions.length}개</span>
                </div>
              </article>

              <article style={tileStyle()}>
                <div style={{ display: 'grid', gap: 4 }}>
                  <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>저장 & 결과물</strong>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                    현재 작업 소스와 최신 결과를 저장합니다.
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button type="button" style={buttonStyle(false, !sourcePath || exportBusy || !intakeReady)} onClick={onExportWorkingSource} disabled={!sourcePath || exportBusy || !intakeReady}>작업 소스 저장</button>
                  <button type="button" style={buttonStyle(false, !latestResultPath || exportBusy || !intakeReady)} onClick={onExportLatestResult} disabled={!latestResultPath || exportBusy || !intakeReady}>결과 저장</button>
                  <button type="button" style={buttonStyle(false, !latestResultPath)} onClick={onDownloadLatestResult} disabled={!latestResultPath}>결과 다운로드</button>
                  <button type="button" style={buttonStyle(false, !intakeReady || !exportPackageItemsCount || packageBusy)} onClick={onExportSessionPackage} disabled={!intakeReady || !exportPackageItemsCount || packageBusy}>세션 패키지 저장</button>
                </div>
                {lastExportPath ? <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5, wordBreak: 'break-all' }}>마지막 저장: {lastExportPath}</span> : null}
                {lastPackagePath ? <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5, wordBreak: 'break-all' }}>패키지: {lastPackagePath}</span> : null}
              </article>
            </div>
          </>
        )}

        {!sourcePreviewable && sourcePath ? (
          <span style={{ fontSize: 12, color: studioTokens.color.warning, lineHeight: 1.5 }}>
            AI 실행에는 현재 TIFF/JPG/PNG/WebP 같은 래스터 작업 소스가 필요합니다. TriRaw 결과나 직접 편집본을 작업 소스로 선택해 주세요.
          </span>
        ) : null}
      </section>

      {isAdvancedWorkspace ? (
        <>
          <section style={sectionCardStyle()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ display: 'grid', gap: 4 }}>
                <strong style={{ fontSize: 15, color: studioTokens.color.ink }}>사전 설정 보관함</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  자주 쓰는 도구, 프롬프트, 슬라이더 조합을 저장하고 다시 적용할 수 있습니다.
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <input
                  ref={presetImportInputRef}
                  type="file"
                  accept="application/json,.json"
                  style={{ display: 'none' }}
                  onChange={(event) => void onImportWorkspacePreset(event)}
                />
                <button type="button" style={buttonStyle(false)} onClick={onSaveCurrentWorkspacePreset}>현재 세팅 저장</button>
                <button type="button" style={buttonStyle(false)} onClick={() => presetImportInputRef.current?.click()}>프리셋 불러오기</button>
              </div>
            </div>
            {workspacePresets.length ? (
              workspacePresets.map((preset) => (
                <article key={preset.id} style={tileStyle()}>
                  <div style={{ display: 'grid', gap: 4 }}>
                    <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{formatWorkspacePresetName(preset.name)}</strong>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                      {formatWorkspacePresetToolLabel(preset.activeTool)} | {formatWorkspacePresetQualityLabel(preset.qualityPreset)} | {formatWorkspacePresetSingleRawModeLabel(preset.singleRawModePreference)} | {formatWorkspacePresetModeLabel(preset.workspaceMode)}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                      강도 {preset.sliders.strength} | 현실감 {preset.sliders.realism} | 질감 보존 {preset.sliders.preserveTexture}
                    </span>
                    {preset.prompt ? (
                      <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>{preset.prompt}</span>
                    ) : null}
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button type="button" style={buttonStyle(false)} onClick={() => onApplyWorkspacePreset(preset)}>적용</button>
                    <button type="button" style={buttonStyle(false)} onClick={() => onExportWorkspacePreset(preset)}>내보내기</button>
                    <button type="button" style={buttonStyle(false)} onClick={() => onRemoveWorkspacePreset(preset.id)}>삭제</button>
                  </div>
                </article>
              ))
            ) : (
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                저장된 프리셋이 아직 없습니다.
              </span>
            )}
          </section>

          {showFinishDeliveryDesk ? finishDeliveryDesk : null}

          <section style={sectionCardStyle()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <strong style={{ fontSize: 15, color: studioTokens.color.ink }}>작업 기록</strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>Ctrl/Cmd+Z, Shift+Ctrl/Cmd+Z</span>
            </div>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
              작업 소스 이동을 되돌리고, 중요한 버전을 고정해서 다시 꺼내 쓸 수 있습니다.
            </span>

            <div style={{ display: 'grid', gap: 8 }}>
              <strong style={{ fontSize: 12, color: studioTokens.color.inkSoft }}>원본함</strong>
              {sourceHistory.length ? (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {sourceHistory.map((path, index) => (
                    <button
                      key={`${path}_${index}`}
                      type="button"
                      style={buttonStyle(index === sourceHistoryIndex)}
                      onClick={() => onApplyWorkingSourceHistory(index)}
                    >
                      {index + 1}. {basenameFromPath(path)}
                    </button>
                  ))}
                </div>
              ) : (
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>아직 기록된 작업 소스 이동이 없습니다.</span>
              )}
            </div>

            <div style={{ display: 'grid', gap: 8 }}>
              <strong style={{ fontSize: 12, color: studioTokens.color.inkSoft }}>저장한 버전</strong>
              {savedVersions.length ? (
                savedVersions.map((version) => (
                  <article key={version.id} style={tileStyle()}>
                    <div style={{ display: 'grid', gap: 4 }}>
                      <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{version.label}</strong>
                      <span style={{ fontSize: 12, color: studioTokens.color.muted }}>{new Date(version.createdAt).toLocaleString()}</span>
                      <span style={{ fontSize: 12, color: studioTokens.color.muted, wordBreak: 'break-all' }}>{version.path}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <button type="button" style={buttonStyle(sourcePath === version.path)} onClick={() => onUseSavedVersion(version.path)}>이 버전 사용</button>
                      <button type="button" style={buttonStyle(false)} onClick={() => onDownloadSavedVersion(version.path)}>다운로드</button>
                      <button type="button" style={buttonStyle(false)} onClick={() => onRemoveSavedVersion(version.id)}>제거</button>
                    </div>
                  </article>
                ))
              ) : (
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>저장된 버전이 없습니다. 중요한 작업 소스를 저장해 두면 패키지에도 포함됩니다.</span>
              )}
            </div>
          </section>
        </>
      ) : null}
    </>
  );
}
