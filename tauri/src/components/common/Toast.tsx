import { useEffect, useState } from 'react';
import { CheckCircle2, AlertCircle, X } from 'lucide-react';

export type ToastMsg = { id: number; kind: 'ok' | 'error'; text: string; action?: { label: string; run: () => void } };

let push: ((t: Omit<ToastMsg, 'id'>) => void) | null = null;
let seq = 1;

export function toast(text: string, kind: 'ok' | 'error' = 'ok', action?: ToastMsg['action']) {
  push?.({ kind, text, action });
}

export function ToastHost() {
  const [items, setItems] = useState<ToastMsg[]>([]);
  useEffect(() => {
    push = (t) => {
      const id = seq++;
      setItems((prev) => [...prev, { ...t, id }]);
      setTimeout(() => setItems((prev) => prev.filter((x) => x.id !== id)), t.kind === 'error' ? 9000 : 6000);
    };
    return () => {
      push = null;
    };
  }, []);
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[80] flex w-[380px] max-w-[calc(100vw-2rem)] flex-col gap-2">
      {items.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto flex items-start gap-2 rounded-xl border bg-white px-4 py-3 text-sm shadow-lg ${
            t.kind === 'ok' ? 'border-emerald-200' : 'border-red-200'
          }`}
        >
          {t.kind === 'ok' ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          ) : (
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
          )}
          <div className="min-w-0 flex-1 break-words text-[#23272E]">
            {t.text}
            {t.action && (
              <button type="button" onClick={t.action.run} className="ml-2 font-semibold text-[#B26337] hover:underline">
                {t.action.label}
              </button>
            )}
          </div>
          <button type="button" onClick={() => setItems((p) => p.filter((x) => x.id !== t.id))} className="text-[#5C626D]" aria-label="Cerrar">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
