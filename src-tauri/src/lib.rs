pub mod application;
pub mod domain;
pub mod infrastructure;
pub mod tauri_api;

pub fn run() {
    tauri::Builder::default()
        .manage(tauri_api::initial_state())
        .invoke_handler(tauri::generate_handler![
            tauri_api::commands::get_timer_snapshot,
            tauri_api::commands::start_focus_session,
            tauri_api::commands::start_rest_session,
            tauri_api::commands::pause_timer,
            tauri_api::commands::resume_timer,
            tauri_api::commands::end_timer,
            tauri_api::commands::adjust_focus_duration,
            tauri_api::commands::adjust_rest_duration,
            tauri_api::commands::get_settings,
            tauri_api::commands::update_settings,
        ])
        .setup(|app| {
            tauri_api::start_scheduler(app.handle().clone());
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("failed to run Yasumi Clock");
}
