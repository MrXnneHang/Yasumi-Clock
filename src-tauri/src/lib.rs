use tauri::Manager;

pub mod application;
pub mod domain;
pub mod infrastructure;
pub mod media_protocol;
pub mod tauri_api;

pub fn run() {
    let app = tauri::Builder::default()
        .register_uri_scheme_protocol("yasumi-media", |context, request| {
            media_protocol::respond(&context.app_handle().state(), &request)
        })
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            tauri_api::commands::get_timer_snapshot,
            tauri_api::commands::start_focus_session,
            tauri_api::commands::pause_timer,
            tauri_api::commands::resume_timer,
            tauri_api::commands::end_timer,
            tauri_api::commands::end_rest,
            tauri_api::commands::adjust_focus_duration,
            tauri_api::commands::get_settings,
            tauri_api::commands::get_settings_state,
            tauri_api::commands::open_settings_window,
            tauri_api::commands::list_imported_media,
            tauri_api::commands::open_media_folder,
            tauri_api::commands::import_animation_media,
            tauri_api::commands::set_theme_mode,
            tauri_api::commands::update_settings,
        ])
        .setup(|app| {
            let state = tauri_api::initial_state(app).map_err(|error| error.message)?;
            app.manage(state);
            tauri_api::window_coordinator::create_rest_overlay(app)
                .map_err(|error| error.to_string())?;
            tauri_api::window_coordinator::register_main_close_handler(app.handle())
                .map_err(|error| error.to_string())?;
            tauri_api::start_media_watcher(app.handle().clone()).map_err(|error| error.message)?;
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
