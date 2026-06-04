const STORAGE_KEY = 'dreamcatcher.delivery.presets.v1';

export type DeliveryPresetKey =
  | 'review_pack'
  | 'client_delivery'
  | 'master_archive'
  | 'proofing_sheet'
  | 'print_master'
  | 'client_review_portal';
export type DeliveryPresetScope = 'session' | 'batch' | 'both';
export type DeliveryPresetStage = 'review' | 'finish' | 'archive';

export interface DeliveryPresetDescriptor {
  profileId: string;
  label: string;
  stage: DeliveryPresetStage;
  masterSource: 'scene_linear' | 'raster' | 'mixed';
  description: string;
}

export interface DeliveryPresetProfile {
  id: string;
  name: string;
  preset: DeliveryPresetKey;
  scope: DeliveryPresetScope;
  createdAt: string;
  profileId: string;
  profileLabel: string;
  stage: DeliveryPresetStage;
  masterSource: 'scene_linear' | 'raster' | 'mixed';
  description: string;
}

const LEGACY_DELIVERY_PRESET_DESCRIPTORS: Record<DeliveryPresetKey, { label: string; description: string }> = {
  review_pack: {
    label: '검토 묶음',
    description: '검토용 비교 묶음과 승인 메모를 저장합니다.',
  },
  client_delivery: {
    label: '고객 전달본',
    description: '최종 결과와 가장 안전한 장면 선형 작업 마스터를 함께 전달합니다.',
  },
  master_archive: {
    label: '마스터 보관본',
    description: '장기 보관용으로 장면 선형 마스터, 미리보기, 진단, 최종 결과를 함께 묶습니다.',
  },
  proofing_sheet: {
    label: '교정 시트',
    description: '미리보기, 최종 결과, 검토 메모를 함께 저장합니다.',
  },
  print_master: {
    label: '출력 마스터',
    description: '출력용 최종 결과와 가장 안전한 장면 선형 마스터, 작업 소스를 함께 전달합니다.',
  },
  client_review_portal: {
    label: '고객 검토 포털',
    description: '고객 검토 포털에 맞춘 미리보기, 최신 결과, 고객 메타데이터 묶음을 만듭니다.',
  },
};

const DELIVERY_PRESET_DESCRIPTORS: Record<DeliveryPresetKey, DeliveryPresetDescriptor> = {
  review_pack: {
    profileId: 'review_contact_sheet_v1',
    label: '검토 묶음',
    stage: 'review',
    masterSource: 'raster',
    description: '검토용 미리보기, 비교 결과, 승인 메모를 묶습니다.',
  },
  client_delivery: {
    profileId: 'finish_delivery_scene_linear_v2',
    label: '고객 전달본',
    stage: 'finish',
    masterSource: 'scene_linear',
    description: '최종 결과와 가장 안전한 장면 선형 작업 마스터를 함께 전달합니다.',
  },
  master_archive: {
    profileId: 'scene_linear_archive_v2',
    label: '마스터 보관본',
    stage: 'archive',
    masterSource: 'mixed',
    description: '장면 선형 마스터, 미리보기, 진단 산출물, 최종 결과를 장기 보관용으로 남깁니다.',
  },
  proofing_sheet: {
    profileId: 'proofing_sheet_v1',
    label: '교정 시트',
    stage: 'review',
    masterSource: 'raster',
    description: '미리보기, 최종 결과, 검토 메모를 함께 저장합니다.',
  },
  print_master: {
    profileId: 'print_master_v2',
    label: '출력 마스터',
    stage: 'finish',
    masterSource: 'scene_linear',
    description: '출력용 최종 결과와 가장 안전한 장면 선형 마스터, 작업 소스를 함께 넘깁니다.',
  },
  client_review_portal: {
    profileId: 'client_review_portal_v1',
    label: '고객 검토 포털',
    stage: 'review',
    masterSource: 'mixed',
    description: '고객 검토 포털에 맞춘 미리보기, 최신 결과, 고객 메타데이터 묶음을 만듭니다.',
  },
};

function normalizePresetText(value: unknown, legacy: string, canonical: string): string {
  if (typeof value !== 'string' || !value.trim()) {
    return canonical;
  }
  const trimmed = value.trim();
  return trimmed === legacy ? canonical : trimmed;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object';
}

function normalizePresetKey(value: unknown): DeliveryPresetKey | null {
  if (
    value === 'review_pack'
    || value === 'client_delivery'
    || value === 'master_archive'
    || value === 'proofing_sheet'
    || value === 'print_master'
    || value === 'client_review_portal'
  ) {
    return value;
  }
  return null;
}

function normalizePresetScope(value: unknown): DeliveryPresetScope {
  if (value === 'batch' || value === 'both') {
    return value;
  }
  return 'session';
}

function normalizeDeliveryPresetProfile(
  payload: unknown,
  fallbackName: string,
): DeliveryPresetProfile | null {
  if (!isRecord(payload)) {
    return null;
  }
  const preset = normalizePresetKey(payload.preset);
  if (!preset) {
    return null;
  }
  const name = typeof payload.name === 'string' && payload.name.trim()
    ? payload.name.trim()
    : fallbackName;
  const descriptor = DELIVERY_PRESET_DESCRIPTORS[preset];
  const legacyDescriptor = LEGACY_DELIVERY_PRESET_DESCRIPTORS[preset];
  return {
    id: typeof payload.id === 'string' && payload.id.trim()
      ? payload.id
      : `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name,
    preset,
    scope: normalizePresetScope(payload.scope),
    createdAt: typeof payload.createdAt === 'string' && payload.createdAt
      ? payload.createdAt
      : new Date().toISOString(),
    profileId: typeof payload.profileId === 'string' && payload.profileId.trim()
      ? payload.profileId
      : descriptor.profileId,
    profileLabel: normalizePresetText(payload.profileLabel, legacyDescriptor.label, descriptor.label),
    stage: payload.stage === 'review' || payload.stage === 'archive'
      ? payload.stage
      : descriptor.stage,
    masterSource: payload.masterSource === 'scene_linear' || payload.masterSource === 'raster' || payload.masterSource === 'mixed'
      ? payload.masterSource
      : payload.masterSource === 'raw_dng'
        ? 'scene_linear'
        : descriptor.masterSource,
    description: normalizePresetText(payload.description, legacyDescriptor.description, descriptor.description),
  };
}

export function deserializeDeliveryPresetProfiles(payload: unknown): DeliveryPresetProfile[] {
  const items = Array.isArray(payload) ? payload : [payload];
  const presets = items
    .map((item, index) => normalizeDeliveryPresetProfile(item, `가져온 납품 사전 설정 ${index + 1}`))
    .filter((item): item is DeliveryPresetProfile => item !== null);
  const seen = new Set<string>();
  return presets.filter((item) => {
    if (seen.has(item.id)) {
      return false;
    }
    seen.add(item.id);
    return true;
  });
}

export function describeDeliveryPreset(preset: DeliveryPresetKey): DeliveryPresetDescriptor {
  return DELIVERY_PRESET_DESCRIPTORS[preset];
}

function readStorage(): DeliveryPresetProfile[] {
  if (typeof window === 'undefined') {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    return deserializeDeliveryPresetProfiles(JSON.parse(raw) as unknown);
  } catch {
    return [];
  }
}

export function loadDeliveryPresetProfiles(): DeliveryPresetProfile[] {
  return readStorage();
}

export function saveDeliveryPresetProfiles(presets: DeliveryPresetProfile[]): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
  } catch {
    // Ignore storage failures so the studio keeps working.
  }
}
