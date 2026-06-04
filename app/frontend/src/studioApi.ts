export type ToolKey =
  | 'removeBg'
  | 'replaceBg'
  | 'relight'
  | 'replaceObject'
  | 'expandCanvas'
  | 'retouch'
  | 'enhance'
  | 'finish'
  | 'compare';

export type EntryPreference = 'auto' | 'rawprep' | 'direct_edit';
export type CameraProfile = 'auto' | 'tz99' | 'eos_r8' | 'sony_a7c_ii' | 'nikon_zf' | 'fuji_x_s20';
export type QualityPreset = 'safe' | 'balanced';
export type SingleRawModePreference = 'auto' | 'fast' | 'hq' | 'safe';
export type SingleRawExecutionMode = 'fast' | 'hq' | 'safe';
export type IntakeEntryMode = 'rawprep_bracket' | 'direct_edit_raw' | 'direct_edit_image';
export type RawprepReferencePolicy = 'auto' | 'first' | 'middle' | 'last';
export type RawRestorationGoal = 'truth_preserving' | 'aggressive_restore';
export type RawRestorationTone = 'default' | 'accent' | 'success' | 'warning';

export interface RawRestorationGoalOption {
  id: RawRestorationGoal;
  label: string;
  summary: string;
  approval?: string | null;
  risk?: string | null;
  delivery_default: boolean;
  requires_human_review: boolean;
  tone: RawRestorationTone;
  review_gates: string[];
}

export interface RawRestorationPolicyPayload {
  schema_version: string;
  contract_id: string;
  baseline_backend: string;
  studio_official_inputs: string[];
  accepted_frame_counts: number[];
  nine_frame_status?: string | null;
  default_goal: RawRestorationGoal;
  options: RawRestorationGoalOption[];
  source_manifest?: string | null;
}

export interface StudioAsset {
  source_path: string;
  staged_path: string;
  file_name: string;
  suffix: string;
  kind: 'raw' | 'image' | 'unknown';
}

export interface RawprepRequestPayload {
  session_id?: string;
  output_root: string;
  camera_profile?: string;
  quality_preset: QualityPreset;
  restoration_goal?: RawRestorationGoal;
  groups: Array<{ bracket_id: string; raw_files: string[]; reference_policy?: RawprepReferencePolicy }>;
}

export interface SingleRawModePolicy {
  [key: string]: unknown;
  requested_quality_preset: QualityPreset;
  requested_mode: SingleRawExecutionMode;
  resolved_mode: SingleRawExecutionMode;
  delivery_intent: 'direct_edit' | 'guarded_preview' | 'maximum_recovery';
  decode_priority: 'latency_first' | 'guardrail_first' | 'quality_first';
  denoise_strategy: 'preview_first' | 'conservative_holdout' | 'maximum_recovery_pending';
  artifact_discipline: 'minimal' | 'guarded' | 'extended';
  summary: string;
  notes: string[];
}

export interface SingleRawPlanPayload {
  [key: string]: unknown;
  status: string;
  quality_preset?: QualityPreset;
  mode_preference?: SingleRawModePreference;
  requested_mode?: SingleRawExecutionMode;
  resolved_mode?: SingleRawExecutionMode;
  mode_policy?: SingleRawModePolicy | null;
  metadata_source?: string;
  materialization_status?: string;
  preview_source_path?: string | null;
  materialized_input_preview_path?: string | null;
  materialized_recovery_baseline_path?: string | null;
  materialized_preview_path?: string | null;
  materialized_noise_map_path?: string | null;
  materialized_lowlight_map_path?: string | null;
  materialized_timing_report?: Record<string, unknown> | null;
  decode?: Record<string, unknown> | null;
  scene_linear?: Record<string, unknown> | null;
  lens_correction?: Record<string, unknown> | null;
}

export interface IntakePlan {
  session_id: string;
  session_root: string;
  entry_mode: IntakeEntryMode;
  alternate_modes: string[];
  staged_assets: StudioAsset[];
  editable_asset_path: string | null;
  single_raw_plan?: SingleRawPlanPayload | null;
  dreamisp_plan?: Record<string, unknown> | null;
  rawprep_request: RawprepRequestPayload | null;
  notes: string[];
}

export interface SessionCatalogSummary {
  rating: number;
  pick_status: 'unreviewed' | 'selected' | 'rejected' | 'hold';
  review_status: 'intake' | 'culling' | 'proofing' | 'client_review' | 'print_ready' | 'delivered' | 'archived';
  color_tag?: string | null;
  keywords: string[];
  notes_preview?: string | null;
  proofing_profile?: string | null;
  print_profile?: string | null;
  client_collection?: string | null;
  updated_at?: string | null;
}

export interface RecentStudioSessionSummary {
  session_id: string;
  output_root: string;
  session_root: string;
  entry_mode: IntakeEntryMode;
  staged_asset_count: number;
  primary_file_name: string | null;
  editable_asset_path: string | null;
  source_preview_path?: string | null;
  result_preview_path?: string | null;
  rawprep_job_id?: string | null;
  rawprep_status?: string | null;
  studio_job_id?: string | null;
  studio_status?: string | null;
  studio_current_step?: string | null;
  studio_tool?: string | null;
  prompt_preview?: string | null;
  catalog: SessionCatalogSummary;
  last_updated_at: string;
}

export interface RecentStudioSessionsResponse {
  items: RecentStudioSessionSummary[];
}

