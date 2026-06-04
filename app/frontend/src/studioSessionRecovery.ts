const STORAGE_KEY = 'dreamcatcher.session.recovery.v1';

export interface StudioSavedVersionSnapshot {
  id: string;
  label: string;
  path: string;
  createdAt: string;
}

export interface StudioSessionRecoverySnapshot {
  sessionId: string;
  outputRoot: string;
  rawprepJobId: string | null;
  studioJobId: string | null;
  directPath: string | null;
  comparePrimary: string | null;
  compareCandidate: string | null;
  sourceHistory: string[];
  sourceHistoryIndex: number;
  savedVersions: StudioSavedVersionSnapshot[];
}

function readStorage(): Partial<StudioSessionRecoverySnapshot> | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as Partial<StudioSessionRecoverySnapshot>;
  } catch {
    return null;
  }
}

function pickNullableString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function pickStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function pickSavedVersions(value: unknown): StudioSavedVersionSnapshot[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return null;
      }
      const candidate = item as Partial<StudioSavedVersionSnapshot>;
      if (
        typeof candidate.id !== 'string'
        || typeof candidate.label !== 'string'
        || typeof candidate.path !== 'string'
        || typeof candidate.createdAt !== 'string'
      ) {
        return null;
      }
      return {
        id: candidate.id,
        label: candidate.label,
        path: candidate.path,
        createdAt: candidate.createdAt,
      };
    })
    .filter((item): item is StudioSavedVersionSnapshot => item !== null);
}

export function loadStudioSessionRecovery(): StudioSessionRecoverySnapshot | null {
  const stored = readStorage();
  if (!stored || typeof stored.sessionId !== 'string' || typeof stored.outputRoot !== 'string') {
    return null;
  }
  return {
    sessionId: stored.sessionId,
    outputRoot: stored.outputRoot,
    rawprepJobId: pickNullableString(stored.rawprepJobId),
    studioJobId: pickNullableString(stored.studioJobId),
    directPath: pickNullableString(stored.directPath),
    comparePrimary: pickNullableString(stored.comparePrimary),
    compareCandidate: pickNullableString(stored.compareCandidate),
    sourceHistory: pickStringArray(stored.sourceHistory),
    sourceHistoryIndex: typeof stored.sourceHistoryIndex === 'number' ? stored.sourceHistoryIndex : -1,
    savedVersions: pickSavedVersions(stored.savedVersions),
  };
}

export function saveStudioSessionRecovery(snapshot: StudioSessionRecoverySnapshot): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // Ignore storage failures so recovery stays best-effort.
  }
}

export function clearStudioSessionRecovery(): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage failures so the studio keeps working.
  }
}
