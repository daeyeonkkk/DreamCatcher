import type React from 'react';

export const studioTokens = {
  color: {
    ink: '#15191d',
    inkSoft: '#35404a',
    muted: '#6a7682',
    line: '#d9e0e7',
    lineStrong: '#b8c3cf',
    surface: '#ffffff',
    surfaceSoft: '#f5f7fa',
    surfaceTint: '#e8f3f1',
    surfaceWarm: '#f6f1e7',
    canvas: '#edf1f5',
    canvasDark: '#1e252b',
    panel: '#fafbfc',
    accent: '#163d44',
    accentSoft: '#dcefed',
    warning: '#9b5d16',
    warningSoft: '#fff3dd',
    success: '#237150',
    successSoft: '#ddf0e6',
    error: '#a23a34',
    errorSoft: '#f9e3df',
    blueSoft: '#e6eef8',
    blueInk: '#285a7c',
  },
  radius: {
    s: 6,
    m: 8,
    l: 8,
    xl: 8,
    pill: 999,
  },
  shadow: {
    card: '0 18px 48px rgba(21, 25, 29, 0.10)',
    soft: '0 10px 28px rgba(21, 25, 29, 0.07)',
  },
  breakpoint: {
    desktop: 1320,
    laptop: 1100,
    tablet: 720,
  },
  font: {
    family: '"Segoe UI", "Apple SD Gothic Neo", sans-serif',
  },
} as const;

export function buttonStyle(primary: boolean, disabled = false): React.CSSProperties {
  return {
    padding: '10px 13px',
    borderRadius: studioTokens.radius.m,
    border: primary ? `1px solid ${studioTokens.color.accent}` : `1px solid ${studioTokens.color.lineStrong}`,
    background: primary ? studioTokens.color.accent : studioTokens.color.surface,
    color: primary ? studioTokens.color.surface : studioTokens.color.accent,
    fontWeight: 700,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.45 : 1,
  };
}

export const controlStyle: React.CSSProperties = {
  minHeight: 40,
  borderRadius: studioTokens.radius.s,
  border: `1px solid ${studioTokens.color.lineStrong}`,
  background: studioTokens.color.surface,
  padding: '0 12px',
  fontSize: 13,
  color: studioTokens.color.accent,
};

export function sectionCardStyle(tone: 'default' | 'soft' | 'accent' | 'warm' = 'default'): React.CSSProperties {
  const background = tone === 'soft'
    ? studioTokens.color.surfaceSoft
    : tone === 'accent'
      ? studioTokens.color.accentSoft
      : tone === 'warm'
        ? studioTokens.color.surfaceWarm
        : studioTokens.color.surface;
  return {
    display: 'grid',
    gap: 12,
    padding: 18,
    borderRadius: studioTokens.radius.l,
    border: `1px solid ${studioTokens.color.line}`,
    background,
    boxShadow: 'none',
  };
}

export function tileStyle(tone: 'default' | 'soft' | 'accent' | 'warm' | 'success' | 'warning' = 'default'): React.CSSProperties {
  const background = tone === 'accent'
    ? studioTokens.color.accentSoft
    : tone === 'success'
      ? studioTokens.color.successSoft
      : tone === 'warning'
        ? studioTokens.color.warningSoft
        : tone === 'warm'
          ? studioTokens.color.surfaceWarm
          : studioTokens.color.surfaceSoft;
  return {
    display: 'grid',
    gap: 6,
    padding: '12px 14px',
    borderRadius: studioTokens.radius.m,
    background,
    border: `1px solid ${studioTokens.color.line}`,
  };
}

export function chipStyle(
  tone: 'default' | 'accent' | 'success' | 'warning' | 'ink' = 'default',
): React.CSSProperties {
  const palette = tone === 'accent'
    ? { background: studioTokens.color.surfaceTint, color: studioTokens.color.accent }
    : tone === 'success'
      ? { background: studioTokens.color.successSoft, color: studioTokens.color.success }
      : tone === 'warning'
        ? { background: studioTokens.color.warningSoft, color: studioTokens.color.warning }
        : tone === 'ink'
          ? { background: studioTokens.color.accent, color: studioTokens.color.surface }
          : { background: studioTokens.color.surface, color: '#536274' };
  return {
    padding: '5px 9px',
    borderRadius: studioTokens.radius.pill,
    border: `1px solid ${studioTokens.color.line}`,
    fontSize: 11,
    fontWeight: 700,
    ...palette,
  };
}