export interface StudioOpsJobSummary {
  job_id: string;
  session_id: string;
  job_type: 'rawprep' | 'studio';
  output_root: string;
  session_root?: string | null;
  tool?: string | null;
  status: string;
  current_step?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  output_count: number;
  error?: string | null;
}

export type StudioTelemetrySource =
  | 'queue'
  | 'studio'
  | 'rawprep'
  | 'export'
  | 'ops'
  | 'quality_automation'
  | 'quality_tuning';

export interface StudioTelemetryEvent {
  event_id: string;
  occurred_at: string;
  output_root: string;
  source: StudioTelemetrySource;
  event_type: string;
  task_type?: string | null;
  job_id?: string | null;
  session_id?: string | null;
  status?: string | null;
  detail?: string | null;
  metadata?: Record<string, unknown>;
}

export interface StudioOpsEventsResponse {
  items: StudioTelemetryEvent[];
}

export interface StudioDeadLetterSummary {
  queue_id: string;
  task_type: 'rawprep' | 'studio';
  job_id: string;
  session_id: string;
  output_root: string;
  status: string;
  current_status?: string | null;
  tool?: string | null;
  current_step?: string | null;
  attempts: number;
  max_attempts: number;
  finished_at?: string | null;
  last_error?: string | null;
  history_path: string;
  investigation_status?: 'open' | 'acknowledged' | 'assigned' | 'resolved' | 'muted';
  assigned_to?: string | null;
  acknowledged_at?: string | null;
  note?: string | null;
  investigation_updated_at?: string | null;
}

export interface StudioOpsRootSummary {
  output_root: string;
  total_sessions: number;
  pending_queue: number;
  delayed_queue: number;
  running_queue: number;
  active_queue_workers: number;
  worker_mode?: 'embedded' | 'external' | null;
  worker_last_seen_at?: string | null;
  worker_stop_requested_at?: string | null;
  dead_letter_count: number;
}

export interface StudioWorkerControlStatus {
  output_root: string;
  running: boolean;
  mode?: 'embedded' | 'external' | null;
  started_at?: string | null;
  last_seen_at?: string | null;
  pid?: number | null;
  processing?: boolean;
  stop_requested_at?: string | null;
  stop_requested_reason?: string | null;
}

export interface StudioProviderCheckpointSavedVersion {
  id: string;
  label: string;
  path: string;
  created_at: string;
}

export interface StudioProviderCheckpointSessionSnapshot {
  session_id: string;
  output_root: string;
  rawprep_job_id?: string | null;
  studio_job_id?: string | null;
  direct_path?: string | null;
  compare_primary?: string | null;
  compare_candidate?: string | null;
  source_history: string[];
  source_history_index: number;
  saved_versions: StudioProviderCheckpointSavedVersion[];
}

export interface StudioProviderCheckpointActiveJob {
  task_type: 'rawprep' | 'studio';
  job_id: string;
  session_id: string;
  output_root: string;
  status: string;
  current_step?: string | null;
}

export interface StudioProviderSummary {
  configured: boolean;
  provider: 'runpod';
  pod_id?: string | null;
  control_state?: 'unconfigured' | 'offline' | 'starting' | 'running' | 'stopping' | 'stopped' | 'error';
  desired_status?: 'RUNNING' | 'EXITED' | 'TERMINATED' | 'UNKNOWN';
  last_status_change?: string | null;
  public_ip?: string | null;
  host_id?: string | null;
  machine_id?: string | null;
  allocation_state?: string | null;
  migration_state?: string | null;
  pod_uptime_seconds?: number | null;
  gpu_count?: number | null;
  port_mappings?: Record<string, number>;
  backend_url?: string | null;
  frontend_url?: string | null;
  network_volume_attached?: boolean;
  supports_stop?: boolean;
  reason?: string | null;
  checkpoint_pending_resume?: boolean;
  checkpoint_id?: string | null;
  checkpoint_updated_at?: string | null;
  checkpoint_reason?: string | null;
  checkpoint_session_id?: string | null;
  checkpoint_output_roots: string[];
  checkpoint_active_jobs: StudioProviderCheckpointActiveJob[];
  checkpoint_session_snapshot?: StudioProviderCheckpointSessionSnapshot | null;
  lifecycle_hints: string[];
}

export interface StudioOpsSummary {
  output_root: string;
  total_sessions: number;
  active_jobs: number;
  queued_jobs: number;
  failed_jobs: number;
  completed_jobs: number;
  exported_packages: number;
  saved_exports: number;
  pending_queue: number;
  delayed_queue: number;
  running_queue: number;
  active_queue_workers: number;
  worker_mode?: 'embedded' | 'external' | null;
  worker_started_at?: string | null;
  worker_last_seen_at?: string | null;
  worker_pid?: number | null;
  worker_processing?: boolean;
  worker_stop_requested_at?: string | null;
  worker_stop_requested_reason?: string | null;
  next_retry_at?: string | null;
  pod_state?: 'offline' | 'booting' | 'ready' | 'busy' | 'failed' | 'stopping';
  pod_state_reason?: string | null;
  ai_ready?: boolean;
  comfy_reason?: string | null;
  runtime_started_at?: string | null;
  runtime_uptime_seconds?: number | null;
  idle_timeout_seconds?: number | null;
  idle_shutdown_at?: string | null;
  last_success_at?: string | null;
  last_failure_at?: string | null;
  last_failure_reason?: string | null;
  resume_session_id?: string | null;
  provider: StudioProviderSummary;
  dead_letter_count: number;
  dead_letters: StudioDeadLetterSummary[];
  recent_jobs: StudioOpsJobSummary[];
  recent_events: StudioTelemetryEvent[];
}

