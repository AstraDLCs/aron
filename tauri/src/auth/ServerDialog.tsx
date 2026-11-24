import { useEffect, useState } from 'react';
import { CheckCircle2, Loader2, Server, X, XCircle } from 'lucide-react';
import { DEFAULT_API_BASE_URL, loadConfig, normalizeBaseUrl, saveConfig, validateApiUrl } from '../api/config';

export function ServerDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [url, setUrl] = useState('');
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!open) return;
    setResult(null);
    setSaved(false);
    void loadConfig().then((c) => setUrl(c.apiBaseUrl));
  }, [open]);

  if (!open) return null;

  const test = async () => {
    setTesting(true);
    setResult(null);
    const base = normalizeBaseUrl(url);
    const invalid = validateApiUrl(base);
    if (invalid) {
      setResult({ ok: false, msg: invalid });
      setTesting(false);
      return;
    }
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 6000);
      const res = await fetch(`${base}/api/health`, { signal: ctrl.signal });
      clearTimeout(t);
      if (res.ok) setResult({ ok: true, msg: `Conexión correcta con ${base}` });
      else setResult({ ok: false, msg: `El servidor respondió con error ${res.status} en ${base}/api/health` });
    } catch {
      setResult({ ok: false, msg: `No se pudo conectar con ${base}. Revisa la URL y que la API esté encendida.` });
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    const invalid = validateApiUrl(url);
    if (invalid) {
      setResult({ ok: false, msg: invalid });
      return;
    }
    const c = await saveConfig({ apiBaseUrl: url });
    setUrl(c.apiBaseUrl);
    setSaved(true);
    setTimeout(onClose, 500);
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-[#23272E]/40 p-4">
      <div className="w-full max-w-md rounded-2xl border border-[#E2E4E8] bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Server className="h-5 w-5 text-[#B26337]" />
            <h2 className="font-display text-lg font-bold text-[#23272E]">Servidor de la API</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-[#5C626D] hover:bg-[#EFEFF1]" aria-label="Cerrar">
            <X className="h-4 w-4" />
          </button>
        </div>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[#5C626D]">URL del servidor</label>
        <input
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
            setResult(null);
          }}
          placeholder={DEFAULT_API_BASE_URL}
          className="w-full rounded-lg border border-[#D4D7DD] px-3 py-2 font-mono text-sm outline-none focus:border-[#B26337] focus:ring-2 focus:ring-[#B26337]/20"
        />
        <p className="mt-1 text-xs text-[#5C626D]">Por defecto: {DEFAULT_API_BASE_URL}</p>
        {result && (
          <div
            className={`mt-3 flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${
              result.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-700'
            }`}
          >
            {result.ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0" />}
            <span>{result.msg}</span>
          </div>
        )}
        {saved && <p className="mt-2 text-sm text-emerald-700">Guardado.</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={test}
            disabled={testing}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#D4D7DD] bg-white px-4 py-2 text-sm font-semibold text-[#23272E] hover:bg-[#EFEFF1] disabled:opacity-60"
          >
            {testing && <Loader2 className="h-4 w-4 animate-spin" />}Probar conexión
          </button>
          <button
            type="button"
            onClick={save}
            className="rounded-lg bg-[#B26337] px-4 py-2 text-sm font-semibold text-white hover:bg-[#99522B]"
          >
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}
