import type { AppState } from '../types';
import { apiFetch } from '../api/client';
import { loadConfig } from '../api/config';
import { runSync, type SyncSummary } from './runSync';

const LAST_SYNC_KEY = 'pulso.lastSyncSummary';
export const SYNC_EVENT = 'pulso:sync-summary';

export function saveLastSummary(s: SyncSummary): void {
  try {
    localStorage.setItem(LAST_SYNC_KEY, JSON.stringify(s));
  } catch {
    /* sin almacenamiento local */
  }
}

export function loadLastSummary(): SyncSummary | null {
  try {
    const raw = localStorage.getItem(LAST_SYNC_KEY);
    return raw ? (JSON.parse(raw) as SyncSummary) : null;
  } catch {
    return null;
  }
}

/** Sincronización al abrir: solo si hay carpeta local configurada y "Sincronizar al abrir" activo. Nunca lanza. */
export async function startupSync(state: AppState, onState: (s: AppState) => void): Promise<void> {
  try {
    const config = await loadConfig();
    if (!config?.cvFolder || !config.syncOnOpen) return;
    const summary = await runSync({
      root: config.cvFolder,
      origin: 'sync_local',
      positions: state.positions,
      sources: state.jobBoards,
    });
    saveLastSummary(summary);
    window.dispatchEvent(new CustomEvent(SYNC_EVENT, { detail: summary }));
    const fresh = await apiFetch<AppState>('/api/state');
    onState(fresh);
  } catch {
    /* silencioso: la app sigue funcionando */
  }
}