export interface StudioOpsRootsResponse {
  items: StudioOpsRootSummary[];
}

export interface StudioWorkerControlResponse {
  items: StudioWorkerControlStatus[];
}

export interface StudioDeadLetterRetryResponse {
  count: number;
  queued: number;
  results: Array<{
    job_id: string;
    task_type: 'rawprep' | 'studio';
    output_root: string;
    status: string;
    detail?: string | null;
  }>;
}

export interface RawprepReferenceSelectionEntry {
  raw_path: string;
  preview_path: string;
  metadata_index: number;
  total_score: number;
  diagnostics?: {
    highlight_watch_path?: string | null;
    shadow_watch_path?: string | null;
    metrics?: {
      highlight_coverage?: number;
      highlight_preservation?: number;
      highlight_detail_focus?: number;
      shadow_coverage?: number;
      shadow_visibility?: number;
      shadow_noise_risk?: number;
      shadow_safety?: number;
    };
    summary?: {
      highlight?: string | null;
      shadow?: string | null;
    };
  };
  score_components?: {
    edge_component?: number;
    entropy_component?: number;
    exposure_component?: number;
    luma_component?: number;
    clip_component?: number;
    shadow_component?: number;
    edge_chroma_component?: number;
    position_component?: number;
    stability_component?: number;
    highlight_region_component?: number;
    shadow_region_component?: number;
    motion_region_component?: number;
    region_stability_component?: number;
    highlight_watch_component?: number;
    shadow_watch_component?: number;
    diagnostic_stability_component?: number;
  };
}

export interface RawprepCandidateScoreEntry {
  label: string;
  path: string;
  total_score: number;
  requires_review?: boolean;
  delivery_default?: boolean;
  risk_tags?: string[];
  review_gate?: string;
  score_components?: {
    detail_component?: number;
    clip_component?: number;
    shadow_component?: number;
    contrast_component?: number;
    highlight_component?: number;
    edge_chroma_component?: number;
    grain_component?: number;
    highlight_region_component?: number;
    shadow_region_component?: number;
    motion_region_component?: number;
    hdr_rescue_bonus?: number;
    coverage_bonus?: number;
    coverage_penalty?: number;
    grain_penalty?: number;
    region_bonus?: number;
    motion_region_penalty?: number;
    alignment_guard_bonus?: number;
    alignment_guard_penalty?: number;
  };
}

export interface RawprepRuntimeOverrideGroup {
  [key: string]: number;
}

export interface RawprepRuntimeBenchmarkGuidanceProfile {
  matched_entry_count?: number;
  group_scales?: Record<string, number>;
  effect_counts?: Record<string, number>;
}

export interface RawprepRuntimeOverrides {
  camera?: Record<string, RawprepRuntimeOverrideGroup>;
  lens?: Record<string, RawprepRuntimeOverrideGroup>;
  combined?: Record<string, RawprepRuntimeOverrideGroup>;
  notes?: string[];
  benchmark_guidance?: {
    camera?: RawprepRuntimeBenchmarkGuidanceProfile | null;
    lens?: RawprepRuntimeBenchmarkGuidanceProfile | null;
    combined_effect_counts?: Record<string, number>;
    combined_group_scales?: Record<string, number>;
  } | null;
}

export interface RawprepDreamispHandoff {
  source_stage?: 'single_raw' | 'tri_raw';
  source_item_key?: string;
  materialization_status?: string;
  plan_path?: string;
  render_state_path?: string;
  report_path?: string;
  scene_linear_path?: string | null;
  scene_linear_exists?: boolean;
  preview_path?: string | null;
  preview_exists?: boolean;
  render_preview_path?: string | null;
  render_preview_exists?: boolean;
  recommended_editable_source_path?: string | null;
  render_source_kind?: 'scene_linear' | 'preview_proxy' | null;
  render_backend?: string | null;
  handoff_ready?: boolean;
}

