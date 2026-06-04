const DATASET_LABELS: Record<string, string> = {
  fivek: 'MIT-Adobe FiveK 기준',
  'MIT-Adobe FiveK': 'MIT-Adobe FiveK 기준',
  acceptable_adjustments: '허용 톤 보정 기준',
  'Acceptable Photographic Tonal Adjustments': '허용 톤 보정 기준',
  ppr10k: 'PPR10K 인물 기준',
  PPR10K: 'PPR10K 인물 기준',
  mmart_ppr10k: 'MMArt-PPR10k 리터치 기준',
  'MMArt-PPR10k': 'MMArt-PPR10k 리터치 기준',
  mmart_bench: 'MMArt-Bench 비교 기준',
  'MMArt-Bench': 'MMArt-Bench 비교 기준',
  dear: 'DEAR 선호 기준',
  DEAR: 'DEAR 선호 기준',
  edithf_1m: 'EditHF-1M 편집 선호 기준',
  'EditHF-1M': 'EditHF-1M 편집 선호 기준',
  editbench: 'EditBench 국소 편집 기준',
  EditBench: 'EditBench 국소 편집 기준',
  imgedit: 'ImgEdit 편집 기준',
  ImgEdit: 'ImgEdit 편집 기준',
  personal_compare_winners: '로컬 비교 우승 기록',
};

const PRIORITY_DIMENSION_LABELS: Record<string, string> = {
  visual_quality: '시각 품질',
  'Visual Quality': '시각 품질',
  instruction_alignment: '지시 일치도',
  'Instruction Alignment': '지시 일치도',
  attribute_preservation: '속성 보존',
  'Attribute Preservation': '속성 보존',
  tone_safety: '톤 안전성',
  'Tone Safety': '톤 안전성',
  group_consistency: '세트 일관성',
  'Group Consistency': '세트 일관성',
};

const RUNTIME_BUNDLE_LABELS: Record<string, string> = {
  'DreamCatcher Local Data Lab Runtime Bundle': 'DreamCatcher 로컬 데이터 랩 런타임 묶음',
};

const RUNTIME_ARTIFACT_LABELS: Record<string, string> = {
  'Edit Evaluator Rules': '편집 평가 규칙',
  'Reference Bank Seed': '레퍼런스 뱅크 시드',
  'MMArt-Bench Seed': 'MMArt-Bench 시드',
  'MMArt-PPR10k Reference Pack': 'MMArt-PPR10k 레퍼런스 팩',
  'DEAR Rendering Seed': 'DEAR 렌더링 시드',
  'Local Compare Learning Seed': '로컬 비교 학습 시드',
};

const WORKFLOW_SOURCE_LABELS: Record<string, string> = {
  'api-export': 'API 내보내기 워크플로',
};

const SELECTION_PROFILE_LABELS: Record<string, string> = {
  dreamcatcher_local_open_2026: 'DreamCatcher 공개 기준 2026',
};

const EXECUTION_ENGINE_LABELS: Record<string, string> = {
  'comfy-workflow': 'Comfy 워크플로',
};

const BOOTSTRAP_RULE_LABELS: Record<string, string> = {
  'Start from public priors for evaluator dimensions and acceptance bands, then let local accepted outputs override them once a repeatable house style appears.':
    '평가 기준과 허용 범위는 공개 prior에서 시작하고, 반복 가능한 하우스 스타일이 잡히면 로컬 승인 결과가 그 기준을 덮어쓰도록 둡니다.',
  'Prefer openly accessible data with practical metadata such as XMP, masks, or preference pairs over giant synthetic corpora that are not yet downloadable.':
    '아직 내려받을 수 없는 거대 합성 코퍼스보다 XMP, 마스크, 선호 쌍처럼 실무 메타데이터가 있는 공개 데이터를 우선합니다.',
  'Treat announced-but-not-yet-released datasets as watchlist signals, not active defaults.':
    '발표만 되고 아직 공개되지 않은 데이터셋은 현재 기본값이 아니라 워치리스트 신호로만 다룹니다.',
};

