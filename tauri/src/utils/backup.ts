export function parseBackupFile(
  text: string,
): { ok: true; backup: unknown } | { ok: false; error: string } {
  const error = 'El archivo no es un respaldo válido de Pulso Laboral';
  try {
    const v = JSON.parse(text);
    if (v && typeof v === 'object' && v.version === 1 && v.data && typeof v.data === 'object') {
      return { ok: true, backup: v };
    }
    return { ok: false, error };
  } catch {
    return { ok: false, error };
  }
}
