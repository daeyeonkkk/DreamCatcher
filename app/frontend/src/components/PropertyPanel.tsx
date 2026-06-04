import React from 'react';
import { CheckCircle2, ClipboardList, SlidersHorizontal, TriangleAlert } from 'lucide-react';
import { studioTokens } from '../designTokens';

export interface PropertyPanelAction {
  label: string;
  onClick?: () => void;
  disabled?: boolean;
}

export interface PropertyPanelItem {
  label: string;
  value: string;
  tone?: 'default' | 'success' | 'warning';
}

export interface PropertyPanelSection {
  title: string;
  description?: string;
  items?: PropertyPanelItem[];
  actions?: PropertyPanelAction[];
}

interface PropertyPanelProps {
  title: string;
  sections: PropertyPanelSection[];
  promptLabel: string;
  promptPlaceholder: string;
  promptValue: string;
  onPromptChange: (value: string) => void;
  compact?: boolean;
  sliders: Array<{
    key: string;
    label: string;
    min: number;
    max: number;
    step?: number;
    value: number;
    onChange: (value: number) => void;
  }>;
}

const toneColors: Record<NonNullable<PropertyPanelItem['tone']>, React.CSSProperties> = {
  default: {
    background: studioTokens.color.surfaceSoft,
    color: studioTokens.color.inkSoft,
    border: `1px solid ${studioTokens.color.line}`,
  },
  success: {
    background: studioTokens.color.successSoft,
    color: studioTokens.color.success,
    border: '1px solid #badcc9',
  },
  warning: {
    background: studioTokens.color.warningSoft,
    color: studioTokens.color.warning,
    border: '1px solid #efd29b',
  },
};

