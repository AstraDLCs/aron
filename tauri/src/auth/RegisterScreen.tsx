import { useState, type FormEvent } from 'react';
import { Loader2 } from 'lucide-react';
import { errorMessage } from '../api/client';
import { useAuth } from './AuthProvider';
import { AuthShell, ErrorBox, inputCls, labelCls } from './LoginScreen';

export function RegisterScreen({ onLogin }: { onLogin: () => void }) {
  const { register } = useAuth();
  const [fullName, setFullName] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) return setError('La contraseña debe tener al menos 8 caracteres.');
    if (password !== password2) return setError('Las contraseñas no coinciden.');
    setBusy(true);
    try {
      await register({
        fullName: fullName.trim(),
        email: email.trim(),
        password,
        jobTitle: jobTitle.trim(),
        inviteCode: inviteCode.trim() || undefined,
      });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Crear cuenta" subtitle="Registra tu usuario para acceder al sistema.">
      <ErrorBox msg={error} />
      <form onSubmit={submit} className="space-y-3.5">
        <div>
          <label className={labelCls}>Nombre completo</label>
          <input required autoFocus value={fullName} onChange={(e) => setFullName(e.target.value)} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Cargo</label>
          <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} className={inputCls} placeholder="Ej. Jefe de RR.HH." />
        </div>
        <div>
          <label className={labelCls}>Correo electrónico</label>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>Contraseña</label>
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Repetir</label>
            <input type="password" required value={password2} onChange={(e) => setPassword2(e.target.value)} className={inputCls} />
          </div>
        </div>
        <div>
          <label className={labelCls}>Código de invitación (si te lo pidieron)</label>
          <input value={inviteCode} onChange={(e) => setInviteCode(e.target.value)} className={inputCls} />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#B26337] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#99522B] disabled:opacity-60"
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}Crear cuenta
        </button>
      </form>
      <p className="mt-5 text-center text-sm text-[#5C626D]">
        ¿Ya tienes cuenta?{' '}
        <button type="button" onClick={onLogin} className="font-semibold text-[#B26337] hover:underline">
          Ingresar
        </button>
      </p>
    </AuthShell>
  );
}
