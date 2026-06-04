import type { CameraProfile, EntryPreference, QualityPreset, RawRestorationGoal, SingleRawModePreference, ToolKey } from './studioApi';

const STORAGE_KEY = 'dreamcatcher.workspace.preferences.v1';

const toolKeys = ['removeBg', 'replaceBg', 'relight', 'replaceObject', 'expandCanvas', 'retouch', 'enhance', 'finish', 'compare'] as const;
const workspaceModes = ['standard', 'advanced'] as const;
const entryPreferences = ['auto', 'rawprep', 'direct_edit'] as const;
const cameraProfiles = ['auto', 'tz99', 'eos_r8', 'sony_a7c_ii', 'nikon_zf', 'fuji_x_s20'] as const;
const qualityPresets = ['safe', 'balanced'] as const;
const singleRawModePreferences = ['auto', 'fast', 'hq', 'safe'] as const;
const rawRestorationGoals = ['truth_preserving', 'aggressive_restore'] as const;

export interface WorkspaceSliderState {
  strength: number;
  realism: number;
  preserveTexture: number;
}

export interface WorkspacePreferences {
  activeTool: ToolKey;
  workspaceMode: 'standard' | 'advanced';
  entryPreference: EntryPreference;
  cameraProfile: CameraProfile;
  qualityPreset: QualityPreset;
  singleRawModePreference: SingleRawModePreference;
  rawRestorationGoal: RawRestorationGoal;
  prompt: string;
  sliders: WorkspaceSliderState;
}

export const defaultWorkspacePreferences = (): WorkspacePreferences => ({
  activeTool: 'retouch',
  workspaceMode: 'standard',
  entryPreference: 'auto',
  cameraProfile: 'auto',
  qualityPreset: 'balanced',
  singleRawModePreference: 'auto',
  rawRestorationGoal: 'truth_preserving',
  prompt: '',
  sliders: {
    strength: 58,
    realism: 72,
    preserveTexture: 84,
  },
});

function readStorage(): Partial<WorkspacePreferences> | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as Partial<WorkspacePreferences>;
  } catch {
    return null;
  }
}

function pickEnumValue<T extends string>(value: unknown, allowedValues: readonly T[], fallback: T): T {
  return typeof value === 'string' && allowedValues.includes(value as T) ? (value as T) : fallback;
}

function clampSlider(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value)
    ? Math.max(0, Math.min(100, Math.round(value)))
    : fallback;
}

export function loadWorkspacePreferences(): WorkspacePreferences {
  const defaults = defaultWorkspacePreferences();
  const stored = readStorage();
  if (!stored) {
    return defaults;
  }

  const storedSliders = (stored.sliders ?? {}) as Partial<WorkspaceSliderState>;
  return {
    activeTool: pickEnumValue(stored.activeTool, toolKeys, defaults.activeTool),
    workspaceMode: pickEnumValue(stored.workspaceMode, workspaceModes, defaults.workspaceMode),
    entryPreference: pickEnumValue(stored.entryPreference, entryPreferences, defaults.entryPreference),
    cameraProfile: pickEnumValue(stored.cameraProfile, cameraProfiles, defaults.cameraProfile),
    qualityPreset: pickEnumValue(stored.qualityPreset, qualityPresets, defaults.qualityPreset),
    singleRawModePreference: pickEnumValue(stored.singleRawModePreference, singleRawModePreferences, defaults.singleRawModePreference),
    rawRestorationGoal: pickEnumValue(stored.rawRestorationGoal, rawRestorationGoals, defaults.rawRestorationGoal),
    prompt: typeof stored.prompt === 'string' ? stored.prompt : defaults.prompt,
    sliders: {
      strength: clampSlider(storedSliders.strength, defaults.sliders.strength),
      realism: clampSlider(storedSliders.realism, defaults.sliders.realism),
      preserveTexture: clampSlider(storedSliders.preserveTexture, defaults.sliders.preserveTexture),
    },
  };
}

export function saveWorkspacePreferences(preferences: WorkspacePreferences): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // Ignore storage failures so the studio keeps working in private mode or strict browsers.
  }
}
