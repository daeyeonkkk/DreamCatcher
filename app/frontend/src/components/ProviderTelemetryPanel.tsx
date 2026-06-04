import React from 'react';
import { buttonStyle, chipStyle, sectionCardStyle, tileStyle, studioTokens } from '../designTokens';
import type { StudioOpsSummary } from '../studioApi';

interface PodStatusSummary {
  label: string;
  tone: string;
  border: string;
  reason: string;
}

interface ProviderTelemetryPanelProps {
  opsSummary: StudioOpsSummary;
  podStatus: PodStatusSummary;
  opsActionBusy: string | null;
  onOpenPodAndContinue: () => Promise<void>;
  onCheckpointAndStopPod: () => Promise<void>;
  onStartExternalWorker: () => Promise<void>;
  onStopWorkerQueue: () => Promise<void>;
  formatSessionTimestamp: (value: string) => string;
}

export function ProviderTelemetryPanel({
  opsSummary,
  podStatus,
  opsActionBusy,
  onOpenPodAndContinue,
  onCheckpointAndStopPod,
  onStartExternalWorker,
  onStopWorkerQueue,
  formatSessionTimestamp,
}: ProviderTelemetryPanelProps) {
  const compact = typeof window !== 'undefined' && window.innerWidth < studioTokens.breakpoint.laptop;
  function formatProviderToken(value: string | null | undefined): string {
    if (!value) {
      return '정보 없음';
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
      case 'locked':
        return '잠금됨';
      case 'interruptible':
        return '중단 가능';
      case 'network_volume_attached':
        return '네트워크 볼륨 연결됨';
      case 'unknown':
        return '미확인';
      default:
        return value.replace(/[_-]+/g, ' ');
    }
  }

  function providerStateLabel(value: string | null | undefined): string {
    return formatProviderToken(value);
  }

  function lifecycleHintLabel(value: string): string {
    if (value.startsWith('migration:')) {
      return `이동 상태 ${formatProviderToken(value.slice('migration:'.length))}`;
    }
    if (value.startsWith('allocation:')) {
      return `할당 상태 ${formatProviderToken(value.slice('allocation:'.length))}`;
    }
    return formatProviderToken(value);
  }

  const lifecycleSummary = opsSummary.provider.lifecycle_hints.length
    ? opsSummary.provider.lifecycle_hints.map(lifecycleHintLabel).join(' · ')
    : '외부 힌트 없음';
  const panelGridTemplateColumns = compact ? '1fr' : 'repeat(auto-fit, minmax(260px, 1fr))';
  const summaryGridTemplateColumns = compact ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))';
  const controlGridTemplateColumns = compact ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))';
  const nextControl = (() => {
    if (!opsSummary.provider.configured) {
      return {
        title: 'RunPod 제어 설정 확인 필요',
        description: 'RunPod 제어 설정이 필요합니다.',
        actionLabel: null as string | null,
      };
    }
    if (opsActionBusy) {
      return {
        title: '운영 제어 실행 중',
        description: 'Pod 또는 작업기 제어 요청을 처리 중입니다.',
        actionLabel: null as string | null,
      };
    }
    if (opsSummary.provider.checkpoint_pending_resume) {
      return {
        title: '체크포인트 재개 판단 필요',
        description: '저장된 체크포인트가 남아 있어 Pod를 다시 열면 직전 세션 흐름을 이어갈 수 있습니다.',
        actionLabel: 'Pod 열고 이어서 작업',
      };
    }
    if (opsSummary.active_queue_workers > 0) {
      return {
        title: '작업기가 연결된 상태',
        description: `${opsSummary.active_queue_workers}개 작업기가 대기열을 처리하고 있습니다.`,
        actionLabel: '작업기 중지',
      };
    }
    if (opsSummary.worker_stop_requested_at) {
      return {
        title: '처리 대기열 재개 가능',
        description: '중지 요청이 남아 있습니다. 필요하면 작업기를 다시 여세요.',
        actionLabel: '처리 대기열 재개',
      };
    }
    return {
      title: 'Pod 열고 이어서 작업 가능',
      description: 'Pod 재개와 작업기 시작 상태입니다.',
      actionLabel: 'Pod 열고 이어서 작업',
    };
  })();

  return (
    <section style={sectionCardStyle('warm')}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'grid', gap: 4 }}>
          <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>운영 제어</strong>
          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
            Pod 상태와 작업기 제어를 확인하세요.
          </span>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', width: compact ? '100%' : 'auto' }}>
          <span style={{ ...chipStyle('accent'), background: podStatus.tone, border: `1px solid ${podStatus.border}` }}>
            {podStatus.label}
          </span>
          {opsSummary.provider.allocation_state ? <span style={chipStyle('default')}>할당 {providerStateLabel(opsSummary.provider.allocation_state)}</span> : null}
          {opsSummary.provider.migration_state ? <span style={chipStyle('warning')}>이동 {providerStateLabel(opsSummary.provider.migration_state)}</span> : null}
        </div>
      </div>

      <article
        style={{
          ...tileStyle('accent'),
          gap: 10,
          padding: compact ? '14px 16px' : '16px 18px',
        }}
      >
        <div style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: studioTokens.color.muted }}>
            지금 확인할 운영 상태
          </span>
          <strong style={{ fontSize: 15, color: studioTokens.color.ink }}>{nextControl.title}</strong>
          <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>{nextControl.description}</span>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {nextControl.actionLabel === 'Pod 열고 이어서 작업' ? (
            <button type="button" style={buttonStyle(true, Boolean(opsActionBusy))} onClick={() => void onOpenPodAndContinue()} disabled={Boolean(opsActionBusy)}>
              Pod 열고 이어서 작업
            </button>
          ) : null}
          {nextControl.actionLabel === '작업기 중지' ? (
            <button
              type="button"
              style={buttonStyle(false, Boolean(opsActionBusy) || (Boolean(opsSummary.worker_stop_requested_at) && !opsSummary.active_queue_workers))}
              onClick={() => void onStopWorkerQueue()}
              disabled={Boolean(opsActionBusy) || (Boolean(opsSummary.worker_stop_requested_at) && !opsSummary.active_queue_workers)}
            >
              작업기 중지
            </button>
          ) : null}
          {nextControl.actionLabel === '처리 대기열 재개' ? (
            <button type="button" style={buttonStyle(false, Boolean(opsActionBusy))} onClick={() => void onStartExternalWorker()} disabled={Boolean(opsActionBusy)}>
              처리 대기열 재개
            </button>
          ) : null}
        </div>
      </article>

      <div style={{ display: 'grid', gridTemplateColumns: panelGridTemplateColumns, gap: 12 }}>
        <article style={{ ...tileStyle('accent'), gap: 10 }}>
          <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>운영 상태 요약</strong>
          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>{podStatus.reason}</span>
          <div style={{ display: 'grid', gridTemplateColumns: summaryGridTemplateColumns, gap: 10 }}>
            <div style={{ display: 'grid', gap: 4 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: studioTokens.color.muted }}>접속과 장비</span>
              <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{opsSummary.provider.public_ip ?? '정보 없음'}</strong>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                {opsSummary.provider.host_id ?? '호스트 미확인'} / {opsSummary.provider.machine_id ?? '머신 미확인'}
              </span>
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                {opsSummary.provider.pod_uptime_seconds ? `${Math.max(1, Math.round(opsSummary.provider.pod_uptime_seconds / 60))}분 가동` : '가동 시간 정보 없음'}
                {opsSummary.provider.gpu_count ? ` · GPU ${opsSummary.provider.gpu_count}` : ''}
              </span>
            </div>
            <div style={{ display: 'grid', gap: 4 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: studioTokens.color.muted }}>수명주기와 체크포인트</span>
              <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{lifecycleSummary}</strong>
              {opsSummary.provider.last_status_change ? (
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  마지막 상태 변경 {formatSessionTimestamp(opsSummary.provider.last_status_change)}
                </span>
              ) : null}
              {opsSummary.provider.checkpoint_id ? (
                <span style={{ fontSize: 12, color: opsSummary.provider.checkpoint_pending_resume ? studioTokens.color.warning : studioTokens.color.muted, lineHeight: 1.55 }}>
                  체크포인트 {opsSummary.provider.checkpoint_pending_resume ? '대기 중' : '준비됨'}
                  {opsSummary.provider.checkpoint_session_id ? ` · 세션 ${opsSummary.provider.checkpoint_session_id}` : ''}
                  {opsSummary.provider.checkpoint_reason ? ` · ${opsSummary.provider.checkpoint_reason}` : ''}
                </span>
              ) : (
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  저장된 체크포인트가 아직 없습니다.
                </span>
              )}
            </div>
          </div>
          {opsSummary.provider.backend_url || opsSummary.provider.frontend_url ? (
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
              {opsSummary.provider.backend_url ? `백엔드 ${opsSummary.provider.backend_url}` : ''}
              {opsSummary.provider.backend_url && opsSummary.provider.frontend_url ? ' · ' : ''}
              {opsSummary.provider.frontend_url ? `프런트엔드 ${opsSummary.provider.frontend_url}` : ''}
            </span>
          ) : null}
        </article>

        <article style={{ ...tileStyle(), gap: 10 }}>
          <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>즉시 제어</strong>
          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
            Pod 열기, 체크포인트 종료, 외부 작업기 제어를 실행합니다.
          </span>
          <div style={{ display: 'grid', gridTemplateColumns: controlGridTemplateColumns, gap: 8 }}>
            <button type="button" style={buttonStyle(false, Boolean(opsActionBusy))} onClick={() => void onOpenPodAndContinue()} disabled={Boolean(opsActionBusy)}>
              Pod 열고 이어서 작업
            </button>
            <button
              type="button"
              style={buttonStyle(false, Boolean(opsActionBusy) || !opsSummary.provider.configured)}
              onClick={() => void onCheckpointAndStopPod()}
              disabled={Boolean(opsActionBusy) || !opsSummary.provider.configured}
            >
              체크포인트 저장 후 Pod 종료
            </button>
            <button type="button" style={buttonStyle(false, Boolean(opsActionBusy))} onClick={() => void onStartExternalWorker()} disabled={Boolean(opsActionBusy)}>
              {opsSummary.worker_stop_requested_at ? '처리 대기열 재개' : '외부 작업기 시작'}
            </button>
            <button
              type="button"
              style={buttonStyle(false, Boolean(opsActionBusy) || (Boolean(opsSummary.worker_stop_requested_at) && !opsSummary.active_queue_workers))}
              onClick={() => void onStopWorkerQueue()}
              disabled={Boolean(opsActionBusy) || (Boolean(opsSummary.worker_stop_requested_at) && !opsSummary.active_queue_workers)}
            >
              작업기 중지
            </button>
          </div>
          <div style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
              작업기 상태: {opsSummary.worker_stop_requested_at ? '중지 요청이 남아 있습니다.' : `${opsSummary.active_queue_workers}개 작업기가 현재 연결되어 있습니다.`}
            </span>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
              Pod 제어: {opsSummary.provider.configured ? 'RunPod 제어가 설정되어 있습니다.' : 'RunPod 제어가 아직 설정되지 않았습니다.'}
            </span>
          </div>
        </article>
      </div>
    </section>
  );
}
