import React from 'react';
import { buttonStyle, chipStyle, controlStyle, sectionCardStyle, studioTokens, tileStyle } from '../designTokens';
import type { RecentStudioSessionSummary } from '../studioApi';

interface RecentSessionsBoardProps {
  recentSessions: RecentStudioSessionSummary[];
  recentSessionsLoading: boolean;
  currentSessionId: string | null;
  expandedRecentSessionIds: string[];
  selectedBatchSessionIds: string[];
  compareGridTemplateColumns: string;
  onSelectAllRecentSessionsForBatch: () => void;
  onClearBatchSessionSelection: () => void;
  onRefreshRecentSessions: () => Promise<void>;
  onToggleBatchSessionSelection: (sessionId: string) => void;
  onToggleRecentSessionExpanded: (sessionId: string) => void;
  onOpenRecentSession: (session: RecentStudioSessionSummary) => Promise<void>;
  onUpdateSessionCatalog: (
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
  ) => Promise<void>;
  onApplyBatchCatalogUpdate: () => Promise<void>;
  batchCatalogPickStatus: 'unreviewed' | 'selected' | 'rejected' | 'hold';
  batchCatalogReviewStatus: 'intake' | 'culling' | 'proofing' | 'client_review' | 'print_ready' | 'delivered' | 'archived';
  batchCatalogKeywords: string;
  batchProofingProfile: string;
  batchPrintProfile: string;
  batchClientCollection: string;
  setBatchCatalogPickStatus: (value: 'unreviewed' | 'selected' | 'rejected' | 'hold') => void;
  setBatchCatalogReviewStatus: (value: 'intake' | 'culling' | 'proofing' | 'client_review' | 'print_ready' | 'delivered' | 'archived') => void;
  setBatchCatalogKeywords: (value: string) => void;
  setBatchProofingProfile: (value: string) => void;
  setBatchPrintProfile: (value: string) => void;
  setBatchClientCollection: (value: string) => void;
  catalogBusyKey: string | null;
  previewUrl: (path: string | null, outputRoot: string, maxEdge: number) => string | null;
  recentPreviewMaxEdge: number;
  formatSessionTimestamp: (value: string) => string;
  formatSessionStep: (value: string | null | undefined) => string | null;
  sessionEntryLabel: (value: RecentStudioSessionSummary['entry_mode']) => string;
  sessionStatusTone: (value: string | null | undefined) => React.CSSProperties;
}

const reviewStatuses: Array<RecentSessionsBoardProps['batchCatalogReviewStatus']> = [
  'intake',
  'culling',
  'proofing',
  'client_review',
  'print_ready',
  'delivered',
  'archived',
];

function pickStatusLabel(value: RecentSessionsBoardProps['batchCatalogPickStatus']): string {
  switch (value) {
    case 'selected':
      return '선택';
    case 'rejected':
      return '제외';
    case 'hold':
      return '보류';
    default:
      return '미검토';
  }
}

function reviewStatusLabel(value: RecentSessionsBoardProps['batchCatalogReviewStatus']): string {
  switch (value) {
    case 'intake':
      return '가져오기';
    case 'culling':
      return '선별';
    case 'proofing':
      return '교정';
    case 'client_review':
      return '고객 검토';
    case 'print_ready':
      return '출력 준비';
    case 'delivered':
      return '전달 완료';
    case 'archived':
      return '보관 완료';
    default:
      return value;
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
    case 'queued':
      return '대기';
    case 'submitted':
      return '제출됨';
    case 'running':
      return '실행 중';
    case 'done':
      return '완료';
    case 'cancelling':
      return '중지 요청';
    case 'cancelled':
      return '중지됨';
    case 'failed':
    case 'error':
      return '실패';
    case 'blocked':
      return '보류';
    default:
      return value ?? '알 수 없음';
  }
}

function hasInFlightStatus(value: string | null | undefined): boolean {
  return ['queued', 'submitted', 'running', 'cancelling', 'starting', 'stopping'].includes(value ?? '');
}

