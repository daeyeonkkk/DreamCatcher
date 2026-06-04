import React, { useEffect, useMemo, useState } from 'react';
import { buttonStyle, chipStyle, sectionCardStyle, studioTokens, tileStyle } from '../designTokens';
import {
  fetchStudioCompareAdvice,
  type StudioCompareAdviceResponse,
  type ToolKey,
} from '../studioApi';
import {
  localizeCommunityTakeaway,
  localizeDatasetLabel,
  localizePriorFreeformText,
  localizePriorityDimension,
} from '../studioPriorLabels';

interface CompareGuidanceDrawerProps {
  outputRoot: string;
  comparePrimary: string | null;
  compareCandidate: string | null;
  comparePrimaryUrl: string | null;
  compareCandidateUrl: string | null;
  motionOverlayPath: string | null;
  motionOverlayUrl: string | null;
  motionOverlaySummary: string | null;
  motionOverlayCoverage: number | null;
  tool: ToolKey;
  onKeepSelect?: () => Promise<void> | void;
  onAcceptCandidate?: () => Promise<void> | void;
}

function basenameFromPath(path: string | null): string {
  if (!path) {
    return '선택 안 됨';
  }
  const segments = path.split(/[\\/]/).filter(Boolean);
  return segments[segments.length - 1] ?? path;
}

function riskChipTone(riskLevel: 'low' | 'medium' | 'high'): 'success' | 'warning' | 'accent' {
  if (riskLevel === 'high') {
    return 'warning';
  }
  if (riskLevel === 'medium') {
    return 'accent';
  }
  return 'success';
}

function signalTone(severity: 'info' | 'warning' | 'risk'): 'default' | 'accent' | 'warm' {
  if (severity === 'risk') {
    return 'warm';
  }
  if (severity === 'warning') {
    return 'accent';
  }
  return 'default';
}

function metricDeltaLabel(value: number, unit: '%' | 'pts' = 'pts'): string {
  const scaled = unit === '%' ? value * 100 : value;
  const prefix = scaled > 0 ? '+' : '';
  return `${prefix}${scaled.toFixed(1)}${unit}`;
}

function previewStyle(): React.CSSProperties {
  return {
    width: '100%',
    aspectRatio: '4 / 3',
    objectFit: 'cover',
    borderRadius: studioTokens.radius.m,
    border: `1px solid ${studioTokens.color.line}`,
    background: studioTokens.color.surfaceSoft,
  };
}

