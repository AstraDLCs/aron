/** Misma regla que `normalize_key` de Python: NFD, sin tildes, minúsculas y todo lo que no es [a-z0-9] → '-'. */
export function normalizeKey(value: string): string {
  return (value ?? '')
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** Igual que `folder_name_for` de Python (máximo 80 caracteres). */
export function folderNameFor(value: string): string {
  return normalizeKey(value).slice(0, 80).replace(/^-+|-+$/g, '');
}

/** Busca el elemento cuya carpeta (`folderName`) o nombre coincide, ignorando mayúsculas, tildes y espacios. */
export function matchFolder<T extends { id: string; name: string; folderName: string }>(
  folder: string,
  items: T[],
): T | null {
  const key = normalizeKey(folder);
  if (!key) return null;
  return (
    items.find((i) => normalizeKey(i.folderName) === key) ?? items.find((i) => normalizeKey(i.name) === key) ?? null
  );
}