export interface RawprepGroupReport {
  reference_selection?: RawprepReferenceSelectionEntry[];
  candidate_scores?: RawprepCandidateScoreEntry[];
  recommended_artifact?: string;
  dreamisp_handoff?: RawprepDreamispHandoff;
  merge_backend?: string;
  restoration_goal?: RawRestorationGoal;
  restoration_goal_policy?: {
    goal?: RawRestorationGoal;
    label?: string;
    delivery_default?: boolean;
    candidate_enabled?: boolean;
    candidate_path?: string | null;
    approval_required?: boolean;
    requires_qwen_metric_golden_human_review?: boolean;
    risk?: string;
    review_gates?: string[];
  };
  effective_camera_profile?: string;
  fallback_reason?: string | null;
  selected_single_raw?: string;
  requested_reference_policy?: RawprepReferencePolicy;
  selected_single_index?: number | null;
  capture_summary?: {
    ev_span?: number | null;
    ev_spacing_quality?: string | null;
    anchor_index_hint?: number | null;
    order_quality?: string | null;
    capture_warnings?: string[];
  };
  bracket_coverage?: {
    coverage_quality?: string | null;
    hdr_worth_it?: boolean;
    scene_class?: string | null;
    scene_traits?: string[];
    highlight_headroom_fraction?: number | null;
    shadow_headroom_luma?: number | null;
    coverage_notes?: string[];
  };
  motion_overlay_path?: string | null;
  motion_overlay_summary?: string | null;
  motion_overlay_coverage?: number | null;
  alignment_summary?: {
    backend?: string | null;
    reference_frame_index?: number | null;
    max_offset?: number | null;
    has_nonzero_offsets?: boolean;
    piecewise_local_alignment?: {
      active_frame_count?: number | null;
      max_local_offset?: number | null;
    };
    frames?: Array<{
      frame_index?: number | null;
      dx?: number | null;
      dy?: number | null;
      offset_magnitude?: number | null;
      confidence?: number | null;
      is_reference?: boolean;
      local_alignment?: {
        enabled?: boolean | null;
        active_tile_count?: number | null;
        max_local_offset?: number | null;
      };
    }>;
  };
  alignment_guard_summary?: {
    severity?: string | null;
    guarded_merge_required?: boolean;
    pressure_score?: number | null;
    primary_signal?: string | null;
    active_frame_count?: number | null;
    max_local_offset?: number | null;
    max_global_offset?: number | null;
    vector_mean_magnitude?: number | null;
    vector_hotspot_coverage?: number | null;
    vector_watch_coverage?: number | null;
    residual_mean?: number | null;
    residual_watch_coverage?: number | null;
    residual_hotspot_coverage?: number | null;
  };
  alignment_refinement_summary?: {
    backend?: string | null;
    learned_backend_available?: boolean;
    consumes_alignment_vector_field?: boolean;
    consumes_alignment_residual?: boolean;
    consumes_confidence_map?: boolean;
    guides_guarded_fusion?: boolean;
    mean_refinement_weight?: number | null;
    hotspot_coverage?: number | null;
    guarded_holdout_coverage?: number | null;
    vector_peak_watch_coverage?: number | null;
    residual_watch_coverage?: number | null;
    merge_strength_suppression_mean?: number | null;
  };
  confidence_summary?: {
    mean_confidence?: number | null;
    high_confidence_coverage?: number | null;
    ghost_risk_coverage?: number | null;
    reference_holdout_coverage?: number | null;
    merge_support_coverage?: number | null;
  };
  joint_denoise_summary?: {
    strategy?: string | null;
    mean_suppression?: number | null;
    strong_suppression_coverage?: number | null;
    shadow_weighted_coverage?: number | null;
    low_detail_coverage?: number | null;
    frame_noise_biases?: number[];
    quietest_frame_index?: number | null;
  };
  deghost_summary?: {
    strategy?: string | null;
    holdout_coverage?: number | null;
    merge_coverage?: number | null;
    ghost_risk_coverage?: number | null;
    motion_coverage?: number | null;
    selected_preview_label?: string | null;
    alignment_holdout_coverage?: number | null;
    alignment_refinement_backend?: string | null;
  };
  hdr_summary?: {
    strategy?: string | null;
    ev_span?: number | null;
    hdr_gain_coverage?: number | null;
    highlight_recovery_coverage?: number | null;
    shadow_lift_coverage?: number | null;
    selected_preview_label?: string | null;
    hdr_worth_it?: boolean;
  };
  fallback_strategy?: {
    selected_action?: string | null;
    selected_reason?: string | null;
    triggered_rules?: string[];
  };
  confidence_map_path?: string | null;
  aggressive_restore_candidate_path?: string | null;
  confidence_preview_path?: string | null;
  ghost_risk_map_path?: string | null;
  highlight_map_path?: string | null;
  shadow_map_path?: string | null;
  deghost_mask_path?: string | null;
  hdr_gain_map_path?: string | null;
  noise_suppression_map_path?: string | null;
  alignment_offset_map_path?: string | null;
  alignment_residual_map_path?: string | null;
  alignment_refinement_map_path?: string | null;
  runtime_overrides?: RawprepRuntimeOverrides;
}

export interface RawprepJobRecord {
  job_id: string;
  session_id: string;
  status: string;
  current_step?: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  missing_tools?: string[];
  group_reports?: RawprepGroupReport[];
  cancel_requested_at?: string | null;
  cancelled_at?: string | null;
}

export interface RawprepArtifactRecord {
  bracket_id: string;
  kind: string;
  path: string;
  exists?: boolean;
  required?: boolean;
  notes?: string | null;
}

export interface RawprepArtifactResponse {
  job_id: string;
  session_id: string;
  status: string;
  artifacts: RawprepArtifactRecord[];
}

export interface RawprepHealthPayload {
  ok: boolean;
  message?: string;
  engine_readiness?: Record<string, { missing_tools: string[] }>;
}

export interface WorkflowPlan {
  job_id: string;
  recipe_id?: string | null;
  selection_profile?: string | null;
  tool: string;
  execution_engine?: string;
  workflow_exists: boolean;
  execution_ready: boolean;
  availability_error?: string | null;
  workflow_source: string;
  workflow_path: string;
  model_family?: string | null;
  maturity?: string | null;
  license?: string | null;
  warm_models: string[];
  cold_models: string[];
  watch_models?: string[];
  references?: string[];
  public_priors?: PublicDatasetPrior[];
  bootstrap_rules?: string[];
  community_takeaways?: string[];
  runtime_prior_bundle?: RuntimePriorBundleSummary | null;
  runtime_prior_artifacts?: RuntimePriorArtifact[];
  frontier_dataset_activation?: FrontierDatasetActivationSummary | null;
  frontier_dataset_items?: FrontierDatasetActivationItem[];
  notes?: string[];
}