export function CompareGuidanceDrawer({
  outputRoot,
  comparePrimary,
  compareCandidate,
  comparePrimaryUrl,
  compareCandidateUrl,
  motionOverlayPath,
  motionOverlayUrl,
  motionOverlaySummary,
  motionOverlayCoverage,
  tool,
  onKeepSelect,
  onAcceptCandidate,
}: CompareGuidanceDrawerProps) {
  const compact = typeof window !== 'undefined' && window.innerWidth < studioTokens.breakpoint.tablet;
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [advice, setAdvice] = useState<StudioCompareAdviceResponse | null>(null);
  const [decisionBusy, setDecisionBusy] = useState<'select' | 'candidate' | null>(null);

  const ready = Boolean(comparePrimary && compareCandidate);
  const pairGridTemplateColumns = compact ? '1fr' : 'repeat(2, minmax(0, 1fr))';
  const metricGridTemplateColumns = compact ? '1fr' : 'repeat(2, minmax(0, 1fr))';

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [open]);

  useEffect(() => {
    if (!open || !comparePrimary || !compareCandidate) {
      return;
    }
    let cancelled = false;
    setBusy(true);
    setError(null);
    fetchStudioCompareAdvice({
      outputRoot,
      primaryPath: comparePrimary,
      candidatePath: compareCandidate,
      tool,
      motionOverlayPath,
      motionOverlaySummary,
      motionOverlayCoverage,
    })
      .then((payload) => {
        if (!cancelled) {
          setAdvice(payload);
        }
      })
      .catch((fetchError) => {
        if (!cancelled) {
          setAdvice(null);
          setError(fetchError instanceof Error ? fetchError.message : '비교 안내를 준비하지 못했습니다.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setBusy(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, compareCandidate, comparePrimary, motionOverlayCoverage, motionOverlayPath, motionOverlaySummary, outputRoot, tool]);

  const quickRead = useMemo(() => {
    if (!advice) {
      return [];
    }
    return [
      {
        label: '밝기 변화',
        value: metricDeltaLabel(advice.candidate_metrics.mean_luma - advice.select_metrics.mean_luma, '%'),
      },
      {
        label: '하이라이트 클립',
        value: `${(advice.candidate_metrics.highlight_clip_ratio * 100).toFixed(1)}%`,
      },
      {
        label: '색온도 변화',
        value: metricDeltaLabel(advice.candidate_metrics.warmth - advice.select_metrics.warmth, '%'),
      },
      {
        label: '디테일 변화',
        value: metricDeltaLabel(advice.candidate_metrics.detail_energy - advice.select_metrics.detail_energy),
      },
    ];
  }, [advice]);

  async function handleDecision(kind: 'select' | 'candidate') {
    const runner = kind === 'candidate' ? onAcceptCandidate : onKeepSelect;
    if (!runner) {
      return;
    }
    setDecisionBusy(kind);
    try {
      await runner();
      setOpen(false);
    } finally {
      setDecisionBusy(null);
    }
  }

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <button
          type="button"
          style={buttonStyle(false, !ready)}
          onClick={() => setOpen(true)}
          disabled={!ready}
        >
          비교 안내
        </button>
        {advice ? (
          <span style={chipStyle(riskChipTone(advice.risk_level))}>
            {advice.risk_level === 'high' ? '세밀한 검토 필요' : advice.risk_level === 'medium' ? '몇 가지 확인 필요' : '안정적'}
          </span>
        ) : null}
      </div>

      {open ? (
        <div
          role="presentation"
          onClick={() => setOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.26)',
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: compact ? 'flex-end' : 'stretch',
            zIndex: 40,
          }}
        >
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="비교 안내"
            onClick={(event) => event.stopPropagation()}
            style={{
              width: compact ? '100%' : 'min(520px, 100vw)',
              maxHeight: compact ? '92vh' : '100%',
              height: compact ? 'auto' : '100%',
              overflowY: 'auto',
              background: studioTokens.color.surface,
              borderLeft: compact ? 'none' : `1px solid ${studioTokens.color.line}`,
              borderTop: compact ? `1px solid ${studioTokens.color.line}` : 'none',
              borderTopLeftRadius: compact ? studioTokens.radius.xl : 0,
              borderTopRightRadius: compact ? studioTokens.radius.xl : 0,
              boxShadow: studioTokens.shadow.card,
              padding: compact ? 18 : 24,
              display: 'grid',
              alignContent: 'start',
              gap: 16,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'start' }}>
              <div style={{ display: 'grid', gap: 4 }}>
                <strong style={{ fontSize: 16, color: studioTokens.color.ink }}>비교 안내</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  판정 메모와 채택 버튼을 확인하세요.
                </span>
              </div>
              <button type="button" style={buttonStyle(false)} onClick={() => setOpen(false)}>
                닫기
              </button>
            </div>

            <section style={sectionCardStyle('soft')}>
              <div style={{ display: 'grid', gap: 4 }}>
                <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>현재 비교 쌍</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  두 후보와 판정 신호를 확인하세요.
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: pairGridTemplateColumns, gap: 10 }}>
                <div style={tileStyle()}>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>유지 후보</strong>
                  {comparePrimaryUrl ? (
                    <img src={comparePrimaryUrl} alt="유지 후보 미리보기" decoding="async" style={previewStyle()} />
                  ) : (
                    <div style={{ ...previewStyle(), display: 'grid', placeItems: 'center', fontSize: 12, color: studioTokens.color.muted }}>
                      미리보기를 아직 만들지 못했습니다.
                    </div>
                  )}
                  <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.5 }}>{basenameFromPath(comparePrimary)}</span>
                </div>
                <div style={tileStyle()}>
                  <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>대안 후보</strong>
                  {compareCandidateUrl ? (
                    <img src={compareCandidateUrl} alt="대안 후보 미리보기" decoding="async" style={previewStyle()} />
                  ) : (
                    <div style={{ ...previewStyle(), display: 'grid', placeItems: 'center', fontSize: 12, color: studioTokens.color.muted }}>
                      미리보기를 아직 만들지 못했습니다.
                    </div>
                  )}
                  <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.5 }}>{basenameFromPath(compareCandidate)}</span>
                </div>
              </div>
            </section>

            {busy ? (
              <section style={sectionCardStyle('soft')}>
                <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>비교 안내를 준비하는 중입니다</strong>
                <span style={{ fontSize: 13, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  현재 비교 쌍의 판정 메모를 준비하고 있습니다.
                </span>
              </section>
            ) : null}

            {!busy && error ? (
              <section style={sectionCardStyle('warm')}>
                <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>비교 안내를 준비하지 못했습니다</strong>
                <span style={{ fontSize: 13, color: studioTokens.color.warning, lineHeight: 1.55 }}>{error}</span>
              </section>
            ) : null}

            {!busy && advice ? (
              <>
                <section style={sectionCardStyle('accent')}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                    <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>판단 요약</strong>
                    <span style={chipStyle(riskChipTone(advice.risk_level))}>
                      {advice.risk_level === 'high' ? '위험 높음' : advice.risk_level === 'medium' ? '위험 보통' : '위험 낮음'}
                    </span>
                  </div>
                  <span style={{ fontSize: 13, color: studioTokens.color.inkSoft, lineHeight: 1.6 }}>{advice.summary}</span>
                  <div style={{ display: 'grid', gridTemplateColumns: metricGridTemplateColumns, gap: 8 }}>
                    {quickRead.map((item) => (
                      <div key={item.label} style={tileStyle()}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: studioTokens.color.muted }}>{item.label}</span>
                        <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>{item.value}</strong>
                      </div>
                    ))}
                  </div>
                </section>

                {advice.motion_watch ? (
                  <section style={sectionCardStyle('soft')}>
                    <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>움직임 감시</strong>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                      {advice.motion_watch.summary}
                    </span>
                    {motionOverlayUrl ? (
                      <img src={motionOverlayUrl} alt="움직임 감시 오버레이" decoding="async" style={previewStyle()} />
                    ) : null}
                    <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                      감지 범위: {(advice.motion_watch.coverage * 100).toFixed(1)}%
                    </span>
                    <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>
                      {advice.motion_watch.recommendation}
                    </span>
                    {motionOverlayPath ? (
                      <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                        오버레이 파일: {basenameFromPath(motionOverlayPath)}
                      </span>
                    ) : null}
                  </section>
                ) : null}

                <section style={sectionCardStyle()}>
                  <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>지금 확인할 점</strong>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {advice.signals.map((signal) => (
                      <div key={`${signal.severity}_${signal.title}`} style={tileStyle(signalTone(signal.severity))}>
                        <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>{signal.title}</strong>
                        <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>{signal.detail}</span>
                      </div>
                    ))}
                  </div>
                </section>

                <section style={sectionCardStyle()}>
                  <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>최종 채택 점검표</strong>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {advice.checklist.map((item) => (
                      <div key={item} style={tileStyle()}>
                        <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>{item}</span>
                      </div>
                    ))}
                  </div>
                </section>

                <section style={sectionCardStyle('soft')}>
                  <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>공개 기준과 로컬 가드레일</strong>
                  {advice.priority_dimensions.length ? (
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {advice.priority_dimensions.map((item) => (
                        <span key={item} style={chipStyle('accent')}>
                          {localizePriorityDimension(item)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {advice.prior_guardrails.length ? (
                    <div style={{ display: 'grid', gap: 8 }}>
                      {advice.prior_guardrails.map((item) => (
                        <div key={item} style={tileStyle()}>
                          <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>
                            {localizePriorFreeformText(item)}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {advice.public_prior_labels.length ? (
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                      적용 중인 기준: {advice.public_prior_labels.map(localizeDatasetLabel).join(', ')}
                    </span>
                  ) : null}
                  {advice.community_takeaways.length ? (
                    <div style={{ display: 'grid', gap: 6 }}>
                      {advice.community_takeaways.map((item) => (
                        <span key={item} style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                          {localizeCommunityTakeaway(item)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </section>

                <div
                  style={{
                    position: 'sticky',
                    bottom: compact ? -18 : -24,
                    marginTop: 4,
                    marginLeft: compact ? -18 : -24,
                    marginRight: compact ? -18 : -24,
                    padding: compact ? '14px 18px' : '16px 24px',
                    borderTop: `1px solid ${studioTokens.color.line}`,
                    background: 'rgba(255, 255, 255, 0.96)',
                    display: 'grid',
                    gap: 8,
                  }}
                >
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
                    현재 비교 쌍을 기록하거나 채택하세요.
                  </span>
                  <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
                    <button
                      type="button"
                      style={buttonStyle(false, !comparePrimary || !compareCandidate || decisionBusy !== null)}
                      disabled={!comparePrimary || !compareCandidate || decisionBusy !== null}
                      onClick={() => void handleDecision('select')}
                    >
                      {decisionBusy === 'select' ? '유지 후보 기록 중...' : '유지 후보 선택'}
                    </button>
                    <button
                      type="button"
                      style={buttonStyle(true, !comparePrimary || !compareCandidate || decisionBusy !== null)}
                      disabled={!comparePrimary || !compareCandidate || decisionBusy !== null}
                      onClick={() => void handleDecision('candidate')}
                    >
                      {decisionBusy === 'candidate' ? '대안 후보 기록 중...' : '대안 후보 채택'}
                    </button>
                  </div>
                </div>
              </>
            ) : null}
          </aside>
        </div>
      ) : null}
    </>
  );
}
