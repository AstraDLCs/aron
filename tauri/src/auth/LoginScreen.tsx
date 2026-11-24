import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { AlertCircle, Loader2, Server } from 'lucide-react';
import { errorMessage } from '../api/client';
import { loadConfig } from '../api/config';
import { useAuth } from './AuthProvider';
import { ServerDialog } from './ServerDialog';

export const inputCls =
  'w-full rounded-lg border border-[#D4D7DD] bg-white px-3 py-2.5 text-sm outline-none transition focus:border-[#B26337] focus:ring-2 focus:ring-[#B26337]/20';
export const labelCls = 'mb-1 block text-xs font-semibold uppercase tracking-wide text-[#5C626D]';

export function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  const [serverOpen, setServerOpen] = useState(false);
  const [apiUrl, setApiUrl] = useState('');
  useEffect(() => {
    void loadConfig().then((c) => setApiUrl(c.apiBaseUrl));
  }, [serverOpen]);
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#F7F7F8] px-4 py-10">
      <div className="mb-6 text-center">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#B26337] font-display text-xl font-extrabold text-white shadow-md">
          PL
        </div>
        <h1 className="font-display text-2xl font-extrabold tracking-tight text-[#23272E]">Pulso Laboral</h1>
        <p className="text-sm text-[#5C626D]">Reclutamiento y selección de personal</p>
      </div>
      <div className="w-full max-w-md rounded-2xl border border-[#E2E4E8] bg-white p-7 shadow-sm">
        <h2 className="font-display text-xl font-bold text-[#23272E]">{title}</h2>
        <p className="mb-5 text-sm text-[#5C626D]">{subtitle}</p>
        {children}
      </div>
      <button
        type="button"
        onClick={() => setServerOpen(true)}
        className="mt-5 inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-[#5C626D] hover:bg-[#EFEFF1] hover:text-[#23272E]"
      >
        <Server className="h-3.5 w-3.5" />
        Servidor: <span className="font-mono">{apiUrl}</span>
      </button>
      <ServerDialog open={serverOpen} onClose={() => setServerOpen(false)} />
    </div>
  );
}

export function ErrorBox({ msg }: { msg: string | null }) {
  if (!msg) return null;
  return (
    <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{msg}</span>
    </div>
  );
}

export function LoginScreen({ onRegister }: { onRegister: () => void }) {
  const { login, expiredNotice } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Ingresar" subtitle="Usa tu cuenta de Pulso Laboral para continuar.">
      {expiredNotice && !error && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">{expiredNotice}</div>
      )}
      <ErrorBox msg={error} />
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className={labelCls}>Correo electrónico</label>
          <input type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} placeholder="nombre@empresa.com" />
        </div>
        <div>
          <label className={labelCls}>Contraseña</label>
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#B26337] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#99522B] disabled:opacity-60"
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}Ingresar
        </button>
      </form>
      <p className="mt-5 text-center text-sm text-[#5C626D]">
        ¿No tienes cuenta?{' '}
        <button type="button" onClick={onRegister} className="font-semibold text-[#B26337] hover:underline">
          Crear una cuenta
        </button>
      </p>
    </AuthShell>
  );
}
