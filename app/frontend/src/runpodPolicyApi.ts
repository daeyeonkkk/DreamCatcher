export interface RunPodModelSet {
  model_set_id: string;
  cli_flag: string | null;
  label: string;
  summary: string;
  task_tags: string[];
  frontier_default: boolean;
  bootstrap_supported: boolean;
  integration_status: string;
  min_vram_class: string;
  requires_hf_token: boolean;
  license_note: string;
  research_refs: string[];
  data_refs: string[];
  target_paths: string[];
}

export interface RunPodModelProfile {
  profile_id: 'frontier' | string;
  label: string;
  summary: string;
  model_set_ids: string[];
  min_vram_class: string;
  requires_hf_token: boolean;
  license_note: string;
  bootstrap_command: string;
  model_sets: RunPodModelSet[];
}

export interface RunPodModelProfilesPayload {
  default_profile: string;
  profiles: RunPodModelProfile[];
  available_model_sets: RunPodModelSet[];
}

export interface RunPodTemplatePolicy {
  template_type: string;
  recommended_gpu_server?: string;
  recommended_gpu_vram?: string;
  image_primary: string;
  compatibility_alias: string;
  fallback_image: string;
  cuda13_experimental_image: string;
  storage_policy: string;
  upload_artifact: string;
  workspace: Record<string, string>;
  ports: Record<string, string>;
  required_env: Record<string, string>;
  gpu_selection_policy: string;
}

export interface RunPodBootstrapSessionPolicy {
  mode: string;
  default_profile: string;
  frontier_bootstrap_scope: string;
  startup_policy: string[];
  end_of_session_policy: string[];
  persistent_volume_policy: string;
  recovery_contract: string;
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function fetchRunPodModelProfiles(): Promise<RunPodModelProfilesPayload> {
  return fetchJson<RunPodModelProfilesPayload>('/api/runpod/model-profiles');
}

export function fetchRunPodTemplatePolicy(): Promise<RunPodTemplatePolicy> {
  return fetchJson<RunPodTemplatePolicy>('/api/runpod/template-policy');
}

export function fetchRunPodBootstrapSession(): Promise<RunPodBootstrapSessionPolicy> {
  return fetchJson<RunPodBootstrapSessionPolicy>('/api/runpod/bootstrap-session');
}
