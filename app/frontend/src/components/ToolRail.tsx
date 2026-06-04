import React from 'react';
import {
  Brush,
  Columns2,
  Crop,
  Eraser,
  ImagePlus,
  Layers3,
  PackageCheck,
  Scissors,
  Sparkles,
  SunMedium,
} from 'lucide-react';
import { studioTokens } from '../designTokens';

export interface ToolRailItem {
  key: string;
  label: string;
  description: string;
  group: string;
  disabled?: boolean;
}

interface ToolRailProps {
  title: string;
  items: ToolRailItem[];
  activeTool: string;
  onSelectTool: (tool: string) => void;
  compact?: boolean;
  dense?: boolean;
}

const toolIcons: Record<string, typeof Scissors> = {
  removeBg: Scissors,
  replaceBg: ImagePlus,
  replaceObject: Eraser,
  expandCanvas: Crop,
  relight: SunMedium,
  retouch: Brush,
  enhance: Sparkles,
  compare: Columns2,
  finish: PackageCheck,
};

const groupOrder = ['마스크', '생성 편집', '보정', '비교 보기', '내보내기'];

export function ToolRail({ title, items, activeTool, onSelectTool, compact = false, dense = false }: ToolRailProps) {
  const effectiveCompact = compact || (typeof window !== 'undefined' && window.innerWidth < 1100);
  const activeItem = items.find((item) => item.key === activeTool) ?? null;
  const groups = items.reduce<Record<string, ToolRailItem[]>>((acc, item) => {
    acc[item.group] = acc[item.group] ?? [];
    acc[item.group].push(item);
    return acc;
  }, {});
  const orderedGroups = [
    ...groupOrder.filter((group) => groups[group]),
    ...Object.keys(groups).filter((group) => !groupOrder.includes(group)),
  ];

  return (
    <aside
      style={{
        display: 'grid',
        alignContent: 'start',
        gap: dense ? 12 : 14,
        padding: dense ? 12 : 14,
        background: studioTokens.color.surface,
        minWidth: effectiveCompact ? 0 : dense ? 224 : 260,
      }}
      aria-label={title}
    >
      <div style={{ display: 'grid', gap: 8 }}>
        <span
          style={{
            display: 'inline-flex',
            gap: 7,
            alignItems: 'center',
            width: 'fit-content',
            padding: '6px 9px',
            borderRadius: studioTokens.radius.m,
            fontSize: 11,
            fontWeight: 900,
            background: studioTokens.color.accentSoft,
            color: studioTokens.color.accent,
          }}
        >
          <Layers3 size={14} />
          작업 레일
        </span>
        <div style={{ display: 'grid', gap: 3 }}>
          <strong style={{ fontSize: 14, color: studioTokens.color.ink }}>{title}</strong>
          <span style={{ fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.45 }}>
            {activeItem ? activeItem.description : '도구를 선택하세요.'}
          </span>
        </div>
      </div>

      <section
        style={{
          display: 'grid',
          gap: 7,
          padding: 10,
          borderRadius: studioTokens.radius.m,
          border: `1px solid ${studioTokens.color.line}`,
          background: studioTokens.color.panel,
        }}
      >
        <span style={{ fontSize: 11, fontWeight: 800, color: studioTokens.color.muted }}>
          현재 도구
        </span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', minWidth: 0 }}>
          {activeItem ? <ToolGlyph toolKey={activeItem.key} active /> : null}
          <strong style={{ fontSize: 14, color: studioTokens.color.ink, lineHeight: 1.3 }}>
            {activeItem?.label ?? '도구를 고르세요'}
          </strong>
        </div>
      </section>

      {orderedGroups.map((group) => (
        <section key={group} style={{ display: 'grid', gap: 6 }}>
          <h2
            style={{
              margin: '6px 2px 0',
              fontSize: 11,
              fontWeight: 900,
              color: studioTokens.color.muted,
            }}
          >
            {group}
          </h2>
          <div style={{ display: 'grid', gap: 6 }}>
            {groups[group].map((item) => {
              const active = item.key === activeTool;
              const showDescription = !dense || active;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => onSelectTool(item.key)}
                  disabled={item.disabled}
                  title={item.description}
                  aria-label={`${item.label}: ${item.description}`}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'auto minmax(0, 1fr)',
                    gap: 9,
                    alignItems: 'center',
                    padding: dense ? '9px 10px' : '10px 11px',
                    borderRadius: studioTokens.radius.m,
                    border: active ? `1px solid ${studioTokens.color.accent}` : `1px solid ${studioTokens.color.line}`,
                    background: active ? studioTokens.color.accent : studioTokens.color.surface,
                    color: active ? studioTokens.color.surface : studioTokens.color.ink,
                    textAlign: 'left',
                    cursor: item.disabled ? 'not-allowed' : 'pointer',
                    opacity: item.disabled ? 0.45 : 1,
                  }}
                >
                  <ToolGlyph toolKey={item.key} active={active} />
                  <span style={{ display: 'grid', gap: showDescription ? 3 : 0, minWidth: 0 }}>
                    <strong style={{ fontSize: 13, lineHeight: 1.25, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.label}
                    </strong>
                    {showDescription ? (
                      <span style={{ fontSize: 12, lineHeight: 1.4, opacity: active ? 0.86 : 0.72 }}>
                        {item.description}
                      </span>
                    ) : null}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </aside>
  );
}

function ToolGlyph({ toolKey, active }: { toolKey: string; active?: boolean }) {
  const Icon = toolIcons[toolKey] ?? Sparkles;
  return (
    <span
      style={{
        width: 28,
        height: 28,
        borderRadius: studioTokens.radius.m,
        display: 'grid',
        placeItems: 'center',
        border: active ? '1px solid rgba(255, 255, 255, 0.28)' : `1px solid ${studioTokens.color.line}`,
        background: active ? 'rgba(255, 255, 255, 0.12)' : studioTokens.color.surfaceSoft,
        color: active ? studioTokens.color.surface : studioTokens.color.accent,
        flex: '0 0 auto',
      }}
      aria-hidden="true"
    >
      <Icon size={16} strokeWidth={2.2} />
    </span>
  );
}
