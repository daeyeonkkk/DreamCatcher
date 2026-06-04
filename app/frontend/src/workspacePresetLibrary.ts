import type { WorkspacePreferences } from './workspacePreferences';

const STORAGE_KEY = 'dreamcatcher.workspace.presets.v1';

export interface WorkspacePreset extends WorkspacePreferences {
  id: string;
  name: string;
  createdAt: string;
}

function readStorage(): WorkspacePreset[] {
  if (typeof window === 'undefined') {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const payload = JSON.parse(raw) as unknown;
    return Array.isArray(payload) ? payload.filter((item): item is WorkspacePreset => Boolean(item && typeof item === 'object')) : [];
  } catch {
    return [];
  }
}

export function loadWorkspacePresets(): WorkspacePreset[] {
  return readStorage();
}

export function saveWorkspacePresets(presets: WorkspacePreset[]): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
  } catch {
    // Ignore storage failures so the studio keeps working.
  }
}
