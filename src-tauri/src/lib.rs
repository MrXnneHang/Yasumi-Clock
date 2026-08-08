use tauri::Manager;

pub mod application;
pub mod domain;
pub mod infrastructure;
pub mod tauri_api;

pub fn run() {
    let app = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            tauri_api::commands::get_timer_snapshot,
            tauri_api::commands::start_focus_session,
            tauri_api::commands::pause_timer,
            tauri_api::commands::resume_timer,
            tauri_api::commands::end_timer,
            tauri_api::commands::adjust_focus_duration,
            tauri_api::commands::get_settings,
            tauri_api::commands::update_settings,
        ])
        .setup(|app| {
            let state = tauri_api::initial_state(app).map_err(|error| error.message)?;
            app.manage(state);
            tauri_api::start_scheduler(app.handle().clone());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build Yasumi Clock");
    app.run(|app, event| {
        if matches!(event, tauri::RunEvent::ExitRequested { .. }) {
            tauri_api::record_shutdown(app);
        }
    });
}
