#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod hardware;
mod sidecar;

use sidecar::SidecarState;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState::default())
        .invoke_handler(tauri::generate_handler![
            commands::check_environment,
            commands::prepare_model,
            commands::send_message,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
