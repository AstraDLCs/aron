import { load, type Store } from '@tauri-apps/plugin-store';

/** API oficial. ÚNICO lugar donde se define. El instalador (.msi) se conecta siempre a esta. */
export const OFFICIAL_API_BASE_URL = 'https://aron.astra-industria.dev';
/** Solo en desarrollo (`npm run tauri dev`) se usa la API local y se puede cambiar desde «Servidor». */
export const API_URL_EDITABLE = import.meta.env.DEV;
export const DEFAULT_API_BASE_URL = API_URL_EDITABLE ? 'http://localhost:8000' : OFFICIAL_API_BASE_URL;

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
    // En el instalador se ignora cualquier URL guardada antes (p. ej. un localhost de pruebas).
    apiBaseUrl: API_URL_EDITABLE ? normalizeBaseUrl(raw.apiBaseUrl || DEFAULTS.apiBaseUrl) : OFFICIAL_API_BASE_URL,
    cvFolder: raw.cvFolder ?? null,
    syncOnOpen: raw.syncOnOpen ?? DEFAULTS.syncOnOpen,
  };
  return cached;
}

export async function saveConfig(patch: Partial<AppConfig>): Promise<AppConfig> {
  const current = await loadConfig();
  const next: AppConfig = { ...current, ...patch };
  next.apiBaseUrl = API_URL_EDITABLE ? normalizeBaseUrl(next.apiBaseUrl) : OFFICIAL_API_BASE_URL;
  const invalid = validateApiUrl(next.apiBaseUrl);
  if (invalid) throw new Error(invalid);
  const serverChanged = next.apiBaseUrl !== current.apiBaseUrl;
  cached = next;
  try {
    if (isTauri()) {
      const s = await getStore('config.json');
      // Solo se guarda la URL en desarrollo; en el instalador se borra la que hubiera quedado.
      if (API_URL_EDITABLE) await s.set('apiBaseUrl', next.apiBaseUrl);
      else await s.delete('apiBaseUrl');
      await s.set('cvFolder', next.cvFolder);
      await s.set('syncOnOpen', next.syncOnOpen);
      await s.save();
    } else {
      localStorage.setItem('pl-config', JSON.stringify(next));
    }
  } catch {
    /* sin persistencia */
  }
  if (serverChanged) {
    // El token nunca se envía a otro servidor: al cambiar la URL se cierra la sesión.
    const session = await import('./session');
    const had = await session.getToken();
    await session.setToken(null);
    if (had) session.fireUnauthorized('Cambiaste el servidor. Ingresa nuevamente.');
  }
  return next;
}

export function getCachedConfig(): AppConfig {
  return cached ?? DEFAULTS;
}