export interface PublicDatasetPrior {
  dataset_id: string;
  label: string;
  kind: string;
  readiness?: string | null;
  availability?: string | null;
  scale?: string | null;
  license?: string | null;
  bootstraps: string[];
  notes?: string | null;
  references?: string[];
}

export interface RuntimePriorBundleSummary {
  label: string;
  profile?: string | null;
  generated_at?: string | null;
  artifact_count?: number | null;
}

export interface RuntimePriorArtifact {
  artifact_id: string;
  label: string;
  kind: string;
  bundle_path?: string | null;
  tool_scopes: string[];
  source_datasets: string[];
  training_tracks: string[];
  notes?: string | null;
  generated_at?: string | null;
  sha256?: string | null;
  size_bytes?: number | null;
  record_count?: number | null;
  summary_text?: string | null;
}

export interface FrontierDatasetActivationSummary {
  label: string;
  tool: string;
  task_ids: string[];
  dataset_count: number;
  active_count: number;
  local_cache_ready_count: number;
  runtime_prior_dataset_ids: string[];
  runpod_default_downloads_datasets: boolean;
  policy: string;
  warnings: string[];
  notes: string[];
}

export interface FrontierDatasetActivationItem {
  dataset_id: string;
  label: string;
  tasks: string[];
  kind: string;
  readiness: string;
  integration_status: string;
  availability: string;
  download_mode: string;
  runpod_default_download: boolean;
  local_dir: string;
  local_cache_present: boolean;
  activation_stage: string;
  studio_use: string[];
  blocking_reason?: string | null;
  license_note?: string | null;
  use_in_dreamcatcher?: string | null;
  references?: string[];
}

export interface StudioJobOutput {
  label: string;
  path: string;
  origin: string;
  kind?: string;
  linked_mask_path?: string | null;
  alpha_extracted?: boolean;
}

export interface StudioJobRecord extends WorkflowPlan {
  session_id: string;
  output_root: string;
  session_root: string;
  job_root: string;
  source_path?: string | null;
  prompt?: string | null;
  status: string;
  current_step?: string | null;
  error?: string | null;
  outputs: StudioJobOutput[];
  started_at?: string | null;
  finished_at?: string | null;
  updated_at?: string | null;
}

export interface StudioExportRecord {
  session_id: string;
  output_root: string;
  export_path: string;
  file_name: string;
}

export interface StudioExportPackageRecord {
  session_id: string;
  output_root: string;
  archive_path: string;
  file_name: string;
  file_count: number;
}

export interface StudioPresetExportResponse extends StudioExportPackageRecord {
  preset: 'review_pack' | 'client_delivery' | 'master_archive' | 'proofing_sheet' | 'print_master' | 'client_review_portal';
  delivery_profile: {
    preset: string;
    profile_id: string;
    label: string;
    branch_stage: 'review' | 'finish' | 'archive';
    master_source: string;
    description: string;
  };
}

export interface StudioBatchExportRecord {
  session_id: string;
  output_root: string;
  archive_path: string;
  file_name: string;
  file_count: number;
  catalog?: Record<string, unknown> | null;
}

export interface StudioBatchExportResponse {
  output_root: string;
  preset: 'review_pack' | 'client_delivery' | 'master_archive' | 'proofing_sheet' | 'print_master' | 'client_review_portal';
  delivery_profile?: {
    preset: string;
    profile_id: string;
    label: string;
    branch_stage: 'review' | 'finish' | 'archive';
    master_source: string;
    description: string;
  };
  batch_id: string;
  session_count: number;
  report_path: string;
  records: StudioBatchExportRecord[];
}

export interface StudioCatalogMetadata {
  session_id: string;
  output_root: string;
  rating: number;
  pick_status: 'unreviewed' | 'selected' | 'rejected' | 'hold';
  review_status: 'intake' | 'culling' | 'proofing' | 'client_review' | 'print_ready' | 'delivered' | 'archived';
  color_tag?: string | null;
  keywords: string[];
  notes?: string | null;
  proofing_profile?: string | null;
  print_profile?: string | null;
  client_collection?: string | null;
  updated_at: string;
}

export interface StudioCatalogBatchResponse {
  count: number;
  items: StudioCatalogMetadata[];
}

export interface StudioCompareAdviceSignal {
  severity: 'info' | 'warning' | 'risk';
  title: string;
  detail: string;
}

export interface StudioCompareAdviceMetrics {
  mean_luma: number;
  contrast: number;
  highlight_clip_ratio: number;
  shadow_clip_ratio: number;
  warmth: number;
  saturation: number;
  detail_energy: number;
}

export interface StudioCompareAdviceResponse {
  tool: string;
  summary: string;
  risk_level: 'low' | 'medium' | 'high';
  signals: StudioCompareAdviceSignal[];
  checklist: string[];
  public_prior_labels: string[];
  community_takeaways: string[];
  prior_guardrails: string[];
  priority_dimensions: string[];
  select_metrics: StudioCompareAdviceMetrics;
  candidate_metrics: StudioCompareAdviceMetrics;
  motion_watch?: {
    path: string;
    summary: string;
    coverage: number;
    compares_overlay: boolean;
    recommendation: string;
  } | null;
}

