use percent_encoding::percent_decode_str;
use std::fs;
use std::path::PathBuf;
use tauri::ipc::{InvokeBody, Request, Response};
use tauri_plugin_opener::OpenerExt;

fn header(request: &Request, name: &str) -> Result<String, String> {
    let raw = request
        .headers()
        .get(name)
        .ok_or_else(|| format!("Falta el encabezado {}", name))?
        .to_str()
        .map_err(|e| e.to_string())?;
    Ok(percent_decode_str(raw).decode_utf8_lossy().to_string())
}

fn body_bytes(request: &Request) -> Result<Vec<u8>, String> {
    match request.body() {
        InvokeBody::Raw(b) => Ok(b.clone()),
        InvokeBody::Json(v) => {
            // Fallback: array of numbers
            serde_json::from_value::<Vec<u8>>(v.clone()).map_err(|_| "Cuerpo inválido".to_string())
        }
    }
}

#[tauri::command]
pub fn save_file(request: Request<'_>) -> Result<(), String> {
    let path = header(&request, "x-path")?;
    let bytes = body_bytes(&request)?;
    fs::write(&path, bytes).map_err(|e| format!("No se pudo guardar {}: {}", path, e))
}

const OPENABLE: [&str; 8] = ["pdf", "docx", "doc", "txt", "rtf", "xlsx", "xls", "csv"];

fn openable(path: &std::path::Path) -> bool {
    path.extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .map(|e| OPENABLE.contains(&e.as_str()))
        .unwrap_or(false)
}

const NOT_ALLOWED: &str = "Tipo de archivo no permitido para abrir";

fn sanitize(name: &str) -> String {
    let cleaned: String = name
        .chars()
        .map(|c| if "<>:\"/\\|?*".contains(c) || c.is_control() { '_' } else { c })
        .collect();
    if cleaned.trim().is_empty() {
        "archivo".to_string()
    } else {
        cleaned
    }
}

#[tauri::command]
pub fn open_temp_file(app: tauri::AppHandle, request: Request<'_>) -> Result<String, String> {
    let name = sanitize(&header(&request, "x-file-name")?);
    if !openable(std::path::Path::new(&name)) {
        return Err(NOT_ALLOWED.to_string());
    }
    let bytes = body_bytes(&request)?;
    let dir: PathBuf = std::env::temp_dir().join("pulso-laboral");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let path = dir.join(name);
    fs::write(&path, bytes).map_err(|e| format!("No se pudo escribir el archivo temporal: {}", e))?;
    let p = path.to_string_lossy().to_string();
    app.opener()
        .open_path(p.clone(), None::<&str>)
        .map_err(|e| format!("No se pudo abrir el archivo: {}", e))?;
    Ok(p)
}

#[tauri::command]
pub fn open_path(app: tauri::AppHandle, path: String) -> Result<(), String> {
    let p = std::path::Path::new(&path);
    // Las carpetas se pueden abrir (Explorador); los archivos solo si son documentos permitidos.
    if !p.is_dir() && !openable(p) {
        return Err(NOT_ALLOWED.to_string());
    }
    app.opener()
        .open_path(path.clone(), None::<&str>)
        .map_err(|e| format!("No se pudo abrir {}: {}", path, e))
}

#[tauri::command]
pub fn read_file_bytes(path: String) -> Result<Response, String> {
    let bytes = fs::read(&path).map_err(|e| format!("No se pudo leer {}: {}", path, e))?;
    Ok(Response::new(bytes))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn only_documents_are_openable() {
        assert!(openable(std::path::Path::new("CV José.PDF")));
        assert!(openable(std::path::Path::new("a.xlsx")));
        assert!(!openable(std::path::Path::new("x.exe")));
        assert!(!openable(std::path::Path::new("x.bat")));
        assert!(!openable(std::path::Path::new("x.lnk")));
        assert!(!openable(std::path::Path::new("sinextension")));
    }
}
