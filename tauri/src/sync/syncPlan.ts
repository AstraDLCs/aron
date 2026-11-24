import { matchFolder } from './folderMatch';

export interface ScanEntry {
  positionFolder: string;
  sourceFolder: string;
  path: string;
  fileName: string;
  size: number;
  sha256: string;
  extension: string;
}

export interface ScanResult {
  rootUsed: string;
  entries: ScanEntry[];
  skipped: { path: string; reason: string }[];
}

export type MatchedEntry = ScanEntry & { positionId: string; sourceId: string };

export interface UnmatchedFolder {
  folder: string;
  kind: 'puesto' | 'fuente';
  count: number;
}

type Named = { id: string; name: string; folderName: string };

export function planMatches(
  scan: ScanResult,
  positions: Named[],
  sources: Named[],
): { matched: MatchedEntry[]; inScanDuplicates: MatchedEntry[]; unmatchedFolders: UnmatchedFolder[] } {
  const matched: MatchedEntry[] = [];
  const inScanDuplicates: MatchedEntry[] = [];
  const unmatched = new Map<string, UnmatchedFolder>();
  const seen = new Set<string>();
  for (const entry of scan.entries) {
    const position = matchFolder(entry.positionFolder, positions);
    if (!position) {
      const key = `puesto:${entry.positionFolder}`;
      const u = unmatched.get(key) ?? { folder: entry.positionFolder, kind: 'puesto' as const, count: 0 };
      u.count += 1;
      unmatched.set(key, u);
      continue;
    }
    const source = matchFolder(entry.sourceFolder, sources);
    if (!source) {
      const folder = `${entry.positionFolder}/${entry.sourceFolder}`;
      const key = `fuente:${folder}`;
      const u = unmatched.get(key) ?? { folder, kind: 'fuente' as const, count: 0 };
      u.count += 1;
      unmatched.set(key, u);
      continue;
    }
    const m: MatchedEntry = { ...entry, positionId: position.id, sourceId: source.id };
    const dedupeKey = `${entry.sha256.toLowerCase()}|${position.id}`;
    if (seen.has(dedupeKey)) {
      inScanDuplicates.push(m);
    } else {
      seen.add(dedupeKey);
      matched.push(m);
    }
  }
  return { matched, inScanDuplicates, unmatchedFolders: [...unmatched.values()] };
}

export type CheckStatus = 'new' | 'duplicate' | 'deleted_before';

export function finalizePlan(
  matched: MatchedEntry[],
  results: { sha256: string; positionId: string; status: CheckStatus }[],
): { toUpload: MatchedEntry[]; duplicates: MatchedEntry[]; deletedBefore: MatchedEntry[] } {
  const statusOf = new Map(results.map((r) => [`${r.sha256.toLowerCase()}|${r.positionId}`, r.status]));
  const toUpload: MatchedEntry[] = [];
  const duplicates: MatchedEntry[] = [];
  const deletedBefore: MatchedEntry[] = [];
  for (const m of matched) {
    const status = statusOf.get(`${m.sha256.toLowerCase()}|${m.positionId}`) ?? 'new';
    if (status === 'duplicate') duplicates.push(m);
    else if (status === 'deleted_before') deletedBefore.push(m);
    else toUpload.push(m);
  }
  return { toUpload, duplicates, deletedBefore };
}
