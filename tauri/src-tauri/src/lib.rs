mod cv_folder;
mod files;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            cv_folder::scan_cv_folder,
            cv_folder::create_folder_structure,
            files::save_file,
            files::open_temp_file,
            files::open_path,
            files::read_file_bytes,
        ])
        .run(tauri::generate_context!())
        .expect("error al iniciar Pulso Laboral");
}
