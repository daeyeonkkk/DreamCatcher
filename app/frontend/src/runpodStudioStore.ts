import { create } from 'zustand';

interface RunPodStudioState {
  advancedOpsOpen: boolean;
  targetVramGb: number;
  setAdvancedOpsOpen: (open: boolean) => void;
  setTargetVramGb: (value: number) => void;
}

export const useRunPodStudioStore = create<RunPodStudioState>((set) => ({
  advancedOpsOpen: false,
  targetVramGb: 96,
  setAdvancedOpsOpen: (open) => set({ advancedOpsOpen: open }),
  setTargetVramGb: (value) => set({ targetVramGb: value }),
}));
