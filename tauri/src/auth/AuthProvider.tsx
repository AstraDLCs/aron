import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { apiFetch, onUnauthorized } from '../api/client';
import { getToken, setToken } from '../api/session';
import type { UserOut } from '../types';

type AuthStatus = 'loading' | 'anonymous' | 'authenticated';

export interface RegisterPayload {
  fullName: string;
  email: string;
  password: string;
  jobTitle: string;
  inviteCode?: string;
}

interface AuthCtx {
  status: AuthStatus;
  user: UserOut | null;
  expiredNotice: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (p: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (u: UserOut) => void;
}

const Ctx = createContext<AuthCtx | null>(null);

type TokenOut = { accessToken: string; user: UserOut };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<UserOut | null>(null);
  const [expiredNotice, setExpiredNotice] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      const t = await getToken();
      if (!t) {
        if (alive) setStatus('anonymous');
        return;
      }
      try {
        const me = await apiFetch<UserOut>('/api/auth/me');
        if (!alive) return;
        setUser(me);
        setStatus('authenticated');
      } catch (e: any) {
        if (!alive) return;
        if (e?.status === 401) await setToken(null);
        // Si no hay conexión, se vuelve al ingreso (allí se muestra el error del servidor).
        setStatus('anonymous');
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(
    () =>
      onUnauthorized((reason) => {
        void setToken(null);
        setUser(null);
        setExpiredNotice(reason ?? 'Tu sesión venció. Vuelve a ingresar.');
        setStatus('anonymous');
      }),
    [],
  );

  const login = useCallback(async (email: string, password: string) => {
    const r = await apiFetch<TokenOut>('/api/auth/login', { method: 'POST', json: { email, password } });
    await setToken(r.accessToken);
    setUser(r.user);
    setExpiredNotice(null);
    setStatus('authenticated');
  }, []);

  const register = useCallback(async (p: RegisterPayload) => {
    const body: Record<string, unknown> = {
      fullName: p.fullName,
      email: p.email,
      password: p.password,
      jobTitle: p.jobTitle,
    };
    if (p.inviteCode) body.inviteCode = p.inviteCode;
    const r = await apiFetch<TokenOut>('/api/auth/register', { method: 'POST', json: body });
    await setToken(r.accessToken);
    setUser(r.user);
    setExpiredNotice(null);
    setStatus('authenticated');
  }, []);

  const logout = useCallback(async () => {
    await setToken(null);
    setUser(null);
    setStatus('anonymous');
  }, []);

  return (
    <Ctx.Provider value={{ status, user, expiredNotice, login, register, logout, setUser }}>{children}</Ctx.Provider>
  );
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useAuth fuera de AuthProvider');
  return c;
}
