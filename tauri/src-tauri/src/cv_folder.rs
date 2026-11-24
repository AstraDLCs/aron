use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};

const ALLOWED: [&str; 4] = ["pdf", "docx", "txt", "rtf"];
const MAX_SIZE: u64 = 15 * 1024 * 1024;

#[derive(Serialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ScanEntry {
    pub position_folder: String,
    pub source_folder: String,
    pub path: String,
    pub file_name: String,
    pub size: u64,
    pub sha256: String,
    pub extension: String,
}

#[derive(Serialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct SkippedEntry {
    pub path: String,
    pub reason: String,
}

#[derive(Serialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ScanResult {
    pub root_used: String,
    pub entries: Vec<ScanEntry>,
    pub skipped: Vec<SkippedEntry>,
}

fn resolve_root(root: &Path) -> PathBuf {
    if let Ok(rd) = fs::read_dir(root) {
        for e in rd.flatten() {
            if e.path().is_dir() && e.file_name().to_string_lossy().eq_ignore_ascii_case("rrhh") {
                return e.path();
            }
        }
    }
    root.to_path_buf()
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let bytes = fs::read(path).map_err(|e| format!("No se pudo leer {}: {}", path.display(), e))?;
    let mut h = Sha256::new();
    h.update(&bytes);
    Ok(hex::encode(h.finalize()))
}

pub fn scan(root: &str) -> Result<ScanResult, String> {
    let root_path = Path::new(root);
    if !root_path.is_dir() {
        return Err(format!("La carpeta {} no existe o no es accesible", root));
    }
    let used = resolve_root(root_path);
    let mut entries = Vec::new();
    let mut skipped = Vec::new();
    for item in walkdir::WalkDir::new(&used).min_depth(1).into_iter().flatten() {
        if !item.file_type().is_file() {
            continue;
        }
        let p = item.path();
        let path_str = p.to_string_lossy().to_string();
        let file_name = item.file_name().to_string_lossy().to_string();
        if file_name.starts_with("~$") || file_name.starts_with('.') {
            continue;
        }
        if item.depth() != 3 {
            skipped.push(SkippedEntry { path: path_str, reason: "estructura".into() });
            continue;
        }
        let ext = p
            .extension()
            .map(|e| e.to_string_lossy().to_lowercase())
            .unwrap_or_default();
        if !ALLOWED.contains(&ext.as_str()) {
            skipped.push(SkippedEntry { path: path_str, reason: "formato".into() });
            continue;
        }
        let size = item.metadata().map(|m| m.len()).unwrap_or(0);
        if size > MAX_SIZE || size == 0 {
            skipped.push(SkippedEntry { path: path_str, reason: "tamaño".into() });
            continue;
        }
        let source_folder = p
            .parent()
            .and_then(|x| x.file_name())
            .map(|x| x.to_string_lossy().to_string())
            .unwrap_or_default();
        let position_folder = p
            .parent()
            .and_then(|x| x.parent())
            .and_then(|x| x.file_name())
            .map(|x| x.to_string_lossy().to_string())
            .unwrap_or_default();
        let sha = match sha256_file(p) {
            Ok(s) => s,
            Err(_) => {
                skipped.push(SkippedEntry { path: path_str, reason: "formato".into() });
                continue;
            }
        };
        entries.push(ScanEntry {
            position_folder,
            source_folder,
            path: path_str,
            file_name,
            size,
            sha256: sha,
            extension: ext,
        });
    }
    Ok(ScanResult { root_used: used.to_string_lossy().to_string(), entries, skipped })
}

#[tauri::command]
pub async fn scan_cv_folder(root: String) -> Result<ScanResult, String> {
    tauri::async_runtime::spawn_blocking(move || scan(&root))
        .await
        .map_err(|e| e.to_string())?
}

pub fn create_structure(root: &str, folders: &[(String, String)]) -> Result<u32, String> {
    let root_path = Path::new(root);
    if !root_path.exists() {
        fs::create_dir_all(root_path)
            .map_err(|e| format!("La carpeta {} no existe o no es accesible: {}", root, e))?;
    }
    let mut created = 0u32;
    for (position, source) in folders {
        let pos_dir = root_path.join(position);
        if !pos_dir.exists() {
            fs::create_dir_all(&pos_dir).map_err(|e| e.to_string())?;
            created += 1;
        }
        if !source.is_empty() {
            let src_dir = pos_dir.join(source);
            if !src_dir.exists() {
                fs::create_dir_all(&src_dir).map_err(|e| e.to_string())?;
                created += 1;
            }
        }
    }
    Ok(created)
}

#[tauri::command]
pub fn create_folder_structure(root: String, folders: Vec<(String, String)>) -> Result<u32, String> {
    create_structure(&root, &folders)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scan_finds_entries_and_hashes() {
        let d = tempfile::tempdir().unwrap();
        let f = d.path().join("rrhh").join("Perforista").join("LinkedIn");
        fs::create_dir_all(&f).unwrap();
        fs::write(f.join("a.pdf"), b"abc").unwrap();
        let r = scan(d.path().to_str().unwrap()).unwrap();
        assert!(r.root_used.ends_with("rrhh"));
        assert_eq!(r.entries.len(), 1);
        assert_eq!(r.entries[0].position_folder, "Perforista");
        assert_eq!(
            r.entries[0].sha256,
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }

    #[test]
    fn scan_missing_root_errors() {
        assert!(scan("Z:/no/existe/carpeta").is_err());
    }

    #[test]
    fn create_folder_structure_is_idempotent() {
        let d = tempfile::tempdir().unwrap();
        let root = d.path().to_str().unwrap();
        let folders = vec![("P".to_string(), "S".to_string())];
        assert_eq!(create_structure(root, &folders).unwrap(), 2);
        assert_eq!(create_structure(root, &folders).unwrap(), 0);
    }
}
