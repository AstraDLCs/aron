export interface SyncSummary {
  scanned: number;
  uploaded: number;
  duplicates: number;
  blocked: number;
  unmatched: number;
  errors: { path: string; message: string }[];
  error?: string;
}