const BOOTSTRAP_LABELS: Record<string, string> = {
  'global tone and exposure priors': '전체 톤·노출 기준',
  'white balance and color rendering anchors': '화이트 밸런스·색 재현 앵커',
  'finish-stage baseline taste before personal style takes over': '개인 스타일 전 기본 마감 취향',
  'acceptance ranges instead of single-target scoring': '단일 정답 대신 허용 범위 평가',
  'finish review guardrails for not overcorrecting tone': '과한 톤 보정을 막는 마감 가드레일',
  'evaluator tolerance bands for compare decisions': '비교 판단용 평가 허용 범위',
  'portrait skin and face retouch priors': '인물 피부·얼굴 리터치 기준',
  'human-region priority': '인물 영역 우선 기준',
  'group-level consistency for a photo set': '사진 세트 일관성 기준',
  'Lightroom/XMP-aligned edit metadata': 'Lightroom/XMP 정렬 편집 메타데이터',
  'natural-language retouch instructions': '자연어 리터치 지시',
  'Lightroom-style tool sequencing priors': 'Lightroom 스타일 도구 순서 기준',
  'before/after/reference triples for later retrieval memory': '후속 검색 기억용 before/after/reference 삼중쌍',
  'benchmark prompts for compare mode': '비교 모드용 벤치마크 프롬프트',
  'instruction richness for future evaluator prompts': '후속 평가 프롬프트용 지시 다양성',
  'pairwise rendering preference signals': '쌍대 렌더링 선호 신호',
  'compare-mode winner selection': '비교 모드 우승 후보 선택 기준',
  'finish-stage aesthetic scoring priors': '마감 단계 미감 점수 기준',
  'evaluator dimensions for edit quality': '편집 품질 평가 축',
  'instruction alignment scoring priors': '지시 일치도 점수 기준',
  'attribute preservation scoring priors': '속성 보존 점수 기준',
  'localized change containment': '국소 변경 억제 기준',
  'inpaint / object-edit evaluation prompts': '인페인트·객체 편집 평가 프롬프트',
  'failure cases for collateral damage checks': '부수 손상 점검 실패 사례',
  'task coverage for replacement and composition edits': '교체·구성 편집 작업 범위',
  'multi-turn edit trajectory priors': '다중 턴 편집 궤적 기준',
  'future workflow regression cases': '후속 워크플로 회귀 사례',
};

const COMMUNITY_TAKEAWAY_LABELS: Record<string, string> = {
  'Captured on 2026-03-26 from r/StableDiffusion: local users currently trust FLUX.2 Dev and Klein for practical edit consistency more than older Kontext-only flows.':
    '2026-03-26 r/StableDiffusion 기록: 실사용자는 예전 Kontext 단일 흐름보다 FLUX.2 Dev와 Klein 쪽을 편집 일관성 측면에서 더 신뢰합니다.',
  'Captured on 2026-03-26 from r/comfyui: users still reach for LoRA, references, and candidate filtering when identity or composition must survive multiple runs.':
    '2026-03-26 r/comfyui 기록: 인물 정체성이나 구도를 여러 번 유지해야 할 때는 여전히 LoRA, 레퍼런스, 후보 필터링을 함께 씁니다.',
  'Captured on 2026-03-26 from r/StableDiffusion: heavier edit models are still preferred when fidelity matters, even if lightweight models win on convenience.':
    '2026-03-26 r/StableDiffusion 기록: 편의성은 경량 모델이 앞서도, 충실도가 중요할 때는 여전히 무거운 편집 모델이 선호됩니다.',
  'Captured on 2026-03-26 from r/StableDiffusion: layered or tightly contained editors are favored because users still complain about angle drift and collateral color shifts.':
    '2026-03-26 r/StableDiffusion 기록: 사용자는 각도 흔들림과 부수 색 이동을 계속 지적하므로, 편집 범위를 단단히 묶는 레이어형 편집기가 더 선호됩니다.',
  'Captured on 2026-03-26 from r/StableDiffusion: Qwen remains strong for instruction following, but users still report angle and color drift; Klein is repeatedly praised for steadier realism.':
    '2026-03-26 r/StableDiffusion 기록: Qwen은 지시 이행이 강하지만 각도·색 흔들림 언급이 계속 있고, Klein은 더 안정적인 사실감으로 반복 언급됩니다.',
  'Captured on 2026-03-26 from r/comfyui: practical consistency still comes from anchor -> generate -> evaluate -> keep, not from assuming a single run will stay stable forever.':
    '2026-03-26 r/comfyui 기록: 실무 일관성은 여전히 기준본 고정 -> 생성 -> 평가 -> 유지 흐름에서 나오며, 한 번의 실행이 끝까지 안정적일 것이라 가정하지 않습니다.',
  'Captured on 2026-03-26 from r/comfyui: validation layers are valued as a safety net, but users reject brute-force filtering if the candidate distribution is too wide.':
    '2026-03-26 r/comfyui 기록: 검증 레이어는 안전장치로 가치가 있지만, 후보 분포가 너무 넓으면 무차별 필터링은 거부됩니다.',
  'Captured on 2026-03-26 from r/comfyui: the strongest workflow advice is still to save anchors, compare candidates, and continue only from winners.':
    '2026-03-26 r/comfyui 기록: 가장 강한 워크플로 조언은 여전히 기준본을 저장하고, 후보를 비교한 뒤, 우승 후보에서만 다음 단계로 가는 것입니다.',
};

