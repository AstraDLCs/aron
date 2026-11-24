export type AuditFilters = {
  userId?: string;
  action?: string;
  entityType?: string;
  entityId?: string;
  dateFrom?: string; // YYYY-MM-DD (día local)
  dateTo?: string; // YYYY-MM-DD (día local)
  q?: string;
  offset?: number;
};

function localDayBoundary(ymd: string, end: boolean): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(ymd);
  if (!m) return null;
  const d = end
    ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 23, 59, 59, 999)
    : new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 0, 0, 0, 0);
  return d.toISOString();
}

/** Arma la consulta de `/api/audit`: omite los campos vacíos y convierte las fechas locales a un rango UTC. */
export function buildAuditQuery(f: AuditFilters, limit = 100): string {
  const parts: string[] = [];
  const add = (k: string, v: string | undefined | null) => {
    if (v != null && String(v).trim() !== '') parts.push(`${k}=${encodeURIComponent(String(v).trim())}`);
  };
  add('userId', f.userId);
  add('action', f.action);
  add('entityType', f.entityType);
  add('entityId', f.entityId);
  if (f.dateFrom) add('dateFrom', localDayBoundary(f.dateFrom, false));
  if (f.dateTo) add('dateTo', localDayBoundary(f.dateTo, true));
  add('q', f.q);
  parts.push(`limit=${limit}`);
  if (f.offset) parts.push(`offset=${f.offset}`);
  return parts.join('&');
}
