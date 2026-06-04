import {
  BadgeCheck,
  Camera,
  ClipboardCheck,
  FileImage,
  PackageCheck,
  ServerCog,
  WandSparkles,
} from 'lucide-react';
import type React from 'react';
import { studioTokens } from '../designTokens';

export interface WorkSurfaceNavItem {
  key: string;
  label: string;
  description: string;
  status: string;
}

interface StudioWorkSurfaceNavProps {
  items: WorkSurfaceNavItem[];
  activeKey: string;
  onSelect: (key: string) => void;
  compact?: boolean;
}

export function StudioWorkSurfaceNav({
  items,
  activeKey,
  onSelect,
  compact = false,
}: StudioWorkSurfaceNavProps) {
  const gridTemplateColumns = compact
    ? 'repeat(2, minmax(0, 1fr))'
    : `repeat(${items.length}, minmax(0, 1fr))`;

  return (
    <nav
      aria-label="작업면"
      style={{
        display: 'grid',
        gap: 8,
        padding: compact ? '8px 0' : '4px 0 8px',
        background: 'transparent',
      }}
    >
      <div
        role="tablist"
        aria-label="작업면 선택"
        style={{
          display: 'grid',
          gridTemplateColumns,
          gap: compact ? 8 : 6,
          border: `1px solid ${studioTokens.color.line}`,
          borderRadius: studioTokens.radius.m,
          padding: 6,
          background: 'rgba(255, 255, 255, 0.72)',
        }}
      >
        {items.map((item) => {
          const active = item.key === activeKey;
          const Icon = surfaceIcons[item.key] ?? FileImage;
          return (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onSelect(item.key)}
              style={{
                minHeight: compact ? 70 : 66,
                display: 'grid',
                gridTemplateColumns: compact ? 'auto minmax(0, 1fr)' : 'auto minmax(0, 1fr)',
                alignItems: 'center',
                gap: 9,
                padding: compact ? '10px 11px' : '10px 12px',
                border: active ? `1px solid ${studioTokens.color.accent}` : '1px solid transparent',
                borderRadius: studioTokens.radius.m,
                background: active ? studioTokens.color.accent : 'transparent',
                color: active ? studioTokens.color.surface : studioTokens.color.ink,
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'background 140ms ease, border-color 140ms ease, color 140ms ease',
              }}
              title={`${item.label}: ${item.description}`}
            >
              <span
                style={{
                  width: 30,
                  height: 30,
                  display: 'grid',
                  placeItems: 'center',
                  borderRadius: studioTokens.radius.m,
                  background: active ? 'rgba(255, 255, 255, 0.14)' : studioTokens.color.surface,
                  border: active ? '1px solid rgba(255, 255, 255, 0.20)' : `1px solid ${studioTokens.color.line}`,
                  color: active ? studioTokens.color.surface : studioTokens.color.accent,
                  flex: '0 0 auto',
                }}
                aria-hidden="true"
              >
                <Icon size={16} strokeWidth={2.2} />
              </span>
              <span style={{ display: 'grid', gap: 3, minWidth: 0 }}>
                <span style={{ display: 'flex', gap: 6, alignItems: 'center', minWidth: 0 }}>
                  <strong style={{ fontSize: 13, lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.label}</strong>
                  {active ? <BadgeCheck size={13} aria-hidden="true" /> : null}
                </span>
                <span
                  style={{
                    fontSize: 11,
                    lineHeight: 1.35,
                    color: active ? 'rgba(255, 255, 255, 0.78)' : studioTokens.color.muted,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {item.status}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}

const surfaceIcons: Record<string, typeof FileImage> = {
  intake: FileImage,
  raw: Camera,
  edit: WandSparkles,
  review: ClipboardCheck,
  deliver: PackageCheck,
  operate: ServerCog,
};
