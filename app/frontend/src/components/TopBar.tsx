import React from 'react';
import { Activity, Gauge, RotateCcw, Search, ShieldCheck } from 'lucide-react';
import { studioTokens } from '../designTokens';

export interface TopBarAction {
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  tone?: 'default' | 'primary' | 'quiet';
}

interface TopBarProps {
  title: string;
  subtitle: string;
  sessionLabel: string;
  pipelineLabel: string;
  healthLabel: string;
  actions?: TopBarAction[];
}

const toneStyles: Record<NonNullable<TopBarAction['tone']>, React.CSSProperties> = {
  default: {
    background: studioTokens.color.surface,
    border: `1px solid ${studioTokens.color.lineStrong}`,
    color: studioTokens.color.accent,
  },
  primary: {
    background: studioTokens.color.accent,
    border: `1px solid ${studioTokens.color.accent}`,
    color: studioTokens.color.surface,
  },
  quiet: {
    background: studioTokens.color.surfaceSoft,
    border: `1px solid ${studioTokens.color.line}`,
    color: studioTokens.color.inkSoft,
  },
};

const actionIcons: Record<string, typeof Activity> = {
  '세션 초기화': RotateCcw,
  '입력 다시 분석': Search,
};

export function TopBar({
  title,
  subtitle,
  sessionLabel,
  pipelineLabel,
  healthLabel,
  actions = [],
}: TopBarProps) {
  const compact = typeof window !== 'undefined' && window.innerWidth < studioTokens.breakpoint.laptop;

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 45,
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'minmax(300px, 0.9fr) minmax(340px, 1fr) auto',
        gap: compact ? 12 : 16,
        alignItems: 'center',
        padding: compact ? '12px 14px' : '12px 18px',
        borderBottom: `1px solid ${studioTokens.color.line}`,
        background: 'rgba(255, 255, 255, 0.96)',
        backdropFilter: 'blur(16px)',
      }}
    >
      <div style={{ display: 'grid', gap: 5, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <span
            style={{
              width: 28,
              height: 28,
              borderRadius: studioTokens.radius.m,
              display: 'grid',
              placeItems: 'center',
              background: studioTokens.color.accent,
              color: studioTokens.color.surface,
              flex: '0 0 auto',
              fontSize: 13,
              fontWeight: 900,
            }}
            aria-hidden="true"
          >
            D
          </span>
          <div style={{ display: 'grid', gap: 1, minWidth: 0 }}>
            <strong
              style={{
                fontSize: 15,
                color: studioTokens.color.ink,
                lineHeight: 1.15,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {title}
            </strong>
            <span
              style={{
                color: studioTokens.color.muted,
                fontSize: 12,
                lineHeight: 1.35,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {subtitle}
            </span>
          </div>
        </div>
        <span
          style={{
            width: 'fit-content',
            maxWidth: '100%',
            padding: '4px 8px',
            borderRadius: studioTokens.radius.pill,
            background: studioTokens.color.surfaceSoft,
            color: studioTokens.color.muted,
            fontSize: 11,
            fontWeight: 700,
            border: `1px solid ${studioTokens.color.line}`,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {sessionLabel}
        </span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: compact ? '1fr' : 'repeat(2, minmax(0, 1fr))',
          gap: 8,
          minWidth: 0,
        }}
      >
        <StatusCell icon={<Activity size={17} color={studioTokens.color.accent} />} label="현재 상태" value={pipelineLabel} />
        <StatusCell icon={<Gauge size={17} color={studioTokens.color.success} />} label="런타임 점검" value={healthLabel} />
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexWrap: 'wrap',
          justifyContent: compact ? 'flex-start' : 'flex-end',
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 7,
            padding: '8px 10px',
            borderRadius: studioTokens.radius.m,
            border: `1px solid ${studioTokens.color.line}`,
            background: studioTokens.color.accentSoft,
            color: studioTokens.color.accent,
            fontSize: 12,
            fontWeight: 800,
          }}
        >
          <ShieldCheck size={15} />
          Frontier
        </span>
        {actions.map((action) => {
          const tone = action.tone ?? 'default';
          const Icon = actionIcons[action.label] ?? Activity;
          return (
            <button
              key={action.label}
              type="button"
              disabled={action.disabled}
              onClick={action.onClick}
              style={{
                ...toneStyles[tone],
                display: 'inline-flex',
                alignItems: 'center',
                gap: 7,
                borderRadius: studioTokens.radius.m,
                padding: '9px 11px',
                fontSize: 12,
                fontWeight: 800,
                cursor: action.disabled ? 'not-allowed' : 'pointer',
                opacity: action.disabled ? 0.45 : 1,
                whiteSpace: 'nowrap',
              }}
            >
              <Icon size={15} />
              {action.label}
            </button>
          );
        })}
      </div>
    </header>
  );
}

function StatusCell({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'auto minmax(0, 1fr)',
        gap: 8,
        alignItems: 'center',
        minHeight: 42,
        padding: '8px 10px',
        borderRadius: studioTokens.radius.m,
        border: `1px solid ${studioTokens.color.line}`,
        background: studioTokens.color.panel,
      }}
    >
      {icon}
      <div style={{ display: 'grid', gap: 2, minWidth: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: studioTokens.color.muted }}>
          {label}
        </span>
        <strong
          style={{
            fontSize: 13,
            color: studioTokens.color.ink,
            lineHeight: 1.25,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {value}
        </strong>
      </div>
    </div>
  );
}
