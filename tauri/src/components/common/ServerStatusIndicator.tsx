export function ServerStatusIndicator({ online, url }: { online: boolean | null; url: string }) {
  const cls =
    online === null
      ? 'border-[#D4D7DD] bg-white text-[#5C626D]'
      : online
        ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
        : 'border-red-200 bg-red-50 text-red-700';
  const dot = online === null ? 'bg-[#9AA0A8]' : online ? 'bg-emerald-500' : 'bg-red-500';
  return (
    <span title={url} className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold ${cls}`}>
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {online === null ? 'Conectando…' : online ? 'Servidor conectado' : 'Sin conexión con el servidor'}
    </span>
  );
}