export interface StudioCompareDecisionResponse {
  decision_id: string;
  occurred_at: string;
  session_id: string;
  output_root: string;
  tool: string;
  action: 'keep_select' | 'accept_candidate' | 'manual';
  note?: string | null;
  select_path: string;
  candidate_path: string;
  winner_path: string;
  loser_path: string;
  winner_role: 'select' | 'candidate';
  select_metrics: StudioCompareAdviceMetrics;
  candidate_metrics: StudioCompareAdviceMetrics;
  winner_metrics: StudioCompareAdviceMetrics;
  loser_metrics: StudioCompareAdviceMetrics;
  winner_delta_vs_loser: Record<string, number>;
}

export type QualityVerdict = 'fail' | 'suspicious' | 'pass';

export interface QwenAxisScores {
  intent_match?: number | null;
  technical_quality?: number | null;
  aesthetic_quality?: number | null;
  subject_preservation?: number | null;
  mask_boundary?: number | null;
  color_naturalness?: number | null;
}

export interface QwenLocalizedIssue {
  area: string;
  issue_type: string;
  severity: 'info' | 'warning' | 'critical';
  description: string;
  confidence?: number | null;
  bbox_norm?: number[] | null;
  suggested_action?: string | null;
}

export interface QwenCorrectionPlan {
  exposure_delta?: number | null;
  contrast_delta?: number | null;
  shadow_delta?: number | null;
  highlight_delta?: number | null;
  temperature_delta?: number | null;
  tint_delta?: number | null;
  saturation_delta?: number | null;
  denoise_strength?: number | null;
  edit_strength?: number | null;
  crop_box_norm?: number[] | null;
  notes?: string | null;
}

export interface QwenJudgeSignal {
  schema_version?: string;
  verdict: QualityVerdict;
  confidence?: number;
  axis_scores?: QwenAxisScores;
  rationale?: string | null;
  failure_tags?: string[];
  localized_issues?: QwenLocalizedIssue[];
  correction_plan?: QwenCorrectionPlan;
  retry_instruction?: string | null;
  work_instruction?: string | null;
}

export interface JudgeEvidencePacket {
  schema_version: string;
  tool: string;
  task_intent: string;
  result_path: string;
  reference_path?: string | null;
  result_metrics: StudioCompareAdviceMetrics;
  reference_metrics?: StudioCompareAdviceMetrics | null;
  metric_delta: Record<string, number>;
  metric_units: Record<string, string>;
  operation_context: Record<string, unknown>;
  mask_evidence: Record<string, unknown>;
  raw_evidence: Record<string, unknown>;
  workflow_evidence: Record<string, unknown>;
  user_preference_evidence: Record<string, unknown>;
  golden_context: Record<string, unknown>;
  available_evidence: string[];
  missing_evidence: string[];
  cautions: string[];
}

export interface GoldenCalibrationResult {
  schema_version: string;
  applied: boolean;
  calibration_source?: string | null;
  profile_id: string;
  sample_count: number;
  calibrated_verdict?: QualityVerdict | null;
  calibrated_confidence?: number | null;
  calibrated_axis_scores: QwenAxisScores;
  added_failure_tags: string[];
  adjustments: string[];
  replay_required: boolean;
  replay_case_ids: string[];
  notes: string[];
}

export interface QualityAutomationPolicy {
  version: string;
  tuning_version: string;
  qwen_judge_schema_version: string;
  judge_evidence_packet_schema_version: string;
  golden_calibration_version: string;
  primary_local_model: string;
  primary_local_repo: string;
  local_judge_endpoint_env: string;
  local_judge_model_path_env: string;
  cloud_fallback_enabled: boolean;
  verdicts: QualityVerdict[];
  runtime_layers: string[];
  metric_checkers: string[];
  automation_allowed: string[];
  human_approval_required_for: string[];
  automation_blocked: string[];
  qwen_response_required_keys: string[];
}

export interface QualityMetricSignal {
  tag: string;
  severity: 'info' | 'warning' | 'critical';
  detail: string;
  value?: number | null;
  threshold?: number | null;
}

export interface QualityAssessmentResponse {
  assessment_id: string;
  created_at: string;
  session_id?: string | null;
  output_root: string;
  tool: string;
  result_path: string;
  reference_path?: string | null;
  version: string;
  primary_local_model: string;
  cloud_fallback_enabled: boolean;
  verdict: QualityVerdict;
  human_approval_required: boolean;
  human_review_reason: string[];
  qwen_judge_signal?: QwenJudgeSignal | null;
  qwen_judge_schema_version: string;
  judge_evidence_packet?: JudgeEvidencePacket | null;
  golden_calibration?: GoldenCalibrationResult | null;
  result_metrics: StudioCompareAdviceMetrics;
  reference_metrics?: StudioCompareAdviceMetrics | null;
  metric_delta: Record<string, number>;
  metric_signals: QualityMetricSignal[];
  failure_tags: string[];
  work_instructions: string[];
  retry_plan: {
    retry_allowed: boolean;
    human_approval_before_accept: boolean;
    max_attempts: number;
    instructions: string[];
  };
  tuning_targets: string[];
  golden_runner_required: boolean;
  code_tuning_gate: Record<string, unknown>;
  artifact_path?: string | null;
}

export interface QualityTuningProposalResponse {
  proposal_id: string;
  created_at: string;
  version: string;
  output_root: string;
  session_id?: string | null;
  source_assessment_count: number;
  status: 'waiting_for_quality_evidence' | 'human_approval_required';
  automatic_code_tuning_enabled: boolean;
  human_approval_required: boolean;
  failure_clusters: Record<string, number>;
  suggested_changes: Array<Record<string, unknown>>;
  golden_runner_plan: Record<string, unknown>;
  blocked_actions: string[];
  allowed_next_actions: string[];
  artifact_path?: string | null;
}

