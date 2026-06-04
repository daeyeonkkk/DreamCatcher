import type React from 'react';
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import * as Dialog from '@radix-ui/react-dialog';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import * as Slider from '@radix-ui/react-slider';
import * as Tooltip from '@radix-ui/react-tooltip';
import { Cpu, Download, FlaskConical, Menu, Power, Server, ShieldCheck, Sparkles } from 'lucide-react';
import { Layer, Rect, Stage, Text as KonvaText } from 'react-konva';
import { chipStyle, studioTokens } from '../designTokens';
import { studioShellLocale } from '../i18n/studioShellLocale';
import {
  fetchRunPodBootstrapSession,
  fetchRunPodModelProfiles,
  fetchRunPodTemplatePolicy,
  type RunPodModelProfile,
  type RunPodModelSet,
} from '../runpodPolicyApi';
import { useRunPodStudioStore } from '../runpodStudioStore';

const compactButtonStyle: React.CSSProperties = {
  width: 36,
  height: 36,
  display: 'grid',
  placeItems: 'center',
  borderRadius: 10,
  border: `1px solid ${studioTokens.color.line}`,
  background: studioTokens.color.surface,
  color: studioTokens.color.accent,
  cursor: 'pointer',
};

const panelStyle: React.CSSProperties = {
  border: `1px solid ${studioTokens.color.line}`,
  background: studioTokens.color.surface,
  boxShadow: studioTokens.shadow.card,
  borderRadius: studioTokens.radius.m,
  padding: 14,
  color: studioTokens.color.ink,
};

function parseVramClass(value: string | undefined): number {
  if (!value) return 0;
  const match = value.match(/\d+/);
  return match ? Number(match[0]) : 0;
}

