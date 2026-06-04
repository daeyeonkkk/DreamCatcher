import type { StudioTelemetryEvent } from '../studioApi';

export interface StageItem {
  key: string;
  label: string;
}

export interface WorkspaceModeOption {
  key: string;
  label: string;
  description: string;
}

export interface CompareSource {
  key: string;
  label: string;
  path: string;
  group: string;
  note?: string;
  previewUrl?: string | null;
}

export interface ExportPackageItem {
  path: string;
  label: string;
}

export interface SingleRawSummaryView {
  status: string;
  statusLabel: string;
  statusTone: 'default' | 'success' | 'warning';
  qualityPresetLabel: string;
  modeLabel: string;
  modeSummary: string;
  runtimeProfileLabel: string;
  timingSummary: string;
  noiseReportSummary: string;
  recoveryReportSummary: string;
  artifactGuardrailSummary: string;
  artifactSuppressionSummary: string;
  safetyFallbackSummary: string;
  inputPreviewPath: string | null;
  inputPreviewUrl: string | null;
  recoveryBaselinePath: string | null;
  recoveryBaselineUrl: string | null;
  previewPath: string | null;
  previewUrl: string | null;
  noiseMapPath: string | null;
  noiseMapUrl: string | null;
  lowlightMapPath: string | null;
  lowlightMapUrl: string | null;
  sceneLinearPath: string | null;
  sceneLinearUrl: string | null;
  sceneLinearLabel: string;
  runtimeBackendLabel: string;
  metadataSourceLabel: string;
  opticalSummary: string;
  processingSummary: string;
  note: string | null;
  isCurrentSource: boolean;
}

export interface FocusHighlight {
  label: string;
  value: string;
  tone: string;
  border: string;
}

export interface QueueAttention {
  title: string;
  description: string;
  tone: string;
  border: string;
  actionLabel: string;
}

export interface OpsEventGroup {
  key: string;
  label: string;
  summary: string;
  items: StudioTelemetryEvent[];
}

export interface ToolMetaView {
  key: string;
  label: string;
  description: string;
  group: string;
}

export interface PodStatusSnapshot {
  state: 'offline' | 'booting' | 'ready' | 'busy' | 'failed' | 'stopping';
  label: string;
  tone: string;
  border: string;
  reason: string;
}