export interface StudioSelectionControls {
  threshold: number;
  expand_pixels: number;
  feather_radius: number;
}

export interface StudioSelectionState {
  session_id: string;
  output_root: string;
  selection_root: string;
  state_path: string;
  source_mask_path: string;
  source_asset_path?: string | null;
  current_mask_path: string;
  preview_path: string;
  controls: StudioSelectionControls;
  width: number;
  height: number;
  selected_pixels: number;
  total_pixels: number;
  coverage_ratio: number;
  bounding_box?: number[] | null;
  summary: string;
  ready: boolean;
  updated_at: string;
}

export interface StudioEditLinkageState {
  session_id: string;
  output_root: string;
  linkage_root: string;
  state_path: string;
  current_source_path?: string | null;
  current_source_kind?: string | null;
  current_source_label?: string | null;
  active_tool?: string | null;
  latest_job_id?: string | null;
  latest_tool?: string | null;
  latest_prompt?: string | null;
  latest_background_cutout_paths: string[];
  latest_generated_candidate_paths: string[];
  latest_linked_mask_paths: string[];
  selection_source_mask_path?: string | null;
  selection_current_mask_path?: string | null;
  selection_preview_path?: string | null;
  selection_summary?: string | null;
  source_history: string[];
  source_history_index: number;
  mask_ready: boolean;
  dreamgen_ready: boolean;
  current_source_matches_generated: boolean;
  current_source_matches_cutout: boolean;
  summary: string;
  next_step: string;
  updated_at: string;
}

export async function parseJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof (payload as { detail?: unknown }).detail === 'string'
      ? String((payload as { detail?: string }).detail)
      : '요청 처리 중 오류가 발생했습니다.';
    throw new Error(detail);
  }
  return payload as T;
}

export function generateSessionId(): string {
  const now = new Date();
  const parts = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
    String(now.getHours()).padStart(2, '0'),
    String(now.getMinutes()).padStart(2, '0'),
    String(now.getSeconds()).padStart(2, '0'),
  ];
  return `studio_${parts.join('')}`;
}

export function summarizeRawprepHealth(payload: RawprepHealthPayload | null): string {
  if (!payload) {
    return 'TriRaw 준비 상태를 확인하는 중입니다.';
  }
  if (payload.message) {
    return payload.message;
  }
  if (payload.ok) {
    return 'TriRaw(rawprep) 백엔드가 준비되어 있습니다.';
  }
  const missing = Object.values(payload.engine_readiness ?? {})
    .flatMap((engine) => engine.missing_tools)
    .filter((value, index, array) => array.indexOf(value) === index);
  return missing.length
    ? `TriRaw 선택 기능은 가능하지만, 현재 비어 있는 도구가 있습니다: ${missing.join(', ')}`
    : 'TriRaw 준비 상태를 읽었지만 추가 확인이 필요합니다.';
}

export async function fetchRawRestorationPolicy(): Promise<RawRestorationPolicyPayload> {
  const response = await fetch('/api/rawprep/restoration-goals');
  return parseJson<RawRestorationPolicyPayload>(response);
}

export function isAiCapableTool(tool: ToolKey): boolean {
  return ['removeBg', 'replaceBg', 'relight', 'replaceObject', 'expandCanvas', 'retouch', 'enhance'].includes(tool);
}

export async function fetchStudioCompareAdvice(request: {
  outputRoot: string;
  primaryPath: string;
  candidatePath: string;
  tool: ToolKey;
  motionOverlayPath?: string | null;
  motionOverlaySummary?: string | null;
  motionOverlayCoverage?: number | null;
}): Promise<StudioCompareAdviceResponse> {
  const response = await fetch('/api/studio/compare/advice', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      output_root: request.outputRoot,
      primary_path: request.primaryPath,
      candidate_path: request.candidatePath,
      tool: request.tool,
      motion_overlay_path: request.motionOverlayPath ?? null,
      motion_overlay_summary: request.motionOverlaySummary ?? null,
      motion_overlay_coverage: request.motionOverlayCoverage ?? null,
    }),
  });
  return parseJson<StudioCompareAdviceResponse>(response);
}

export async function recordStudioCompareDecision(request: {
  sessionId: string;
  outputRoot: string;
  primaryPath: string;
  candidatePath: string;
  winnerPath: string;
  tool: ToolKey;
  action: 'keep_select' | 'accept_candidate' | 'manual';
  note?: string | null;
}): Promise<StudioCompareDecisionResponse> {
  const response = await fetch('/api/studio/compare/decision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: request.sessionId,
      output_root: request.outputRoot,
      primary_path: request.primaryPath,
      candidate_path: request.candidatePath,
      winner_path: request.winnerPath,
      tool: request.tool,
      action: request.action,
      note: request.note ?? null,
    }),
  });
  return parseJson<StudioCompareDecisionResponse>(response);
}

export async function fetchQualityAutomationPolicy(): Promise<QualityAutomationPolicy> {
  const response = await fetch('/api/studio/quality-automation/policy');
  return parseJson<QualityAutomationPolicy>(response);
}

