import React from 'react';
import { buttonStyle, chipStyle, controlStyle, sectionCardStyle, studioTokens, tileStyle } from '../designTokens';
import type { StudioDeadLetterSummary, StudioOpsRootSummary, StudioOpsSummary, StudioTelemetrySource } from '../studioApi';
import { ProviderTelemetryPanel } from './ProviderTelemetryPanel';
import type { OpsEventGroup, PodStatusSnapshot } from './studioWorkspaceTypes';

type OpsEventSourceFilter = 'all' | StudioTelemetrySource;
type OpsEventStatusFilter = 'all' | 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'acknowledged' | 'assigned' | 'resolved' | 'muted';

interface InvestigationPayload {
  acknowledged?: boolean;
  investigation_status?: StudioDeadLetterSummary['investigation_status'];
  assigned_to?: string;
  note?: string;
}

interface StudioOperationsBoardProps {
  opsSummary: StudioOpsSummary | null;
  opsRoots: StudioOpsRootSummary[];
  groupedOpsEvents: OpsEventGroup[];
  opsLoading: boolean;
  opsActionBusy: string | null;
  opsEventSourceFilter: OpsEventSourceFilter;
  opsEventStatusFilter: OpsEventStatusFilter;
  opsEventQuery: string;
  optionGridTemplateColumns: string;
  sessionOutputRoot: string;
  podStatus: PodStatusSnapshot;
  onRefreshOperations: () => void;
  onOpenPodAndContinue: () => void;
  onCheckpointAndStopPod: () => void;
  onStartExternalWorker: (outputRoots?: string[]) => void;
  onStopWorkerQueue: (outputRoots?: string[]) => void;
  onRetryVisibleDeadLetters: () => void;
  onOpenDeadLetterSession: (deadLetter: StudioDeadLetterSummary) => void;
  onUpdateDeadLetterInvestigation: (deadLetter: StudioDeadLetterSummary, payload: InvestigationPayload) => void;
  onDownloadAssetFromRoot: (path: string | null, outputRoot: string) => void;
  onRetryDeadLetter: (deadLetter: StudioDeadLetterSummary) => void;
  onSetOpsEventSourceFilter: (value: OpsEventSourceFilter) => void;
  onSetOpsEventStatusFilter: (value: OpsEventStatusFilter) => void;
  onSetOpsEventQuery: (value: string) => void;
  formatSessionTimestamp: (value: string) => string;
  formatSessionStep: (value: string | null | undefined) => string | null;
  formatWorkerModeLabel: (value: 'embedded' | 'external' | null | undefined) => string;
  formatProviderControlState: (value: StudioOpsSummary['provider']['control_state'] | undefined) => string;
  outputRootLabel: (value: string) => string;
  deadLetterToolLabel: (deadLetter: StudioDeadLetterSummary) => string;
  deadLetterInvestigationLabel: (status: StudioDeadLetterSummary['investigation_status']) => string;
  formatTelemetryEventLabel: (eventType: string) => string;
  telemetrySourceLabel: (source: StudioTelemetrySource) => string;
}