const ARTIFACT_SUMMARY_LABELS: Record<string, string> = {
  'food 50, landscape 58, portrait 102, street 43': '음식 50, 풍경 58, 인물 102, 거리 43',
  'exp -0.40..1.15 | hl -77..-41': '노출 -0.40..1.15 | 하이라이트 -77..-41',
  'exp -0.50..1.17 | temp 3650..5979': '노출 -0.50..1.17 | 색온도 3650..5979',
};

function replaceKnownLabels(value: string, replacements: Record<string, string>): string {
  return Object.entries(replacements)
    .sort((a, b) => b[0].length - a[0].length)
    .reduce((current, [source, target]) => current.split(source).join(target), value);
}

export function localizeDatasetLabel(value: string): string {
  return DATASET_LABELS[value] ?? value;
}

export function localizePriorityDimension(value: string): string {
  return PRIORITY_DIMENSION_LABELS[value] ?? value;
}

export function localizeRuntimeBundleLabel(value: string): string {
  return RUNTIME_BUNDLE_LABELS[value] ?? value;
}

export function localizeRuntimeArtifactLabel(value: string): string {
  return RUNTIME_ARTIFACT_LABELS[value] ?? value;
}

export function localizeWorkflowSource(value: string): string {
  return WORKFLOW_SOURCE_LABELS[value] ?? value;
}

export function localizeSelectionProfile(value: string): string {
  return SELECTION_PROFILE_LABELS[value] ?? value;
}

export function localizeExecutionEngine(value: string): string {
  return EXECUTION_ENGINE_LABELS[value] ?? value;
}

export function localizeBootstrapRule(value: string): string {
  return BOOTSTRAP_RULE_LABELS[value] ?? value;
}

export function localizeBootstrapLabel(value: string): string {
  return BOOTSTRAP_LABELS[value] ?? value;
}

export function localizeCommunityTakeaway(value: string): string {
  return COMMUNITY_TAKEAWAY_LABELS[value] ?? value;
}

export function localizeArtifactSummaryText(value: string): string {
  return ARTIFACT_SUMMARY_LABELS[value] ?? value;
}

export function summarizeWorkflowPath(value: string): string {
  const normalized = value.split(/[\\/]/).filter(Boolean);
  return normalized[normalized.length - 1] ?? value;
}

export function localizePriorFreeformText(value: string): string {
  const localizedDatasetLabels = replaceKnownLabels(value, DATASET_LABELS);
  return replaceKnownLabels(localizedDatasetLabels, PRIORITY_DIMENSION_LABELS);
}