export function RecentSessionsBoard({
  recentSessions,
  recentSessionsLoading,
  currentSessionId,
  expandedRecentSessionIds,
  selectedBatchSessionIds,
  compareGridTemplateColumns,
  onSelectAllRecentSessionsForBatch,
  onClearBatchSessionSelection,
  onRefreshRecentSessions,
  onToggleBatchSessionSelection,
  onToggleRecentSessionExpanded,
  onOpenRecentSession,
  onUpdateSessionCatalog,
  onApplyBatchCatalogUpdate,
  batchCatalogPickStatus,
  batchCatalogReviewStatus,
  batchCatalogKeywords,
  batchProofingProfile,
  batchPrintProfile,
  batchClientCollection,
  setBatchCatalogPickStatus,
  setBatchCatalogReviewStatus,
  setBatchCatalogKeywords,
  setBatchProofingProfile,
  setBatchPrintProfile,
  setBatchClientCollection,
  catalogBusyKey,
  previewUrl,
  recentPreviewMaxEdge,
  formatSessionTimestamp,
  formatSessionStep,
  sessionEntryLabel,
  sessionStatusTone,
}: RecentSessionsBoardProps) {
  const compact = typeof window !== 'undefined' && window.innerWidth < studioTokens.breakpoint.laptop;
  const summaryGridTemplateColumns = compact ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))';
  const sessionOverviewGridTemplateColumns = compact ? '1fr' : 'repeat(auto-fit, minmax(240px, 1fr))';
  const expandedPreviewGridTemplateColumns = compact ? '1fr' : compareGridTemplateColumns;
  const expandedFieldGridTemplateColumns = compact ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))';
  const activeRecentSessions = recentSessions.filter((session) => (
    hasInFlightStatus(session.rawprep_status) || hasInFlightStatus(session.studio_status)
  )).length;
  const reviewedRecentSessions = recentSessions.filter((session) => (
    session.catalog.pick_status !== 'unreviewed'
    || session.catalog.review_status !== 'intake'
    || session.catalog.rating > 0
  )).length;
  const currentSessionSummary = currentSessionId
    ? recentSessions.find((session) => session.session_id === currentSessionId) ?? null
    : null;
  const featuredSession = currentSessionSummary ?? recentSessions[0] ?? null;

  return (
    <section style={sectionCardStyle('default')}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ display: 'grid', gap: 4 }}>
          <strong style={{ fontSize: 15, color: studioTokens.color.ink }}>최근 세션</strong>
          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
            최근 작업을 다시 열고 여러 세션을 선별/분류하세요.
          </span>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', width: compact ? '100%' : 'auto' }}>
          <button type="button" style={buttonStyle(false, !recentSessions.length)} onClick={onSelectAllRecentSessionsForBatch} disabled={!recentSessions.length}>
            모두 선택
          </button>
          <button type="button" style={buttonStyle(false, !selectedBatchSessionIds.length)} onClick={onClearBatchSessionSelection} disabled={!selectedBatchSessionIds.length}>
            선택 해제
          </button>
          <button type="button" style={buttonStyle(false, recentSessionsLoading)} onClick={() => void onRefreshRecentSessions()} disabled={recentSessionsLoading}>
            새로고침
          </button>
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
            지금 이어갈 세션
          </span>
          <strong style={{ fontSize: 15, color: studioTokens.color.ink }}>
            {featuredSession?.primary_file_name ?? '아직 이어갈 세션이 없습니다.'}
          </strong>
          <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>
            {featuredSession
              ? `${sessionEntryLabel(featuredSession.entry_mode)} · 갱신 ${formatSessionTimestamp(featuredSession.last_updated_at)}`
              : '이어갈 세션이 아직 없습니다.'}
          </span>
        </div>
        {featuredSession ? (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <span style={chipStyle('default')}>
              원본함 {featuredSession.staged_asset_count}건
            </span>
            {featuredSession.rawprep_status ? (
              <span style={{ ...chipStyle('default'), ...sessionStatusTone(featuredSession.rawprep_status) }}>
                TriRaw {jobStatusLabel(featuredSession.rawprep_status)}
              </span>
            ) : null}
            {featuredSession.studio_status ? (
              <span style={{ ...chipStyle('default'), ...sessionStatusTone(featuredSession.studio_status) }}>
                {studioToolLabel(featuredSession.studio_tool)} {jobStatusLabel(featuredSession.studio_status)}
              </span>
            ) : null}
          </div>
        ) : null}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {featuredSession ? (
            <button
              type="button"
              style={buttonStyle(currentSessionId === featuredSession.session_id, currentSessionId === featuredSession.session_id)}
              onClick={() => void onOpenRecentSession(featuredSession)}
              disabled={currentSessionId === featuredSession.session_id}
            >
              {currentSessionId === featuredSession.session_id ? '현재 세션 사용 중' : '이 세션 이어서 열기'}
            </button>
          ) : null}
          <button type="button" style={buttonStyle(false, recentSessionsLoading)} onClick={() => void onRefreshRecentSessions()} disabled={recentSessionsLoading}>
            목록 새로고침
          </button>
        </div>
      </article>

      <div style={{ display: 'grid', gridTemplateColumns: summaryGridTemplateColumns, gap: 10 }}>
        <article style={tileStyle('accent')}>
          <span style={{ fontSize: 11, fontWeight: 700, color: studioTokens.color.muted }}>이어 작업 가능한 세션</span>
          <strong style={{ fontSize: 16, color: studioTokens.color.accent }}>{recentSessions.length}개</strong>
          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
            최근 세션을 다시 열어 이어갑니다.
          </span>
        </article>
        <article style={tileStyle()}>
          <span style={{ fontSize: 11, fontWeight: 700, color: studioTokens.color.muted }}>현재 움직이는 세션</span>
          <strong style={{ fontSize: 16, color: studioTokens.color.accent }}>{activeRecentSessions}개</strong>
          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
            TriRaw 또는 편집 작업이 아직 진행 중인 세션 수입니다.
          </span>
        </article>
        <article style={tileStyle()}>
          <span style={{ fontSize: 11, fontWeight: 700, color: studioTokens.color.muted }}>일괄 분류 선택</span>
          <strong style={{ fontSize: 16, color: studioTokens.color.accent }}>{selectedBatchSessionIds.length}개</strong>
          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
            검토 흐름에 올린 세션 {reviewedRecentSessions}개 · 현재 세션 {currentSessionSummary?.primary_file_name ?? '없음'}
          </span>
        </article>
      </div>

      {selectedBatchSessionIds.length ? (
        <section style={sectionCardStyle('accent')}>
          <div style={{ display: 'grid', gap: 4 }}>
            <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>일괄 선별 및 분류 보드</strong>
            <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
              선택된 {selectedBatchSessionIds.length}개 세션에 선별 상태, 검토 단계, 납품 메타데이터를 한 번에 적용합니다.
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
            <label style={{ display: 'grid', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700 }}>선별 상태</span>
              <select style={controlStyle} value={batchCatalogPickStatus} onChange={(event) => setBatchCatalogPickStatus(event.target.value as RecentSessionsBoardProps['batchCatalogPickStatus'])}>
                <option value="unreviewed">미검토</option>
                <option value="selected">선택</option>
                <option value="rejected">제외</option>
                <option value="hold">보류</option>
              </select>
            </label>
            <label style={{ display: 'grid', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700 }}>검토 단계</span>
              <select style={controlStyle} value={batchCatalogReviewStatus} onChange={(event) => setBatchCatalogReviewStatus(event.target.value as RecentSessionsBoardProps['batchCatalogReviewStatus'])}>
                {reviewStatuses.map((value) => (
                  <option key={value} value={value}>{reviewStatusLabel(value)}</option>
                ))}
              </select>
            </label>
            <label style={{ display: 'grid', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700 }}>키워드</span>
              <input style={controlStyle} value={batchCatalogKeywords} onChange={(event) => setBatchCatalogKeywords(event.target.value)} placeholder="대표컷, 출력, 1차" />
            </label>
            <label style={{ display: 'grid', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700 }}>교정 프로필</span>
              <input style={controlStyle} value={batchProofingProfile} onChange={(event) => setBatchProofingProfile(event.target.value)} placeholder="기본 교정 프로필" />
            </label>
            <label style={{ display: 'grid', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700 }}>출력 프로필</span>
              <input style={controlStyle} value={batchPrintProfile} onChange={(event) => setBatchPrintProfile(event.target.value)} placeholder="A3 파인아트 출력" />
            </label>
            <label style={{ display: 'grid', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700 }}>클라이언트 묶음</span>
              <input style={controlStyle} value={batchClientCollection} onChange={(event) => setBatchClientCollection(event.target.value)} placeholder="봄 출시 1차" />
            </label>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" style={buttonStyle(true, Boolean(catalogBusyKey))} onClick={() => void onApplyBatchCatalogUpdate()} disabled={Boolean(catalogBusyKey)}>
              일괄 메타데이터 적용
            </button>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
              선별, 검토, 프로필, 키워드를 한 번에 적용합니다.
            </span>
          </div>
        </section>
      ) : null}

      {recentSessionsLoading ? (
        <span style={{ fontSize: 12, color: studioTokens.color.muted }}>최근 세션을 불러오는 중입니다.</span>
      ) : null}
      {!recentSessionsLoading && !recentSessions.length ? (
        <span style={{ fontSize: 12, color: studioTokens.color.muted }}>저장된 세션이 아직 없습니다.</span>
      ) : null}
      {recentSessions.map((session) => {
        const rawprepTone = sessionStatusTone(session.rawprep_status);
        const studioTone = sessionStatusTone(session.studio_status);
        const isCurrentSession = currentSessionId === session.session_id;
        const isExpanded = expandedRecentSessionIds.includes(session.session_id);
        const isBatchSelected = selectedBatchSessionIds.includes(session.session_id);
        const sourceThumbUrl = isExpanded ? previewUrl(session.source_preview_path ?? session.editable_asset_path ?? null, session.output_root, recentPreviewMaxEdge) : null;
        const resultThumbUrl = isExpanded ? previewUrl(session.result_preview_path ?? null, session.output_root, recentPreviewMaxEdge) : null;
        const studioStepLabel = formatSessionStep(session.studio_current_step);
        return (
          <article
            key={session.session_id}
            style={{
              ...tileStyle(isCurrentSession ? 'accent' : 'default'),
              gap: 10,
              padding: '16px 18px',
              background: isCurrentSession ? studioTokens.color.accentSoft : studioTokens.color.surfaceSoft,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div style={{ display: 'grid', gap: 3 }}>
                <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{session.primary_file_name ?? session.session_id}</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.muted }}>{session.session_id}</span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end', width: compact ? '100%' : 'auto' }}>
                <button type="button" style={buttonStyle(isBatchSelected)} onClick={() => onToggleBatchSessionSelection(session.session_id)}>
                  {isBatchSelected ? '일괄 처리에 포함됨' : '일괄 처리 선택'}
                </button>
                <button type="button" style={buttonStyle(false)} onClick={() => onToggleRecentSessionExpanded(session.session_id)}>
                  {isExpanded ? '접기' : '상세'}
                </button>
                <button
                  type="button"
                  style={buttonStyle(isCurrentSession, isCurrentSession)}
                  onClick={() => void onOpenRecentSession(session)}
                  disabled={isCurrentSession}
                >
                  {isCurrentSession ? '현재 세션' : '열기'}
                </button>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: sessionOverviewGridTemplateColumns, gap: 10 }}>
              <div style={{ display: 'grid', gap: 8 }}>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span style={chipStyle('default')}>{sessionEntryLabel(session.entry_mode)}</span>
                  {session.rawprep_status ? (
                    <span style={{ ...chipStyle('default'), ...rawprepTone }}>TriRaw {jobStatusLabel(session.rawprep_status)}</span>
                  ) : null}
                  {session.studio_status ? (
                    <span style={{ ...chipStyle('default'), ...studioTone }}>
                      {`${studioToolLabel(session.studio_tool)} ${jobStatusLabel(session.studio_status)}`}
                    </span>
                  ) : null}
                </div>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                  원본함 {session.staged_asset_count}건 · 갱신 {formatSessionTimestamp(session.last_updated_at)}
                </span>
                {session.catalog.keywords.length ? (
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {session.catalog.keywords.map((keyword) => (
                      <span key={`${session.session_id}_${keyword}`} style={chipStyle('default')}>{keyword}</span>
                    ))}
                  </div>
                ) : null}
              </div>
              <div style={{ ...tileStyle(isCurrentSession ? 'accent' : 'default'), gap: 8 }}>
                <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>이어 작업 요약</strong>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span style={chipStyle(session.catalog.pick_status === 'selected' ? 'success' : session.catalog.pick_status === 'rejected' ? 'warning' : 'default')}>
                    {pickStatusLabel(session.catalog.pick_status)}
                  </span>
                  <span style={chipStyle('accent')}>{reviewStatusLabel(session.catalog.review_status)}</span>
                  <span style={chipStyle('default')}>평점 {session.catalog.rating}/5</span>
                </div>
                {studioStepLabel ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.55 }}>
                    마지막 AI 단계: {studioStepLabel}
                  </span>
                ) : (
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                    최근 AI 단계 기록이 아직 없습니다.
                  </span>
                )}
                {session.editable_asset_path ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                    현재 작업 소스: {session.editable_asset_path.split(/[\\/]/).pop() ?? session.editable_asset_path}
                  </span>
                ) : null}
              </div>
            </div>
            {isExpanded ? (
              <>
                <section style={{ ...tileStyle(), gap: 10 }}>
                  <div style={{ display: 'grid', gap: 4 }}>
                    <strong style={{ fontSize: 12, color: studioTokens.color.ink }}>세션 미리보기</strong>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                      원본함과 최신 결과를 확인하세요.
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: expandedPreviewGridTemplateColumns, gap: 10 }}>
                    <div style={{ display: 'grid', gap: 6 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: studioTokens.color.muted }}>소스</span>
                    {sourceThumbUrl ? (
                      <img
                        src={sourceThumbUrl}
                        alt={`${session.session_id} 원본함 미리보기`}
                        loading="lazy"
                        decoding="async"
                        style={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', borderRadius: 10, background: studioTokens.color.surface, border: `1px solid ${studioTokens.color.line}` }}
                      />
                    ) : (
                      <div style={{ width: '100%', aspectRatio: '4 / 3', display: 'grid', placeItems: 'center', borderRadius: 10, background: studioTokens.color.surface, border: `1px dashed ${studioTokens.color.line}`, fontSize: 11, color: '#7a8798', textAlign: 'center', padding: 8 }}>
                        소스 미리보기를 만들 수 없습니다.
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'grid', gap: 6 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: studioTokens.color.muted }}>최신 결과</span>
                    {resultThumbUrl ? (
                      <img
                        src={resultThumbUrl}
                        alt={`${session.session_id} 최신 결과 미리보기`}
                        loading="lazy"
                        decoding="async"
                        style={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', borderRadius: 10, background: studioTokens.color.surface, border: `1px solid ${studioTokens.color.line}` }}
                      />
                    ) : (
                      <div style={{ width: '100%', aspectRatio: '4 / 3', display: 'grid', placeItems: 'center', borderRadius: 10, background: studioTokens.color.surface, border: `1px dashed ${studioTokens.color.line}`, fontSize: 11, color: '#7a8798', textAlign: 'center', padding: 8 }}>
                        아직 결과 미리보기가 없습니다.
                      </div>
                    )}
                  </div>
                  </div>
                </section>
                <section style={{ ...tileStyle('accent'), gap: 10 }}>
                  <div style={{ display: 'grid', gap: 4 }}>
                    <strong style={{ fontSize: 12, color: studioTokens.color.accent }}>선별 및 분류 작업</strong>
                    <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                      대표컷, 검토 단계, 납품 프로필을 정리하세요.
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {[1, 2, 3, 4, 5].map((rating) => (
                      <button
                        key={`${session.session_id}_rating_${rating}`}
                        type="button"
                        style={buttonStyle(session.catalog.rating === rating, Boolean(catalogBusyKey))}
                        onClick={() => void onUpdateSessionCatalog(session.session_id, { rating })}
                        disabled={Boolean(catalogBusyKey)}
                      >
                        {rating}점
                      </button>
                    ))}
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button type="button" style={buttonStyle(session.catalog.pick_status === 'selected', Boolean(catalogBusyKey))} onClick={() => void onUpdateSessionCatalog(session.session_id, { pick_status: 'selected' })} disabled={Boolean(catalogBusyKey)}>선택</button>
                    <button type="button" style={buttonStyle(session.catalog.pick_status === 'rejected', Boolean(catalogBusyKey))} onClick={() => void onUpdateSessionCatalog(session.session_id, { pick_status: 'rejected' })} disabled={Boolean(catalogBusyKey)}>제외</button>
                    <button type="button" style={buttonStyle(session.catalog.pick_status === 'hold', Boolean(catalogBusyKey))} onClick={() => void onUpdateSessionCatalog(session.session_id, { pick_status: 'hold' })} disabled={Boolean(catalogBusyKey)}>보류</button>
                    <button type="button" style={buttonStyle(session.catalog.pick_status === 'unreviewed', Boolean(catalogBusyKey))} onClick={() => void onUpdateSessionCatalog(session.session_id, { pick_status: 'unreviewed' })} disabled={Boolean(catalogBusyKey)}>초기화</button>
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {['proofing', 'client_review', 'print_ready', 'delivered'].map((status) => (
                      <button
                        key={`${session.session_id}_${status}`}
                        type="button"
                        style={buttonStyle(session.catalog.review_status === status, Boolean(catalogBusyKey))}
                        onClick={() => void onUpdateSessionCatalog(session.session_id, { review_status: status as RecentSessionsBoardProps['batchCatalogReviewStatus'] })}
                        disabled={Boolean(catalogBusyKey)}
                      >
                        {reviewStatusLabel(status as RecentSessionsBoardProps['batchCatalogReviewStatus'])}
                      </button>
                    ))}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: expandedFieldGridTemplateColumns, gap: 10 }}>
                    <label style={{ display: 'grid', gap: 6 }}>
                      <span style={{ fontSize: 12, fontWeight: 700 }}>교정 프로필</span>
                      <input
                        style={controlStyle}
                        defaultValue={session.catalog.proofing_profile ?? ''}
                        placeholder="기본 교정 프로필"
                        onBlur={(event) => {
                          const value = event.target.value.trim();
                          if (value !== (session.catalog.proofing_profile ?? '')) {
                            void onUpdateSessionCatalog(session.session_id, { proofing_profile: value });
                          }
                        }}
                      />
                    </label>
                    <label style={{ display: 'grid', gap: 6 }}>
                      <span style={{ fontSize: 12, fontWeight: 700 }}>출력 프로필</span>
                      <input
                        style={controlStyle}
                        defaultValue={session.catalog.print_profile ?? ''}
                        placeholder="A3 파인아트 출력"
                        onBlur={(event) => {
                          const value = event.target.value.trim();
                          if (value !== (session.catalog.print_profile ?? '')) {
                            void onUpdateSessionCatalog(session.session_id, { print_profile: value });
                          }
                        }}
                      />
                    </label>
                    <label style={{ display: 'grid', gap: 6 }}>
                      <span style={{ fontSize: 12, fontWeight: 700 }}>클라이언트 묶음</span>
                      <input
                        style={controlStyle}
                        defaultValue={session.catalog.client_collection ?? ''}
                        placeholder="봄 출시 1차"
                        onBlur={(event) => {
                          const value = event.target.value.trim();
                          if (value !== (session.catalog.client_collection ?? '')) {
                            void onUpdateSessionCatalog(session.session_id, { client_collection: value });
                          }
                        }}
                      />
                    </label>
                    <label style={{ display: 'grid', gap: 6 }}>
                      <span style={{ fontSize: 12, fontWeight: 700 }}>키워드</span>
                      <input
                        style={controlStyle}
                        defaultValue={session.catalog.keywords.join(', ')}
                        placeholder="대표컷, 출력, 1차"
                        onBlur={(event) => {
                          const values = event.target.value.split(',').map((item) => item.trim()).filter(Boolean);
                          if (values.join('|') !== session.catalog.keywords.join('|')) {
                            void onUpdateSessionCatalog(session.session_id, { keywords: values });
                          }
                        }}
                      />
                    </label>
                  </div>
                </section>
                {session.prompt_preview ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
                    프롬프트: {session.prompt_preview}
                  </span>
                ) : null}
                {studioStepLabel ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.5 }}>
                    마지막 AI 단계: {studioStepLabel}
                  </span>
                ) : null}
                {session.editable_asset_path ? (
                  <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.5 }}>
                    작업 소스 경로: {session.editable_asset_path.split(/[\\/]/).pop() ?? session.editable_asset_path}
                  </span>
                ) : null}
              </>
            ) : null}
          </article>
        );
      })}
    </section>
  );
}