export function StudioOperationsBoard({
  opsSummary,
  opsRoots,
  groupedOpsEvents,
  opsLoading,
  opsActionBusy,
  opsEventSourceFilter,
  opsEventStatusFilter,
  opsEventQuery,
  optionGridTemplateColumns,
  sessionOutputRoot,
  podStatus,
  onRefreshOperations,
  onOpenPodAndContinue,
  onCheckpointAndStopPod,
  onStartExternalWorker,
  onStopWorkerQueue,
  onRetryVisibleDeadLetters,
  onOpenDeadLetterSession,
  onUpdateDeadLetterInvestigation,
  onDownloadAssetFromRoot,
  onRetryDeadLetter,
  onSetOpsEventSourceFilter,
  onSetOpsEventStatusFilter,
  onSetOpsEventQuery,
  formatSessionTimestamp,
  formatSessionStep,
  formatWorkerModeLabel,
  formatProviderControlState,
  outputRootLabel,
  deadLetterToolLabel,
  deadLetterInvestigationLabel,
  formatTelemetryEventLabel,
  telemetrySourceLabel,
}: StudioOperationsBoardProps) {
  function providerValueLabel(value: string | null | undefined): string {
    if (!value) {
      return '없음';
    }
    switch (value.toLowerCase()) {
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
      case 'unconfigured':
        return '미설정';
      case 'pending':
        return '대기 중';
      case 'allocating':
        return '할당 중';
      case 'allocated':
        return '할당 완료';
      case 'migrating':
        return '이동 중';
      case 'migrated':
        return '이동 완료';
      case 'ready':
        return '준비됨';
      case 'unknown':
        return '미확인';
      case 'none':
        return '없음';
      default:
        return value.replace(/[_-]+/g, ' ');
    }
  }

  function studioToolLabel(value: string | null | undefined): string {
    switch (value) {
      case 'removeBg':
        return '배경 제거';
      case 'replaceBg':
        return '배경 교체';
      case 'relight':
        return '조명 보정';
      case 'replaceObject':
        return '오브젝트 편집';
      case 'expandCanvas':
        return '화면 확장';
      case 'retouch':
        return '리터치';
      case 'enhance':
        return '품질 개선';
      case 'finish':
        return '최종 출력';
      case 'compare':
        return '비교 보기';
      default:
        return value ?? 'AI 작업';
    }
  }

  function jobStatusLabel(value: string | null | undefined): string {
    switch (value) {
      case 'RUNNING':
        return '실행 유지';
      case 'EXITED':
        return '종료 요청';
      case 'TERMINATED':
        return '완전 종료';
      case 'UNKNOWN':
        return '미확인';
      case 'queued':
        return '대기';
      case 'submitted':
        return '제출됨';
      case 'running':
        return '실행 중';
      case 'done':
        return '완료';
      case 'failed':
      case 'error':
        return '실패';
      case 'cancelled':
        return '중지됨';
      case 'acknowledged':
        return '확인됨';
      case 'assigned':
        return '배정됨';
      case 'resolved':
        return '해결됨';
      case 'muted':
        return '음소거';
      case 'starting':
        return '시작 중';
      case 'stopping':
        return '종료 중';
      case 'stopped':
        return '종료됨';
      case 'offline':
        return '오프라인';
      case 'open':
        return '열림';
      default:
        return formatSessionStep(value) ?? value ?? '알 수 없음';
    }
  }

  function providerDetailKeyLabel(value: string): string {
    switch (value) {
      case 'control_state':
        return '제어 상태';
      case 'desired_status':
        return '목표 상태';
      case 'public_ip':
        return '공개 주소';
      case 'host_id':
        return '호스트';
      case 'machine_id':
        return '머신';
      case 'allocation_state':
        return '할당 상태';
      case 'migration_state':
        return '이동 상태';
      default:
        return value.replace(/_/g, ' ');
    }
  }

  function formatOpsEventDetail(eventType: string, detail: string | null | undefined): string | null {
    if (!detail) {
      return null;
    }
    if (!['provider_lifecycle_changed', 'provider_migration_detected', 'provider_allocation_changed'].includes(eventType)) {
      return detail;
    }
    const segments = detail.split(' | ').map((segment) => segment.trim()).filter(Boolean);
    const formattedSegments = segments.map((segment) => {
      const matched = /^([a-z_]+)\s+(.+?)\s+->\s+(.+)$/.exec(segment);
      if (!matched) {
        return segment;
      }
      const [, key, previous, current] = matched;
      return `${providerDetailKeyLabel(key)} ${providerValueLabel(previous)} -> ${providerValueLabel(current)}`;
    });
    return formattedSegments.join(' · ');
  }

  function investigationOwnerLabel(value: string | null | undefined): string | null {
    if (!value) {
      return null;
    }
    if (value === 'studio_ops') {
      return '운영 보드';
    }
    return value.replace(/_/g, ' ');
  }

  const compact = typeof window !== 'undefined' && window.innerWidth < studioTokens.breakpoint.laptop;
  const overviewGridTemplateColumns = compact ? '1fr' : optionGridTemplateColumns;
  const supportDeckGridTemplateColumns = compact ? '1fr' : 'minmax(0, 1.02fr) minmax(320px, 0.98fr)';

  const operationsLead = opsSummary ? (() => {
    if (!opsSummary.provider.configured) {
      return {
        tone: 'warm' as const,
        focus: 'Pod 제어와 상태 점검',
        title: 'RunPod 제어 설정 필요',
        description: 'Pod 재개와 체크포인트 종료를 사용하려면 운영 제어를 연결하세요.',
        actionLabel: null as string | null,
      };
    }
    if (opsSummary.dead_letter_count > 0) {
      return {
        tone: 'warm' as const,
        focus: '오류 보관함',
        title: `오류 보관함 ${opsSummary.dead_letter_count}건`,
        description: '실패 원인과 세션 복귀 여부를 확인하세요.',
        actionLabel: null as string | null,
      };
    }
    if (opsSummary.provider.checkpoint_pending_resume) {
      return {
        tone: 'accent' as const,
        focus: 'Pod 제어와 상태 점검',
        title: '체크포인트 재개 필요',
        description: '저장된 체크포인트가 있어 Pod를 다시 열면 직전 세션 흐름을 같은 상태에서 이어갈 수 있습니다.',
        actionLabel: 'Pod 열고 이어서 작업',
      };
    }
    if (opsSummary.worker_stop_requested_at && !opsSummary.active_queue_workers) {
      return {
        tone: 'default' as const,
        focus: '처리 대기열 루트',
        title: '멈춘 대기열을 어느 루트에서 다시 열지 결정하세요',
        description: '재개할 출력 루트를 선택하세요.',
        actionLabel: opsRoots.length ? '보이는 루트 재개' : null,
      };
    }
    if (opsSummary.active_jobs > 0 || opsSummary.running_queue > 0) {
      return {
        tone: 'accent' as const,
        focus: '최근 작업',
        title: '진행 중인 작업 확인',
        description: `활성 작업 ${opsSummary.active_jobs}개, 실행 중 대기열 ${opsSummary.running_queue}개.`,
        actionLabel: null as string | null,
      };
    }
    return {
      tone: 'default' as const,
      focus: '최근 이벤트 타임라인',
      title: '급한 장애 신호 없이 안정적으로 흐르고 있습니다',
      description: '지금은 이벤트 타임라인과 누적 산출물을 훑으며 다음 재개 시점을 차분하게 판단하면 됩니다.',
      actionLabel: null as string | null,
    };
  })() : null;

  const overviewGroups = opsSummary ? [
    {
      key: 'session-flow',
      label: '세션 흐름',
      value: `${opsSummary.total_sessions}개 세션`,
      tone: 'accent' as const,
      lines: [
        `활성 작업 ${opsSummary.active_jobs} · 대기 작업 ${opsSummary.queued_jobs}`,
        `완료 ${opsSummary.completed_jobs} · 실패 ${opsSummary.failed_jobs}`,
      ],
    },
    {
      key: 'queue-pressure',
      label: '대기열 압력',
      value: `${opsSummary.pending_queue + opsSummary.delayed_queue + opsSummary.running_queue}개`,
      tone: 'default' as const,
      lines: [
        `처리 대기열 ${opsSummary.pending_queue} · 지연 대기 ${opsSummary.delayed_queue}`,
        `실행 중 대기열 ${opsSummary.running_queue} · 작업기 ${opsSummary.active_queue_workers}`,
      ],
    },
    {
      key: 'risk',
      label: '장애 신호',
      value: `${opsSummary.dead_letter_count}건 조사 대기`,
      tone: 'warm' as const,
      lines: [
        `오류 보관함 ${opsSummary.dead_letter_count} · 실패 ${opsSummary.failed_jobs}`,
        opsSummary.next_retry_at
          ? `다음 재시도 ${formatSessionTimestamp(opsSummary.next_retry_at)}`
          : '다음 재시도 일정은 아직 없습니다.',
      ],
    },
    {
      key: 'delivery',
      label: '산출물 누적',
      value: `패키지 ${opsSummary.exported_packages}`,
      tone: 'default' as const,
      lines: [
        `저장한 내보내기 ${opsSummary.saved_exports}`,
        opsSummary.last_success_at
          ? `마지막 성공 ${formatSessionTimestamp(opsSummary.last_success_at)}`
          : '최근 성공 기록이 아직 없습니다.',
      ],
    },
  ] : [];

  const overviewChips = opsSummary ? [
    {
      key: 'root',
      label: `현재 루트 ${outputRootLabel(sessionOutputRoot)}`,
      tone: 'accent' as const,
    },
    {
      key: 'worker',
      label: `작업기 ${formatWorkerModeLabel(opsSummary.worker_mode)}`,
      tone: 'default' as const,
    },
    {
      key: 'provider',
      label: `RunPod ${formatProviderControlState(opsSummary.provider.control_state)}`,
      tone: 'default' as const,
    },
    {
      key: 'dead-letter',
      label: opsSummary.dead_letter_count ? `오류 보관함 ${opsSummary.dead_letter_count}` : '오류 보관함 안정',
      tone: opsSummary.dead_letter_count ? 'warning' as const : 'success' as const,
    },
  ] : [];

  return (
    <section style={sectionCardStyle()}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 15, color: studioTokens.color.ink }}>운영 보드</strong>
        <button type="button" style={buttonStyle(false, opsLoading)} onClick={onRefreshOperations} disabled={opsLoading}>
          운영 갱신
        </button>
      </div>
      <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
        현재 출력 루트의 세션, 대기열, 장애 신호, 산출물을 확인하세요.
      </span>

      {opsSummary ? (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {overviewChips.map((chip) => (
              <span key={chip.key} style={chipStyle(chip.tone)}>
                {chip.label}
              </span>
            ))}
          </div>

          {operationsLead ? (
            <article
              style={{
                ...tileStyle(operationsLead.tone),
                gap: 12,
                padding: compact ? '14px 16px' : '16px 18px',
              }}
            >
              <div style={{ display: 'grid', gap: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: studioTokens.color.muted }}>
                  운영 상태
                </span>
                <strong style={{ fontSize: 16, color: studioTokens.color.ink }}>{operationsLead.title}</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.6 }}>
                  {operationsLead.description}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <span style={chipStyle(operationsLead.tone === 'warm' ? 'warning' : operationsLead.tone === 'accent' ? 'accent' : 'default')}>
                  권장 보드 {operationsLead.focus}
                </span>
                <span style={chipStyle('default')}>활성 작업 {opsSummary.active_jobs}</span>
                <span style={chipStyle(opsSummary.dead_letter_count ? 'warning' : 'success')}>
                  오류 보관함 {opsSummary.dead_letter_count}
                </span>
                <span style={chipStyle('default')}>
                  다음 재시도 {opsSummary.next_retry_at ? formatSessionTimestamp(opsSummary.next_retry_at) : '없음'}
                </span>
              </div>
              {operationsLead.actionLabel ? (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {operationsLead.actionLabel === 'Pod 열고 이어서 작업' ? (
                    <button type="button" style={buttonStyle(true, Boolean(opsActionBusy))} onClick={onOpenPodAndContinue} disabled={Boolean(opsActionBusy)}>
                      Pod 열고 이어서 작업
                    </button>
                  ) : null}
                  {operationsLead.actionLabel === '보이는 루트 재개' ? (
                    <button
                      type="button"
                      style={buttonStyle(false, Boolean(opsActionBusy) || !opsRoots.length)}
                      onClick={() => onStartExternalWorker(opsRoots.map((root) => root.output_root))}
                      disabled={Boolean(opsActionBusy) || !opsRoots.length}
                    >
                      보이는 루트 재개
                    </button>
                  ) : null}
                </div>
              ) : null}
            </article>
          ) : null}

          <div style={{ display: 'grid', gridTemplateColumns: overviewGridTemplateColumns, gap: 12 }}>
            {overviewGroups.map((group) => (
              <article
                key={group.key}
                style={{
                  ...tileStyle(group.tone),
                  gap: 10,
                  padding: '16px 18px',
                }}
              >
                <span style={{ fontSize: 11, fontWeight: 700, color: studioTokens.color.muted }}>{group.label}</span>
                <strong style={{ fontSize: 16, color: studioTokens.color.accent }}>{group.value}</strong>
                {group.lines.map((line) => (
                  <span key={line} style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                    {line}
                  </span>
                ))}
              </article>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: supportDeckGridTemplateColumns, gap: 12 }}>
            <ProviderTelemetryPanel
              opsSummary={opsSummary}
              podStatus={podStatus}
              opsActionBusy={opsActionBusy}
              onOpenPodAndContinue={async () => onOpenPodAndContinue()}
              onCheckpointAndStopPod={async () => onCheckpointAndStopPod()}
              onStartExternalWorker={async () => onStartExternalWorker()}
              onStopWorkerQueue={async () => onStopWorkerQueue()}
              formatSessionTimestamp={formatSessionTimestamp}
            />

            <section style={sectionCardStyle('soft')}>
              <div style={{ display: 'grid', gap: 4 }}>
                <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>처리 대기열 루트</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  출력 루트별 큐 압력과 작업기 상태를 묶어 보고, 필요한 루트만 다시 열거나 잠시 멈출 수 있습니다.
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button
                  type="button"
                  style={buttonStyle(false, Boolean(opsActionBusy) || !opsRoots.length)}
                  onClick={() => onStartExternalWorker(opsRoots.map((root) => root.output_root))}
                  disabled={Boolean(opsActionBusy) || !opsRoots.length}
                >
                  보이는 루트 재개
                </button>
                <button
                  type="button"
                  style={buttonStyle(false, Boolean(opsActionBusy) || !opsRoots.length)}
                  onClick={() => onStopWorkerQueue(opsRoots.map((root) => root.output_root))}
                  disabled={Boolean(opsActionBusy) || !opsRoots.length}
                >
                  보이는 루트 중지
                </button>
              </div>
              {opsRoots.length ? (
                <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(260px, 1fr))', gap: 10 }}>
                  {opsRoots.map((root) => (
                    <article
                      key={root.output_root}
                      style={{
                        ...tileStyle(root.output_root === sessionOutputRoot ? 'accent' : 'default'),
                        background: root.output_root === sessionOutputRoot ? studioTokens.color.accentSoft : studioTokens.color.surfaceSoft,
                        gap: 8,
                        padding: '14px 16px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                        <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{outputRootLabel(root.output_root)}</strong>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted }}>{formatWorkerModeLabel(root.worker_mode)}</span>
                      </div>
                      <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                        세션 {root.total_sessions} · 오류 보관함 {root.dead_letter_count}
                      </span>
                      <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                        대기 {root.pending_queue} · 지연 {root.delayed_queue} · 실행 {root.running_queue} · 작업기 {root.active_queue_workers}
                      </span>
                      {root.worker_last_seen_at ? (
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          마지막 작업기 신호 {formatSessionTimestamp(root.worker_last_seen_at)}
                        </span>
                      ) : null}
                      {root.worker_stop_requested_at ? (
                        <span style={{ fontSize: 12, color: studioTokens.color.warning, lineHeight: 1.5 }}>
                          중지 요청 {formatSessionTimestamp(root.worker_stop_requested_at)}
                        </span>
                      ) : null}
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <button type="button" style={buttonStyle(false, Boolean(opsActionBusy))} onClick={() => onStartExternalWorker([root.output_root])} disabled={Boolean(opsActionBusy)}>
                          재개
                        </button>
                        <button type="button" style={buttonStyle(false, Boolean(opsActionBusy))} onClick={() => onStopWorkerQueue([root.output_root])} disabled={Boolean(opsActionBusy)}>
                          중지
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>표시할 출력 루트가 없습니다.</span>
              )}
            </section>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: supportDeckGridTemplateColumns, gap: 12 }}>
            <section style={sectionCardStyle('warm')}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ display: 'grid', gap: 4 }}>
                  <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>오류 보관함</strong>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                    조사 대기, 세션 복귀, 배정, 재시도를 처리합니다.
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted }}>{opsSummary.dead_letter_count}건 조사 대기</span>
                  <button
                    type="button"
                    style={buttonStyle(false, Boolean(opsActionBusy) || !opsSummary.dead_letters.length)}
                    onClick={onRetryVisibleDeadLetters}
                    disabled={Boolean(opsActionBusy) || !opsSummary.dead_letters.length}
                  >
                    전체 재시도
                  </button>
                </div>
              </div>
              {opsSummary.dead_letters.length ? (
                opsSummary.dead_letters.map((deadLetter) => (
                  <article key={`${deadLetter.queue_id}_${deadLetter.finished_at ?? deadLetter.job_id}`} style={tileStyle('warm')}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                      <strong style={{ fontSize: 13, color: '#7b4c17' }}>
                        {deadLetterToolLabel(deadLetter)} · {jobStatusLabel(deadLetter.current_status ?? deadLetter.status)}
                      </strong>
                      <span style={{ fontSize: 12, color: studioTokens.color.warning }}>
                        {deadLetter.finished_at ? formatSessionTimestamp(deadLetter.finished_at) : '시간 정보 없음'}
                      </span>
                    </div>
                    <span style={{ fontSize: 12, color: studioTokens.color.warning, lineHeight: 1.5 }}>
                      {deadLetterInvestigationLabel(deadLetter.investigation_status)}
                      {investigationOwnerLabel(deadLetter.assigned_to) ? ` · ${investigationOwnerLabel(deadLetter.assigned_to)}` : ''}
                      {deadLetter.acknowledged_at ? ` · 확인 ${formatSessionTimestamp(deadLetter.acknowledged_at)}` : ''}
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.warning, lineHeight: 1.5 }}>
                      {deadLetter.session_id} · {deadLetter.job_id} · 시도 {deadLetter.attempts}/{deadLetter.max_attempts}
                      {deadLetter.current_step ? ` · ${formatSessionStep(deadLetter.current_step) ?? deadLetter.current_step}` : ''}
                    </span>
                    {deadLetter.last_error ? (
                      <span style={{ fontSize: 12, color: '#6b4a1d', lineHeight: 1.5, wordBreak: 'break-word' }}>{deadLetter.last_error}</span>
                    ) : null}
                    {deadLetter.note ? (
                      <span style={{ fontSize: 12, color: '#5b4a32', lineHeight: 1.5 }}>{deadLetter.note}</span>
                    ) : null}
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <button type="button" style={buttonStyle(false, Boolean(opsActionBusy))} onClick={() => onOpenDeadLetterSession(deadLetter)} disabled={Boolean(opsActionBusy)}>
                        세션 열기
                      </button>
                      <button
                        type="button"
                        style={buttonStyle(false, Boolean(opsActionBusy))}
                        onClick={() => onUpdateDeadLetterInvestigation(deadLetter, {
                          acknowledged: true,
                          investigation_status: deadLetter.assigned_to ? 'assigned' : 'acknowledged',
                        })}
                        disabled={Boolean(opsActionBusy)}
                      >
                        확인
                      </button>
                      <button
                        type="button"
                        style={buttonStyle(false, Boolean(opsActionBusy))}
                        onClick={() => onUpdateDeadLetterInvestigation(deadLetter, {
                          assigned_to: deadLetter.assigned_to ? '' : 'studio_ops',
                          investigation_status: deadLetter.assigned_to ? 'open' : 'assigned',
                          note: deadLetter.assigned_to ? '' : (deadLetter.note ?? '운영 보드에서 배정함'),
                        })}
                        disabled={Boolean(opsActionBusy)}
                      >
                        {deadLetter.assigned_to ? '배정 해제' : '운영 보드에 배정'}
                      </button>
                      <button
                        type="button"
                        style={buttonStyle(false, Boolean(opsActionBusy))}
                        onClick={() => onUpdateDeadLetterInvestigation(deadLetter, {
                          acknowledged: true,
                          investigation_status: 'resolved',
                          note: deadLetter.note ?? '운영 보드에서 해결 처리함',
                        })}
                        disabled={Boolean(opsActionBusy)}
                      >
                        해결
                      </button>
                      <button
                        type="button"
                        style={buttonStyle(false, Boolean(opsActionBusy))}
                        onClick={() => onUpdateDeadLetterInvestigation(deadLetter, {
                          acknowledged: true,
                          investigation_status: 'muted',
                          note: deadLetter.note ?? '운영 보드에서 음소거 처리함',
                        })}
                        disabled={Boolean(opsActionBusy)}
                      >
                        음소거
                      </button>
                      <button type="button" style={buttonStyle(false, Boolean(opsActionBusy))} onClick={() => onDownloadAssetFromRoot(deadLetter.history_path, deadLetter.output_root)} disabled={Boolean(opsActionBusy)}>
                        로그 다운로드
                      </button>
                      <button type="button" style={buttonStyle(false, Boolean(opsActionBusy))} onClick={() => onRetryDeadLetter(deadLetter)} disabled={Boolean(opsActionBusy)}>
                        {opsActionBusy === `retry_${deadLetter.job_id}` ? '재시도 중...' : '재시도'}
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>조사할 오류 보관함 작업이 없습니다.</span>
              )}
            </section>

            <section style={sectionCardStyle('soft')}>
              <div style={{ display: 'grid', gap: 4 }}>
                <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>최근 작업</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  최근 작업 상태와 문제 신호입니다.
                </span>
              </div>
              {opsSummary.recent_jobs.length ? (
                opsSummary.recent_jobs.map((job) => (
                  <article key={`${job.job_type}_${job.job_id}`} style={tileStyle()}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                      <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>
                        {job.job_type === 'rawprep' ? 'TriRaw' : studioToolLabel(job.tool)} · {jobStatusLabel(job.status)}
                      </strong>
                      <span style={{ fontSize: 12, color: studioTokens.color.muted }}>{formatSessionTimestamp(job.updated_at ?? job.created_at ?? '')}</span>
                    </div>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                      {job.session_id} · 단계 {formatSessionStep(job.current_step) ?? '계획 수립'} · 산출물 {job.output_count}
                    </span>
                    {job.error ? (
                      <span style={{ fontSize: 12, color: studioTokens.color.warning, lineHeight: 1.5 }}>{job.error}</span>
                    ) : null}
                  </article>
                ))
              ) : (
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>표시할 최근 작업이 없습니다.</span>
              )}
            </section>
          </div>

          <section style={sectionCardStyle('soft')}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ display: 'grid', gap: 4 }}>
                <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>최근 이벤트 타임라인</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  운영 이벤트를 소스와 상태로 필터링합니다.
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', width: compact ? '100%' : 'auto' }}>
                <select style={controlStyle} value={opsEventSourceFilter} onChange={(event) => onSetOpsEventSourceFilter(event.target.value as OpsEventSourceFilter)}>
                  <option value="all">모든 소스</option>
                  <option value="queue">처리 대기열</option>
                  <option value="studio">작업 스튜디오</option>
                  <option value="rawprep">TriRaw</option>
                  <option value="export">내보내기</option>
                  <option value="ops">운영</option>
                  <option value="quality_automation">품질 자동화</option>
                  <option value="quality_tuning">튜닝 제안</option>
                </select>
                <select style={controlStyle} value={opsEventStatusFilter} onChange={(event) => onSetOpsEventStatusFilter(event.target.value as OpsEventStatusFilter)}>
                  <option value="all">모든 상태</option>
                  <option value="queued">대기</option>
                  <option value="running">실행 중</option>
                  <option value="done">완료</option>
                  <option value="failed">실패</option>
                  <option value="cancelled">중지됨</option>
                  <option value="acknowledged">확인됨</option>
                  <option value="assigned">배정됨</option>
                  <option value="resolved">해결됨</option>
                  <option value="muted">음소거</option>
                </select>
                <input
                  style={{ ...controlStyle, minWidth: 180 }}
                  value={opsEventQuery}
                  onChange={(event) => onSetOpsEventQuery(event.target.value)}
                  placeholder="작업 ID, 세션, 상세 검색"
                />
              </div>
            </div>
            {groupedOpsEvents.length ? (
              groupedOpsEvents.map((group) => (
                <section key={group.key} style={tileStyle()}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                    <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{group.label}</strong>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>{group.summary}</span>
                  </div>
                  <div style={{ display: 'grid', gap: 8, paddingLeft: 12, borderLeft: `2px solid ${studioTokens.color.line}` }}>
                    {group.items.map((event) => (
                      <article key={event.event_id} style={{ display: 'grid', gap: 6 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                          <strong style={{ fontSize: 12, color: studioTokens.color.accent }}>
                            {formatTelemetryEventLabel(event.event_type)}
                          </strong>
                          <span style={{ fontSize: 12, color: studioTokens.color.muted }}>{formatSessionTimestamp(event.occurred_at)}</span>
                        </div>
                        <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                          {telemetrySourceLabel(event.source)}
                          {event.job_id ? ` · ${event.job_id}` : ''}
                          {event.status ? ` · ${jobStatusLabel(event.status)}` : ''}
                        </span>
                        {event.detail ? (
                          <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.5, wordBreak: 'break-all' }}>{formatOpsEventDetail(event.event_type, event.detail)}</span>
                        ) : null}
                      </article>
                    ))}
                  </div>
                </section>
              ))
            ) : (
              <span style={{ fontSize: 12, color: studioTokens.color.muted }}>필터에 맞는 최근 이벤트가 없습니다.</span>
            )}
          </section>
        </>
      ) : (
        <span style={{ fontSize: 12, color: studioTokens.color.muted }}>{opsLoading ? '운영 지표를 불러오는 중입니다.' : '운영 지표를 아직 읽지 못했습니다.'}</span>
      )}
    </section>
  );
}