export async function createQualityAssessment(request: {
  outputRoot: string;
  sessionId?: string | null;
  tool: ToolKey;
  resultPath: string;
  referencePath?: string | null;
  qwenJudgeSignal?: QwenJudgeSignal | null;
  judgeEvidencePacket?: JudgeEvidencePacket | null;
  runQwenJudge?: boolean;
  taskIntent?: string | null;
  seedRoot?: string;
  operationContext?: Record<string, unknown>;
  maskEvidence?: Record<string, unknown>;
  rawEvidence?: Record<string, unknown>;
  workflowEvidence?: Record<string, unknown>;
  userPreferenceEvidence?: Record<string, unknown>;
  writeArtifact?: boolean;
}): Promise<QualityAssessmentResponse> {
  const response = await fetch('/api/studio/quality-automation/assess', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      output_root: request.outputRoot,
      session_id: request.sessionId ?? null,
      tool: request.tool,
      result_path: request.resultPath,
      reference_path: request.referencePath ?? null,
      qwen_judge_signal: request.qwenJudgeSignal ?? null,
      judge_evidence_packet: request.judgeEvidencePacket ?? null,
      run_qwen_judge: request.runQwenJudge ?? false,
      task_intent: request.taskIntent ?? null,
      seed_root: request.seedRoot ?? 'seed_bundle',
      operation_context: request.operationContext ?? {},
      mask_evidence: request.maskEvidence ?? {},
      raw_evidence: request.rawEvidence ?? {},
      workflow_evidence: request.workflowEvidence ?? {},
      user_preference_evidence: request.userPreferenceEvidence ?? {},
      write_artifact: request.writeArtifact ?? true,
    }),
  });
  return parseJson<QualityAssessmentResponse>(response);
}

export async function createQualityTuningProposal(request: {
  outputRoot: string;
  sessionId?: string | null;
  assessments?: QualityAssessmentResponse[];
  assessmentPaths?: string[];
  writeArtifact?: boolean;
}): Promise<QualityTuningProposalResponse> {
  const response = await fetch('/api/studio/quality-automation/tuning/proposal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      output_root: request.outputRoot,
      session_id: request.sessionId ?? null,
      assessments: request.assessments ?? [],
      assessment_paths: request.assessmentPaths ?? [],
      write_artifact: request.writeArtifact ?? true,
    }),
  });
  return parseJson<QualityTuningProposalResponse>(response);
}

export async function applyDreamispPreviewAdjustments(request: {
  sessionId: string;
  outputRoot: string;
  sliders: {
    strength: number;
    realism: number;
    preserveTexture: number;
  };
  controls?: {
    temperatureDelta: number;
    tintDelta: number;
    exposureEv: number;
    contrast: number;
    clarity: number;
  };
}): Promise<IntakePlan> {
  const response = await fetch('/api/studio/dreamisp/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: request.sessionId,
      output_root: request.outputRoot,
      sliders: {
        strength: request.sliders.strength,
        realism: request.sliders.realism,
        preserve_texture: request.sliders.preserveTexture,
      },
      controls: request.controls ? {
        temperature_delta: request.controls.temperatureDelta,
        tint_delta: request.controls.tintDelta,
        exposure_ev: request.controls.exposureEv,
        contrast: request.controls.contrast,
        clarity: request.controls.clarity,
      } : null,
    }),
  });
  return parseJson<IntakePlan>(response);
}

export async function fetchStudioSelectionState(request: {
  sessionId: string;
  outputRoot: string;
}): Promise<StudioSelectionState> {
  const params = new URLSearchParams({
    session_id: request.sessionId,
    output_root: request.outputRoot,
  });
  const response = await fetch(`/api/studio/selection?${params.toString()}`);
  return parseJson<StudioSelectionState>(response);
}

export async function applyStudioSelectionState(request: {
  sessionId: string;
  outputRoot: string;
  sourceMaskPath: string;
  sourceAssetPath?: string | null;
  controls?: {
    threshold: number;
    expandPixels: number;
    featherRadius: number;
  };
}): Promise<StudioSelectionState> {
  const response = await fetch('/api/studio/selection/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: request.sessionId,
      output_root: request.outputRoot,
      source_mask_path: request.sourceMaskPath,
      source_asset_path: request.sourceAssetPath ?? null,
      controls: request.controls ? {
        threshold: request.controls.threshold,
        expand_pixels: request.controls.expandPixels,
        feather_radius: request.controls.featherRadius,
      } : null,
    }),
  });
  return parseJson<StudioSelectionState>(response);
}

export async function fetchStudioEditLinkageState(request: {
  sessionId: string;
  outputRoot: string;
}): Promise<StudioEditLinkageState> {
  const params = new URLSearchParams({
    session_id: request.sessionId,
    output_root: request.outputRoot,
  });
  const response = await fetch(`/api/studio/edit-linkage?${params.toString()}`);
  return parseJson<StudioEditLinkageState>(response);
}

export async function syncStudioEditLinkageState(request: {
  sessionId: string;
  outputRoot: string;
  currentSourcePath?: string | null;
  activeTool?: string | null;
  studioJobId?: string | null;
  sourceHistory?: string[];
  sourceHistoryIndex?: number;
}): Promise<StudioEditLinkageState> {
  const response = await fetch('/api/studio/edit-linkage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: request.sessionId,
      output_root: request.outputRoot,
      current_source_path: request.currentSourcePath ?? null,
      active_tool: request.activeTool ?? null,
      studio_job_id: request.studioJobId ?? null,
      source_history: request.sourceHistory ?? [],
      source_history_index: request.sourceHistoryIndex ?? -1,
    }),
  });
  return parseJson<StudioEditLinkageState>(response);
}

