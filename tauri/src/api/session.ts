import { getStore, isTauri } from './config';

let token: string | null | undefined;

export async function getToken(): Promise<string | null> {
  if (token !== undefined) return token;
  try {
    if (isTauri()) {
      const s = await getStore('session.json');
      token = (await s.get<string>('token')) ?? null;
    } else {
      token = localStorage.getItem('pl-token');
    }
  } catch {
    token = null;
  }
  return token ?? null;
}

export async function setToken(t: string | null): Promise<void> {
  token = t;
  try {
    if (isTauri()) {
      const s = await getStore('session.json');
      if (t) await s.set('token', t);
      else await s.delete('token');
      await s.save();
    } else if (t) localStorage.setItem('pl-token', t);
    else localStorage.removeItem('pl-token');
  } catch {
    /* ignore */
  }
  resetUnauthorized();
}

let unauthorizedFired = false;
const listeners = new Set<(reason?: string) => void>();

export function onUnauthorized(cb: (reason?: string) => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function fireUnauthorized(reason?: string) {
  if (unauthorizedFired) return;
  unauthorizedFired = true;
  listeners.forEach((l) => {
    try {
      l(reason);
    } catch {
      /* ignore */
    }
  });
}

export function resetUnauthorized() {
  unauthorizedFired = false;
}
