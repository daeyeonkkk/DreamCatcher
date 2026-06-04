import React from 'react';
import { buttonStyle, chipStyle, sectionCardStyle, tileStyle, studioTokens } from '../designTokens';
import type { RecentStudioSessionSummary } from '../studioApi';
import { describeDeliveryPreset, type DeliveryPresetKey, type DeliveryPresetProfile } from '../deliveryPresetLibrary';

interface ExportPackageItem {
  path: string;
  label: string;
}

interface FinishExportPresetView {
  key: DeliveryPresetKey;
  label: string;
  description: string;
  items: ExportPackageItem[];
}

interface FinishTelemetryItem {
  label: string;
  value: string;
}

interface FinishDeliveryDeskProps {
  intakeReady: boolean;
  packageBusy: boolean;
  batchPackageBusy: boolean;
  optionGridTemplateColumns: string;
  deliveryPresetProfiles: DeliveryPresetProfile[];
  finishExportPresets: FinishExportPresetView[];
  finishTelemetry: FinishTelemetryItem[];
  selectedBatchSessions: RecentStudioSessionSummary[];
  selectedBatchSessionIds: string[];
  recentSessionsCount: number;
  lastBatchReportPath: string | null;
  onImportProfiles: (event: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  onExportLibrary: () => void;
  onDownloadSessionReport: () => void;
  onApplyDeliveryPresetProfile: (profile: DeliveryPresetProfile) => Promise<void>;
  onExportBatchDelivery: (preset: DeliveryPresetKey) => Promise<void>;
  onExportDeliveryPresetPackage: (
    preset: DeliveryPresetKey,
    options?: { label?: string; metadata?: Record<string, unknown> },
  ) => Promise<void>;
  onSaveDeliveryPresetProfile: (preset: DeliveryPresetKey, scope: 'session' | 'batch' | 'both', label: string) => void;
  onExportDeliveryPresetProfile: (profile: DeliveryPresetProfile) => void;
  onRemoveDeliveryPresetProfile: (id: string) => void;
  onSelectAllBatch: () => void;
  onClearBatchSelection: () => void;
  onDownloadAsset: (path: string | null) => void;
}

function formatMasterSourceLabel(value: DeliveryPresetProfile['masterSource']): string {
  switch (value) {
    case 'scene_linear':
      return '장면 선형 마스터';
    case 'raster':
      return '래스터 결과';
    case 'mixed':
      return '혼합 구성';
    default:
      return value;
  }
}

function formatScopeLabel(value: DeliveryPresetProfile['scope']): string {
  switch (value) {
    case 'batch':
      return '일괄 전용';
    case 'both':
      return '세션+일괄';
    default:
      return '세션 전용';
  }
}

function formatStageLabel(value: DeliveryPresetProfile['stage']): string {
  switch (value) {
    case 'review':
      return '검토 단계';
    case 'archive':
      return '보관 단계';
    default:
      return '마무리 단계';
  }
}

export function FinishDeliveryDesk({
  intakeReady,
  packageBusy,
  batchPackageBusy,
  optionGridTemplateColumns,
  deliveryPresetProfiles,
  finishExportPresets,
  finishTelemetry,
  selectedBatchSessions,
  selectedBatchSessionIds,
  recentSessionsCount,
  lastBatchReportPath,
  onImportProfiles,
  onExportLibrary,
  onDownloadSessionReport,
  onApplyDeliveryPresetProfile,
  onExportBatchDelivery,
  onExportDeliveryPresetPackage,
  onSaveDeliveryPresetProfile,
  onExportDeliveryPresetProfile,
  onRemoveDeliveryPresetProfile,
  onSelectAllBatch,
  onClearBatchSelection,
  onDownloadAsset,
}: FinishDeliveryDeskProps) {
  const deliveryPresetImportInputRef = React.useRef<HTMLInputElement | null>(null);
  const deliveryStatusChips = [
    { key: 'session', label: intakeReady ? '세션 출력 준비됨' : '세션 출력 준비 대기', tone: intakeReady ? 'success' as const : 'default' as const },
    { key: 'profiles', label: `저장 프리셋 ${deliveryPresetProfiles.length}`, tone: deliveryPresetProfiles.length ? 'accent' as const : 'default' as const },
    { key: 'batch', label: `일괄 선택 ${selectedBatchSessionIds.length}`, tone: selectedBatchSessionIds.length ? 'warning' as const : 'default' as const },
  ];
  const deliveryOverviewItems = [
    {
      label: '마스터 소스',
      value: finishExportPresets.length ? '세션 출력 기준' : '출력 없음',
      note: '선택된 납품 프리셋이 현재 세션 산출물에서 무엇을 묶을지 정합니다.',
    },
    {
      label: '세션 저장',
      value: packageBusy ? '내보내기 진행 중' : '저장 가능',
      note: intakeReady ? '세션 패키지와 보고서를 저장할 수 있습니다.' : '세션 산출물이 필요합니다.',
    },
    {
      label: '일괄 처리',
      value: selectedBatchSessionIds.length ? `${selectedBatchSessionIds.length}개 세션 선택됨` : '선택 대기',
      note: '최근 세션을 골라 같은 납품 프리셋을 반복 적용합니다.',
    },
  ];

  return (
    <section
      style={{
        ...sectionCardStyle('warm'),
        gap: 18,
        background: studioTokens.color.surface,
        border: `1px solid ${studioTokens.color.line}`,
      }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(280px, 0.8fr)', gap: 18, alignItems: 'start' }}>
        <div style={{ display: 'grid', gap: 10 }}>
          <span style={{ ...chipStyle('accent'), width: 'fit-content' }}>납품 준비</span>
          <div style={{ display: 'grid', gap: 6 }}>
            <strong style={{ fontSize: 24, lineHeight: 1.1, color: studioTokens.color.accent }}>최종 납품 보드</strong>
            <span style={{ fontSize: 13, color: studioTokens.color.inkSoft, lineHeight: 1.65 }}>
              마스터 소스, 납품 프리셋, 세션 저장, 일괄 처리.
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {deliveryStatusChips.map((chip) => (
              <span key={chip.key} style={chipStyle(chip.tone)}>
                {chip.label}
              </span>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input
              ref={deliveryPresetImportInputRef}
              type="file"
              accept="application/json,.json"
              style={{ display: 'none' }}
              onChange={(event) => void onImportProfiles(event)}
            />
            <button type="button" style={buttonStyle(false, !deliveryPresetProfiles.length)} onClick={onExportLibrary} disabled={!deliveryPresetProfiles.length}>
              사전 설정 보관함 내보내기
            </button>
            <button type="button" style={buttonStyle(false)} onClick={() => deliveryPresetImportInputRef.current?.click()}>
              납품 사전 설정 불러오기
            </button>
            <button type="button" style={buttonStyle(false, !intakeReady)} onClick={onDownloadSessionReport} disabled={!intakeReady}>
              세션 보고서 다운로드
            </button>
          </div>
        </div>

        <div
          style={{
            ...sectionCardStyle('default'),
            gap: 10,
            padding: 18,
            background: studioTokens.color.panel,
            boxShadow: 'none',
          }}
        >
          <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>납품 준비 보드</strong>
          <div style={{ display: 'grid', gap: 10 }}>
            {deliveryOverviewItems.map((item) => (
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

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 14 }}>
        <section style={sectionCardStyle('soft')}>
          <div style={{ display: 'grid', gap: 4 }}>
            <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>납품 프리셋</strong>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
              자주 쓰는 세션 저장과 일괄 납품 구성을 저장하고 다시 불러옵니다.
            </span>
          </div>
          {deliveryPresetProfiles.length ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {deliveryPresetProfiles.map((profile) => (
                <article key={profile.id} style={tileStyle()}>
                  {(() => {
                    const descriptor = describeDeliveryPreset(profile.preset);
                    return (
                      <>
                <div style={{ display: 'grid', gap: 4 }}>
                  <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{profile.name}</strong>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                    {descriptor.label} · {formatScopeLabel(profile.scope)} · {new Date(profile.createdAt).toLocaleString()}
                  </span>
                  <span style={{ fontSize: 12, color: studioTokens.color.inkSoft, lineHeight: 1.5 }}>
                    {descriptor.profileId} · {formatStageLabel(profile.stage)} · {formatMasterSourceLabel(profile.masterSource)}
                  </span>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>{profile.description || descriptor.description}</span>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {profile.scope !== 'batch' ? (
                    <button type="button" style={buttonStyle(false, packageBusy)} onClick={() => void onApplyDeliveryPresetProfile(profile)} disabled={packageBusy}>
                      세션 저장
                    </button>
                  ) : null}
                  {profile.scope !== 'session' ? (
                    <button
                      type="button"
                      style={buttonStyle(false, batchPackageBusy || !selectedBatchSessionIds.length)}
                      onClick={() => void onExportBatchDelivery(profile.preset)}
                      disabled={batchPackageBusy || !selectedBatchSessionIds.length}
                    >
                      일괄 저장
                    </button>
                  ) : null}
                  <button type="button" style={buttonStyle(false)} onClick={() => onExportDeliveryPresetProfile(profile)}>
                    내보내기
                  </button>
                  <button type="button" style={buttonStyle(false)} onClick={() => onRemoveDeliveryPresetProfile(profile.id)}>
                    삭제
                  </button>
                </div>
                      </>
                    );
                  })()}
                </article>
              ))}
            </div>
          ) : (
            <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
              저장한 납품 구성이 아직 없습니다.
            </span>
          )}
        </section>

        <section style={sectionCardStyle('default')}>
          <div style={{ display: 'grid', gap: 4 }}>
            <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>세션 내보내기</strong>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.55 }}>
              선택한 결과를 묶음으로 저장합니다.
            </span>
          </div>
          <div style={{ display: 'grid', gap: 10 }}>
            {finishExportPresets.map((preset) => (
              <article key={preset.key} style={tileStyle()}>
                <div style={{ display: 'grid', gap: 4 }}>
                  <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{preset.label}</strong>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>{preset.description}</span>
                  <span style={{ fontSize: 12, color: studioTokens.color.inkSoft }}>{preset.items.length}개 파일</span>
                </div>
                <button
                  type="button"
                  style={buttonStyle(true, !intakeReady || !preset.items.length || packageBusy)}
                  onClick={() => void onExportDeliveryPresetPackage(preset.key, {
                    label: preset.key,
                    metadata: { preset: preset.key, preset_label: preset.label },
                  })}
                  disabled={!intakeReady || !preset.items.length || packageBusy}
                >
                  {preset.label} 저장
                </button>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button type="button" style={buttonStyle(false)} onClick={() => onSaveDeliveryPresetProfile(preset.key, 'session', preset.label)}>
                    세션 빠른 저장
                  </button>
                  <button type="button" style={buttonStyle(false)} onClick={() => onSaveDeliveryPresetProfile(preset.key, 'both', preset.label)}>
                    흐름 빠른 저장
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>

      <div style={{ display: 'grid', gap: 10 }}>
        <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>세션 출력 요약</strong>
        <div style={{ display: 'grid', gridTemplateColumns: optionGridTemplateColumns, gap: 10 }}>
          {finishTelemetry.map((item) => (
            <div key={item.label} style={tileStyle()}>
              <span style={{ fontSize: 11, fontWeight: 700, color: studioTokens.color.muted }}>{item.label}</span>
              <strong style={{ fontSize: 13, color: studioTokens.color.accent, lineHeight: 1.45 }}>{item.value}</strong>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gap: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'grid', gap: 4 }}>
            <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>일괄 처리 대기열</strong>
            <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>
              최근 세션에서 고른 세션에 현재 납품 사전 설정을 한 번에 적용합니다.
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" style={buttonStyle(false, !recentSessionsCount)} onClick={onSelectAllBatch} disabled={!recentSessionsCount}>
              최근 세션 전체 선택
            </button>
            <button type="button" style={buttonStyle(false, !selectedBatchSessionIds.length)} onClick={onClearBatchSelection} disabled={!selectedBatchSessionIds.length}>
              선택 해제
            </button>
            <button type="button" style={buttonStyle(false, !lastBatchReportPath)} onClick={() => onDownloadAsset(lastBatchReportPath)} disabled={!lastBatchReportPath}>
              일괄 보고서 다운로드
            </button>
          </div>
        </div>
        {selectedBatchSessions.length ? (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {selectedBatchSessions.map((session) => (
              <span key={session.session_id} style={chipStyle('default')}>
                {session.primary_file_name ?? session.session_id}
              </span>
            ))}
          </div>
        ) : (
          <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
            일괄 처리할 세션을 선택하세요.
          </span>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: optionGridTemplateColumns, gap: 12 }}>
          {finishExportPresets.map((preset) => (
            <article key={`batch_${preset.key}`} style={tileStyle()}>
              <div style={{ display: 'grid', gap: 4 }}>
                <strong style={{ fontSize: 13, color: studioTokens.color.accent }}>{preset.label}</strong>
                <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.5 }}>{preset.description}</span>
                <span style={{ fontSize: 12, color: studioTokens.color.inkSoft }}>{selectedBatchSessionIds.length}개 세션 선택</span>
              </div>
              <button
                type="button"
                style={buttonStyle(true, !selectedBatchSessionIds.length || batchPackageBusy)}
                onClick={() => void onExportBatchDelivery(preset.key)}
                disabled={!selectedBatchSessionIds.length || batchPackageBusy}
              >
                {preset.label} 일괄 저장
              </button>
              <button type="button" style={buttonStyle(false)} onClick={() => onSaveDeliveryPresetProfile(preset.key, 'batch', preset.label)}>
                일괄 빠른 저장
              </button>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
