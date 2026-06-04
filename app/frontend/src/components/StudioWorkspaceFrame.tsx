import React, { useEffect, useState } from 'react';
import { buttonStyle, studioTokens } from '../designTokens';
import { studioShellLocale } from '../i18n/studioShellLocale';

interface StudioWorkspaceFrameProps {
  topBar: React.ReactNode;
  rail: React.ReactNode;
  main: React.ReactNode;
  inspector: React.ReactNode;
  sessionStrip?: React.ReactNode;
  shellGridTemplateColumns: string;
  isStackedLayout: boolean;
}

export function StudioWorkspaceFrame({
  topBar,
  rail,
  main,
  inspector,
  sessionStrip,
  shellGridTemplateColumns,
  isStackedLayout,
}: StudioWorkspaceFrameProps) {
  const [showRail, setShowRail] = useState(!isStackedLayout);
  const [showInspector, setShowInspector] = useState(!isStackedLayout);

  useEffect(() => {
    if (!isStackedLayout) {
      setShowRail(true);
      setShowInspector(true);
      return;
    }
    setShowRail(false);
    setShowInspector(false);
  }, [isStackedLayout]);

  return (
    <div
      style={{
        minHeight: '100vh',
        background: studioTokens.color.canvas,
        color: studioTokens.color.ink,
        fontFamily: studioTokens.font.family,
      }}
    >
      {topBar}
      {isStackedLayout ? (
        <div
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 35,
            padding: '10px 12px',
            borderBottom: `1px solid ${studioTokens.color.line}`,
            background: 'rgba(245, 247, 250, 0.96)',
            backdropFilter: 'blur(14px)',
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
              gap: 8,
            }}
          >
            <button type="button" style={buttonStyle(showRail)} onClick={() => setShowRail((current) => !current)}>
              {showRail ? studioShellLocale.layout.hideRail : studioShellLocale.layout.showRail}
            </button>
            <button type="button" style={buttonStyle(showInspector)} onClick={() => setShowInspector((current) => !current)}>
              {showInspector ? studioShellLocale.layout.hideInspector : studioShellLocale.layout.showInspector}
            </button>
          </div>
        </div>
      ) : null}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: shellGridTemplateColumns,
          gap: 0,
          alignItems: 'stretch',
          minHeight: isStackedLayout ? 'auto' : 'calc(100vh - 132px)',
          borderBottom: `1px solid ${studioTokens.color.line}`,
          borderTop: `1px solid ${studioTokens.color.line}`,
          background: studioTokens.color.surfaceSoft,
          margin: '0 auto',
        }}
      >
        {!isStackedLayout || showRail ? (
          <div
            style={{
              overflow: 'auto',
              borderRight: isStackedLayout ? 'none' : `1px solid ${studioTokens.color.line}`,
              borderBottom: isStackedLayout ? `1px solid ${studioTokens.color.line}` : 'none',
              background: studioTokens.color.surface,
            }}
          >
            {rail}
          </div>
        ) : null}
        <div style={{ minWidth: 0, background: studioTokens.color.surfaceSoft }}>{main}</div>
        {!isStackedLayout || showInspector ? (
          <div
            style={{
              overflow: 'auto',
              borderLeft: isStackedLayout ? 'none' : `1px solid ${studioTokens.color.line}`,
              borderTop: isStackedLayout ? `1px solid ${studioTokens.color.line}` : 'none',
              background: studioTokens.color.surface,
            }}
          >
            {inspector}
          </div>
        ) : null}
      </div>
      {sessionStrip ? (
        <div
          style={{
            position: isStackedLayout ? 'relative' : 'sticky',
            bottom: isStackedLayout ? 'auto' : 0,
            zIndex: isStackedLayout ? 1 : 30,
            borderTop: `1px solid ${studioTokens.color.line}`,
            background: 'rgba(255, 255, 255, 0.96)',
            backdropFilter: 'blur(16px)',
          }}
        >
          {sessionStrip}
        </div>
      ) : null}
    </div>
  );
}