export function PropertyPanel({
  title,
  sections,
  promptLabel,
  promptPlaceholder,
  promptValue,
  onPromptChange,
  compact = false,
  sliders,
}: PropertyPanelProps) {
  const effectiveCompact = compact || (typeof window !== 'undefined' && window.innerWidth < 1100);
  const promptGridTemplateColumns = effectiveCompact ? '1fr' : 'minmax(0, 1fr)';

  return (
    <aside
      style={{
        display: 'grid',
        alignContent: 'start',
        gap: 14,
        padding: 14,
        background: studioTokens.color.surface,
        minWidth: effectiveCompact ? 0 : 304,
      }}
    >
      <div style={{ display: 'grid', gap: 8 }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 7,
            width: 'fit-content',
            padding: '6px 9px',
            borderRadius: studioTokens.radius.m,
            fontSize: 11,
            fontWeight: 900,
            background: studioTokens.color.warningSoft,
            color: studioTokens.color.warning,
          }}
        >
          <ClipboardList size={14} />
          판단 패널
        </span>
        <div style={{ display: 'grid', gap: 3 }}>
          <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>{title}</strong>
          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.45 }}>
            결과 상태와 다음 작업을 확인하세요.
          </span>
        </div>
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
          <CounterChip label="판단" value={sections.length} />
          <CounterChip label="조정" value={sliders.length} warning />
        </div>
      </div>

      <section
        style={{
          display: 'grid',
          gap: 12,
          padding: 12,
          borderRadius: studioTokens.radius.m,
          background: studioTokens.color.panel,
          border: `1px solid ${studioTokens.color.line}`,
        }}
      >
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <SlidersHorizontal size={16} color={studioTokens.color.accent} />
          <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>지시와 조정</strong>
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: promptGridTemplateColumns,
            gap: 12,
            alignItems: 'start',
          }}
        >
          <label style={{ display: 'grid', gap: 7 }}>
            <span style={{ fontSize: 12, fontWeight: 800, color: studioTokens.color.inkSoft }}>{promptLabel}</span>
            <textarea
              rows={5}
              value={promptValue}
              onChange={(event) => onPromptChange(event.target.value)}
              placeholder={promptPlaceholder}
              style={{
                resize: 'vertical',
                minHeight: 118,
                borderRadius: studioTokens.radius.m,
                border: `1px solid ${studioTokens.color.lineStrong}`,
                padding: 11,
                lineHeight: 1.5,
                fontSize: 13,
                color: studioTokens.color.ink,
                background: studioTokens.color.surface,
              }}
            />
          </label>

          <div style={{ display: 'grid', gap: 10 }}>
            {sliders.length ? (
              sliders.map((slider) => (
                <label key={slider.key} style={{ display: 'grid', gap: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, color: studioTokens.color.inkSoft }}>
                    <span>{slider.label}</span>
                    <strong>{slider.value}</strong>
                  </div>
                  <input
                    type="range"
                    min={slider.min}
                    max={slider.max}
                    step={slider.step ?? 1}
                    value={slider.value}
                    onChange={(event) => slider.onChange(Number(event.target.value))}
                  />
                </label>
              ))
            ) : (
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.45 }}>
                현재 단계에서 사용할 실시간 조정이 아직 없습니다.
              </span>
            )}
          </div>
        </div>
      </section>

      {sections.map((section) => (
        <section
          key={section.title}
          style={{
            display: 'grid',
            gap: 10,
            padding: 12,
            borderRadius: studioTokens.radius.m,
            background: studioTokens.color.surface,
            border: `1px solid ${studioTokens.color.line}`,
          }}
        >
          <div style={{ display: 'grid', gap: 4 }}>
            <strong style={{ fontSize: 13, color: studioTokens.color.ink }}>{section.title}</strong>
            {section.description ? (
              <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.45 }}>{section.description}</span>
            ) : null}
          </div>

          {section.items?.length ? (
            <div style={{ display: 'grid', gap: 7 }}>
              {section.items.map((item) => {
                const tone = item.tone ?? 'default';
                const Icon = tone === 'warning' ? TriangleAlert : tone === 'success' ? CheckCircle2 : ClipboardList;
                return (
                  <div
                    key={`${section.title}_${item.label}`}
                    style={{
                      ...toneColors[tone],
                      display: 'grid',
                      gridTemplateColumns: 'auto minmax(0, 1fr)',
                      gap: 8,
                      alignItems: 'start',
                      padding: '9px 10px',
                      borderRadius: studioTokens.radius.m,
                    }}
                  >
                    <Icon size={14} style={{ marginTop: 2, flex: '0 0 auto' }} />
                    <span style={{ display: 'grid', gap: 2, minWidth: 0 }}>
                      <span style={{ fontSize: 11, fontWeight: 800 }}>{item.label}</span>
                      <span style={{ fontSize: 12, lineHeight: 1.45, overflowWrap: 'anywhere' }}>{item.value}</span>
                    </span>
                  </div>
                );
              })}
            </div>
          ) : null}

          {section.actions?.length ? (
            <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
              {section.actions.map((action) => (
                <button
                  key={`${section.title}_${action.label}`}
                  type="button"
                  onClick={action.onClick}
                  disabled={action.disabled}
                  style={{
                    borderRadius: studioTokens.radius.m,
                    border: `1px solid ${studioTokens.color.lineStrong}`,
                    background: studioTokens.color.surfaceSoft,
                    color: studioTokens.color.accent,
                    padding: '8px 10px',
                    fontSize: 12,
                    fontWeight: 800,
                    cursor: action.disabled ? 'not-allowed' : 'pointer',
                    opacity: action.disabled ? 0.45 : 1,
                  }}
                >
                  {action.label}
                </button>
              ))}
            </div>
          ) : null}
        </section>
      ))}
    </aside>
  );
}

function CounterChip({ label, value, warning = false }: { label: string; value: number; warning?: boolean }) {
  return (
    <span
      style={{
        padding: '5px 8px',
        borderRadius: studioTokens.radius.pill,
        fontSize: 11,
        fontWeight: 800,
        color: warning ? studioTokens.color.warning : studioTokens.color.accent,
        background: warning ? studioTokens.color.warningSoft : studioTokens.color.accentSoft,
        border: `1px solid ${studioTokens.color.line}`,
      }}
    >
      {label} {value}
    </span>
  );
}
