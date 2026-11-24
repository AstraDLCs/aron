import { createRoot, type Root } from 'react-dom/client';
import { SyncSummaryDialog } from '../components/cv/SyncSummaryDialog';
import type { SyncSummary } from './runSync';

let host: { root: Root; el: HTMLElement } | null = null;

/** Muestra el detalle de una sincronización desde cualquier lugar (por ejemplo, desde el aviso al abrir la app). */
export function showSyncSummary(summary: SyncSummary): void {
  if (!host) {
    const el = document.createElement('div');
    el.id = 'pulso-sync-summary-host';
    document.body.appendChild(el);
    host = { root: createRoot(el), el };
  }
  const close = () => host?.root.render(null);
  host.root.render(<SyncSummaryDialog summary={summary} onClose={close} />);
}
