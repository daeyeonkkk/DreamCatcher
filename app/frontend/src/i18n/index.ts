export type LocaleCode = 'ko-KR' | 'en-US';

type MessageValue = string | number | boolean | null | MessageTree | MessageValue[];
interface MessageTree {
  [key: string]: MessageValue;
}

export interface I18nInstance {
  locale: LocaleCode;
  t: (key: string, args?: Record<string, string | number>) => string;
  raw: <T = MessageValue>(key: string) => T | undefined;
  exists: (key: string) => boolean;
}

function getByPath(obj: unknown, key: string): MessageValue | undefined {
  return key.split('.').reduce<MessageValue | undefined>((acc, segment) => {
    if (acc === undefined || acc === null || typeof acc !== 'object' || Array.isArray(acc)) {
      return undefined;
    }
    return (acc as MessageTree)[segment];
  }, obj as MessageValue);
}

function interpolate(template: string, args?: Record<string, string | number>): string {
  if (!args) return template;
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = args[key];
    return value === undefined ? `{${key}}` : String(value);
  });
}

export function createI18n(
  catalogs: Record<LocaleCode, MessageTree>,
  locale: LocaleCode,
  fallback: LocaleCode = 'ko-KR',
): I18nInstance {
  const current = catalogs[locale];
  const fallbackCatalog = catalogs[fallback];

  return {
    locale,
    t(key, args) {
      const candidate = getByPath(current, key) ?? getByPath(fallbackCatalog, key);
      if (typeof candidate === 'string') {
        return interpolate(candidate, args);
      }
      if (candidate === undefined) {
        return key;
      }
      return String(candidate);
    },
    raw<T = MessageValue>(key: string) {
      return (getByPath(current, key) ?? getByPath(fallbackCatalog, key)) as T | undefined;
    },
    exists(key: string) {
      return getByPath(current, key) !== undefined || getByPath(fallbackCatalog, key) !== undefined;
    },
  };
}