function TooltipIconButton({
  label,
  children,
  onClick,
}: {
  label: string;
  children: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button type="button" aria-label={label} style={compactButtonStyle} onClick={onClick}>
          {children}
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="top"
          style={{
            borderRadius: 8,
            padding: '7px 9px',
            background: studioTokens.color.accent,
            color: studioTokens.color.surface,
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          {label}
          <Tooltip.Arrow fill={studioTokens.color.accent} />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

function SessionMap({ executableCount, researchCount }: { executableCount: number; researchCount: number }) {
  return (
    <Stage width={190} height={52}>
      <Layer>
        <Rect x={0} y={8} width={50} height={28} cornerRadius={6} fill="#dbe9e0" stroke="#b9ddc6" />
        <Rect x={64} y={8} width={58} height={28} cornerRadius={6} fill="#e4eff0" stroke="#bdd0e8" />
        <Rect x={136} y={8} width={52} height={28} cornerRadius={6} fill="#f5e6d0" stroke="#f1dfc6" />
        <KonvaText x={8} y={17} text="Zip" fontSize={10} fill="#2f6148" fontStyle="bold" />
        <KonvaText x={72} y={17} text={`${executableCount} set`} fontSize={10} fill="#31566d" fontStyle="bold" />
        <KonvaText x={144} y={17} text={`${researchCount} R&D`} fontSize={10} fill="#9a641f" fontStyle="bold" />
      </Layer>
    </Stage>
  );
}

function groupModelSets(modelSets: RunPodModelSet[]) {
  const groups = new Map<string, RunPodModelSet[]>();
  for (const modelSet of modelSets) {
    const key = modelSet.task_tags[0] ?? 'frontier';
    groups.set(key, [...(groups.get(key) ?? []), modelSet]);
  }
  return Array.from(groups.entries());
}

export function EphemeralRunPodStrip() {
  const text = studioShellLocale.runpod;
  const { advancedOpsOpen, targetVramGb, setAdvancedOpsOpen, setTargetVramGb } = useRunPodStudioStore();

  const profilesQuery = useQuery({
    queryKey: ['runpod', 'model-profiles'],
    queryFn: fetchRunPodModelProfiles,
    staleTime: 60_000,
  });
  const templateQuery = useQuery({
    queryKey: ['runpod', 'template-policy'],
    queryFn: fetchRunPodTemplatePolicy,
    staleTime: 60_000,
  });
  const sessionQuery = useQuery({
    queryKey: ['runpod', 'bootstrap-session'],
    queryFn: fetchRunPodBootstrapSession,
    staleTime: 60_000,
  });

  const profiles = profilesQuery.data?.profiles ?? [];
  const frontierProfile: RunPodModelProfile | undefined =
    profiles.find((profile) => profile.profile_id === 'frontier') ?? profiles[0];
  const modelSets = frontierProfile?.model_sets ?? profilesQuery.data?.available_model_sets ?? [];
  const executableSets = modelSets.filter((modelSet) => modelSet.bootstrap_supported && modelSet.integration_status === 'ready');
  const researchSets = modelSets.filter((modelSet) => !modelSet.bootstrap_supported || modelSet.integration_status !== 'ready');
  const selectedVram = parseVramClass(frontierProfile?.min_vram_class);
  const vramReady = selectedVram === 0 || targetVramGb >= selectedVram;
  const gpuLabel = templateQuery.data?.recommended_gpu_server ?? 'RTX PRO 6000';
  const statusLabel = profilesQuery.isLoading || templateQuery.isLoading || sessionQuery.isLoading
    ? text.loading
    : profilesQuery.isError || templateQuery.isError || sessionQuery.isError
      ? text.unavailable
      : sessionQuery.data?.mode ?? 'ephemeral_zip_pod';

  const groupedSets = useMemo(() => groupModelSets(modelSets), [modelSets]);

  return (
    <Tooltip.Provider delayDuration={180}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: 14,
          alignItems: 'center',
          padding: '12px 20px',
          maxWidth: 1760,
          margin: '0 auto',
        }}
      >
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', minWidth: 0, flexWrap: 'wrap' }}>
          <span style={{ ...chipStyle('ink'), display: 'inline-flex', gap: 8, alignItems: 'center' }}>
            <Server size={14} />
            {text.title}
          </span>
          <span style={{ ...chipStyle('accent'), display: 'inline-flex', gap: 8, alignItems: 'center' }}>
            <Cpu size={14} />
            {text.gpu} {gpuLabel}
          </span>
          <span style={{ ...chipStyle(vramReady ? 'success' : 'warning'), display: 'inline-flex', gap: 8, alignItems: 'center' }}>
            <Cpu size={14} />
            {text.vram} {targetVramGb}GB
          </span>
          <span style={{ ...chipStyle('default'), overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {statusLabel}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'center', flexWrap: 'wrap' }}>
          <span style={{ ...chipStyle('accent'), display: 'inline-flex', gap: 8, alignItems: 'center' }}>
            <Sparkles size={14} />
            {text.frontier}
          </span>
          <span style={{ ...chipStyle('success') }}>
            {text.executableSets} {executableSets.length}
          </span>
          <span style={{ ...chipStyle('warning') }}>
            {text.researchSets} {researchSets.length}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <SessionMap executableCount={executableSets.length} researchCount={researchSets.length} />
          <TooltipIconButton label={text.recoverOutputs}>
            <Download size={17} />
          </TooltipIconButton>
          <TooltipIconButton label={text.terminate}>
            <Power size={17} />
          </TooltipIconButton>

          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button type="button" aria-label={text.template} style={compactButtonStyle}>
                <Menu size={17} />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content side="top" align="end" style={{ ...panelStyle, width: 320 }}>
                <DropdownMenu.Label style={{ fontSize: 12, fontWeight: 800, color: studioTokens.color.accent }}>
                  {text.template}
                </DropdownMenu.Label>
                <DropdownMenu.Separator style={{ height: 1, background: studioTokens.color.line, margin: '9px 0' }} />
                <DropdownMenu.Item style={{ fontSize: 12, lineHeight: 1.5 }}>
                  Primary: {templateQuery.data?.image_primary ?? 'runpod/comfyui:1.4.1-cuda12.8'}
                </DropdownMenu.Item>
                <DropdownMenu.Item style={{ fontSize: 12, lineHeight: 1.5 }}>
                  Alias: {templateQuery.data?.compatibility_alias ?? 'runpod/comfyui:cuda12.8'}
                </DropdownMenu.Item>
                <DropdownMenu.Item style={{ fontSize: 12, lineHeight: 1.5 }}>
                  {text.cuda13Lab}
                </DropdownMenu.Item>
                <DropdownMenu.Item style={{ fontSize: 12, lineHeight: 1.5 }}>
                  {text.comfyAdmin}
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>

          <Dialog.Root open={advancedOpsOpen} onOpenChange={setAdvancedOpsOpen}>
            <Dialog.Trigger asChild>
              <button type="button" aria-label={text.advancedOps} style={compactButtonStyle}>
                <FlaskConical size={17} />
              </button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay style={{ position: 'fixed', inset: 0, background: 'rgba(31, 36, 40, 0.22)', zIndex: 80 }} />
              <Dialog.Content
                style={{
                  ...panelStyle,
                  position: 'fixed',
                  right: 24,
                  bottom: 84,
                  zIndex: 90,
                  width: 'min(540px, calc(100vw - 32px))',
                  display: 'grid',
                  gap: 14,
                }}
              >
                <Dialog.Title style={{ margin: 0, fontSize: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
                  <ShieldCheck size={18} />
                  {text.sessionPolicy}
                </Dialog.Title>
                <Dialog.Description style={{ margin: 0, fontSize: 12, color: studioTokens.color.muted, lineHeight: 1.6 }}>
                  {sessionQuery.data?.frontier_bootstrap_scope ?? frontierProfile?.summary ?? text.unavailable}
                </Dialog.Description>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8 }}>
                  {groupedSets.slice(0, 6).map(([group, items]) => (
                    <span key={group} style={{ ...chipStyle('default'), display: 'inline-flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                      {group.replace(/_/g, ' ')} {items.length}
                    </span>
                  ))}
                </div>
                <div style={{ display: 'grid', gap: 8 }}>
                  {(sessionQuery.data?.end_of_session_policy ?? [text.recoverOutputs]).map((item) => (
                    <span key={item} style={{ fontSize: 12, color: studioTokens.color.inkSoft }}>
                      {item}
                    </span>
                  ))}
                </div>
                <div style={{ display: 'grid', gap: 8 }}>
                  <strong style={{ fontSize: 12 }}>{text.vram}</strong>
                  <Slider.Root
                    value={[targetVramGb]}
                    min={24}
                    max={128}
                    step={8}
                    onValueChange={(values) => setTargetVramGb(values[0] ?? targetVramGb)}
                    style={{ position: 'relative', display: 'flex', alignItems: 'center', height: 24 }}
                  >
                    <Slider.Track style={{ position: 'relative', flexGrow: 1, height: 4, borderRadius: 999, background: studioTokens.color.line }}>
                      <Slider.Range style={{ position: 'absolute', height: '100%', borderRadius: 999, background: studioTokens.color.accent }} />
                    </Slider.Track>
                    <Slider.Thumb
                      aria-label={text.vram}
                      style={{
                        display: 'block',
                        width: 18,
                        height: 18,
                        borderRadius: 9,
                        border: `2px solid ${studioTokens.color.surface}`,
                        background: studioTokens.color.accent,
                        boxShadow: studioTokens.shadow.soft,
                      }}
                    />
                  </Slider.Root>
                  <span style={{ fontSize: 12, color: studioTokens.color.muted }}>
                    {text.minVram}: {frontierProfile?.min_vram_class ?? '48GB'}
                  </span>
                </div>
                <Dialog.Close asChild>
                  <button type="button" style={{ ...compactButtonStyle, width: '100%', fontWeight: 800 }}>
                    OK
                  </button>
                </Dialog.Close>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </div>
      </div>
    </Tooltip.Provider>
  );
}
