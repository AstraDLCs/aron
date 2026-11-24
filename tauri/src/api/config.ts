import { load, type Store } from '@tauri-apps/plugin-store';

/** URL de la API por defecto. ÚNICO lugar donde se define el endpoint oficial. */
export const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export type AppConfig = { apiBaseUrl: string; cvFolder: string | null; syncOnOpen: boolean };

const DEFAULTS: AppConfig = { apiBaseUrl: DEFAULT_API_BASE_URL, cvFolder: null, syncOnOpen: true };

export const isTauri = (): boolean => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

const stores = new Map<string, Promise<Store>>();
export function getStore(file: string): Promise<Store> {
  let p = stores.get(file);
  if (!p) {
    p = load(file, { autoSave: true, defaults: {} });
    stores.set(file, p);
  }
  return p;
}

let cached: AppConfig | null = null;

export function normalizeBaseUrl(url: string): string {
  let u = (url || '').trim();
  if (!u) return DEFAULT_API_BASE_URL;
  if (!/^https?:\/\//i.test(u)) u = 'http://' + u;
  return u.replace(/\/+$/, '');
}

/** Devuelve un mensaje de error si la URL no es aceptable (remota sin https). */
export function validateApiUrl(url: string): string | null {
  const u = normalizeBaseUrl(url);
  let parsed: URL;
  try {
    parsed = new URL(u);
  } catch {
    return 'La URL del servidor no es válida';
  }
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname);
  if (!local && parsed.protocol !== 'https:') return 'Usa https:// para servidores remotos';
  return null;
}

export async function loadConfig(): Promise<AppConfig> {
  if (cached) return cached;
  let raw: Partial<AppConfig> = {};
  try {
    if (isTauri()) {
      const s = await getStore('config.json');
      raw = {
        apiBaseUrl: (await s.get<string>('apiBaseUrl')) ?? undefined,
        cvFolder: (await s.get<string | null>('cvFolder')) ?? null,
        syncOnOpen: (await s.get<boolean>('syncOnOpen')) ?? undefined,
      };
    } else {
      raw = JSON.parse(localStorage.getItem('pl-config') || '{}');
    }
  } catch {
    raw = {};
  }
  cached = {
    apiBaseUrl: normalizeBaseUrl(raw.apiBaseUrl || DEFAULTS.apiBaseUrl),
    cvFolder: raw.cvFolder ?? null,
    syncOnOpen: raw.syncOnOpen ?? DEFAULTS.syncOnOpen,
  };
  return cached;
}

export async function saveConfig(patch: Partial<AppConfig>): Promise<AppConfig> {
  const current = await loadConfig();
  const next: AppConfig = { ...current, ...patch };
  next.apiBaseUrl = normalizeBaseUrl(next.apiBaseUrl);
  const invalid = validateApiUrl(next.apiBaseUrl);
  if (invalid) throw new Error(invalid);
  cached = next;
  try {
    if (isTauri()) {
      const s = await getStore('config.json');
      await s.set('apiBaseUrl', next.apiBaseUrl);
      await s.set('cvFolder', next.cvFolder);
      await s.set('syncOnOpen', next.syncOnOpen);
      await s.save();
    } else {
      localStorage.setItem('pl-config', JSON.stringify(next));
    }
  } catch {
    /* sin persistencia */
  }
  return next;
}

export function getCachedConfig(): AppConfig {
  return cached ?? DEFAULTS;
}
