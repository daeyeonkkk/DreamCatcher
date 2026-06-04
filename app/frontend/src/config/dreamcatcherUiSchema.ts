export const TOPBAR_ITEMS = [
  'topbar.newProject',
  'topbar.open',
  'topbar.save',
  'topbar.export',
  'topbar.compare',
  'topbar.settings',
] as const;

export const TOOL_KEYS = [
  'removeBg',
  'replaceBg',
  'relight',
  'replaceObject',
  'expandCanvas',
  'retouch',
  'enhance',
  'finish',
  'compare',
] as const;

export const RIGHT_PANEL_KEYS = [
  'panels.layers',
  'panels.history',
  'panels.variants',
  'panels.properties',
  'panels.mask',
  'panels.export',
] as const;

export const SIMPLE_MODE_ALLOWED_PRO_TERMS = new Set<string>([
  'toasts',
  'errors',
  'help',
]);
