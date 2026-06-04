import React from 'react';
import { studioTokens } from '../designTokens';

interface StatusToastProps {
  message: string;
  tone?: 'info' | 'success' | 'warning' | 'error';
}

const tonePalette: Record<NonNullable<StatusToastProps['tone']>, React.CSSProperties> = {
  info: {
    background: studioTokens.color.blueSoft,
    color: studioTokens.color.blueInk,
    border: '1px solid #c8d8f0',
  },
  success: {
    background: studioTokens.color.successSoft,
    color: '#1d6b3c',
    border: '1px solid #c9e3d1',
  },
  warning: {
    background: studioTokens.color.warningSoft,
    color: '#8d6100',
    border: '1px solid #f0ddb2',
  },
  error: {
    background: studioTokens.color.errorSoft,
    color: studioTokens.color.error,
    border: '1px solid #efc9c9',
  },
};

export function StatusToast({ message, tone = 'info' }: StatusToastProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        ...tonePalette[tone],
        padding: '12px 14px',
        borderRadius: studioTokens.radius.m,
        fontSize: 13,
        lineHeight: 1.5,
      }}
    >
      {message}
    </div>
  );
}
