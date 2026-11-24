import { useState } from 'react';
import { AlertTriangle, Loader2, Trash2 } from 'lucide-react';
import { apiFetch, errorMessage, type StateResponse } from '../api/client';
import { Modal, inputClass } from './cv/ui';
import { toast } from './common/Toast';
import type { AppState } from '../types';

const CONFIRM_WORD = 'BORRAR';

type WipeResult = StateResponse<{ counts: Record<string, number>; deletedFiles: number; demo: object | null }>;

/** Borrado total de la versión de prueba (atajo Ctrl+Alt+B). El servidor puede desactivarlo con ALLOW_WIPE=false. */
export function WipeDialog({ onClose, onDone }: { onClose: () => void; onDone: (s: AppState) => void }) {
  const [typed, setTyped] = useState('');
  const [reloadDemo, setReloadDemo] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ready = typed.trim() === CONFIRM_WORD && !busy;

  const run = async () => {
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      const r = await apiFetch<WipeResult>('/api/datacenter/wipe', {
        method: 'POST',
        json: { confirm: CONFIRM_WORD, reloadDemo },
      });
      const records = Object.values(r.counts).reduce((a, b) => a + b, 0);
      onDone(r.state);
      toast(
        `Se borraron ${records} registros y ${r.deletedFiles} archivos de CV` +
          (r.demo ? '. Se cargaron de nuevo los datos de demostración.' : '.'),
      );
      onClose();
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  return (
    <Modal
      title="Borrar todos los datos"
      subtitle="Atajo Ctrl + Alt + B. Solo para la versión de prueba."
      onClose={busy ? () => {} : onClose}
      width="max-w-xl"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-lg border border-[#D4D7DD] bg-white px-4 py-2 text-sm font-semibold text-[#23272E] hover:bg-[#EFEFF1] disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => void run()}
            disabled={!ready}
            className="inline-flex items-center gap-1.5 rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:bg-red-300"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            {busy ? 'Borrando…' : 'Borrar todo'}
          </button>
        </>
      }
    >
      <div className="space-y-4 text-sm text-[#23272E]">
        <div className="flex gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-red-800">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <p>
            <strong>Se borran los datos de todos los usuarios del servidor, no solo los tuyos.</strong> No se puede
            deshacer.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <h3 className="mb-1 font-semibold">Se borra</h3>
            <ul className="list-disc space-y-0.5 pl-5 text-[#5C626D]">
              <li>Organigrama, requerimientos y fuentes</li>
              <li>Candidatos, personas y decisiones</li>
              <li>Todos los CV, incluidos los archivos guardados en el servidor</li>
              <li>Pruebas, criterios y conversaciones con la IA</li>
            </ul>
          </div>
          <div>
            <h3 className="mb-1 font-semibold">Se conserva</h3>
            <ul className="list-disc space-y-0.5 pl-5 text-[#5C626D]">
              <li>Las cuentas de usuario</li>
              <li>La bitácora; el borrado queda registrado con tu nombre</li>
              <li>La configuración: modelo de IA y umbral</li>
              <li>Los CV de la carpeta de tu PC. Si vuelves a sincronizar, se suben de nuevo.</li>
            </ul>
          </div>
        </div>

        <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-[#E2E4E8] bg-[#F7F7F8] p-3">
          <input
            type="checkbox"
            checked={reloadDemo}
            onChange={(e) => setReloadDemo(e.target.checked)}
            disabled={busy}
            className="mt-0.5 h-4 w-4 accent-[#B26337]"
          />
          <span>
            Después del borrado, cargar de nuevo los datos de demostración: organigrama, requerimientos, fuentes y
            criterios, sin candidatos.
          </span>
        </label>

        <div>
          <label htmlFor="wipe-confirm" className="mb-1 block font-semibold">
            Para confirmar, escribe {CONFIRM_WORD}
          </label>
          <input
            id="wipe-confirm"
            autoFocus
            autoComplete="off"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void run();
            }}
            disabled={busy}
            className={inputClass}
            placeholder={CONFIRM_WORD}
          />
        </div>

        {error && <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-800">{error}</p>}
      </div>
    </Modal>
  );
}
