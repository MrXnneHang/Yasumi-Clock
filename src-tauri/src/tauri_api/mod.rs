pub mod commands;
mod error;
mod events;
mod state;
pub(crate) mod window_coordinator;

use notify::{Config, Event, RecommendedWatcher, RecursiveMode, Watcher};
use std::{sync::atomic::Ordering, time::Duration};

use tauri::{AppHandle, Manager};

use crate::{
    application::{Clock, FocusTimer},
    domain::TimerState,
    infrastructure::{MediaLibrary, Persistence, SystemClock},
};

pub use error::CommandError;
pub use state::AppState;

pub fn initial_state(app: &tauri::App) -> Result<AppState, CommandError> {
    let config_directory = app.path().app_config_dir().map_err(|error| {
        CommandError::persistence_failed(format!("could not resolve config directory: {error}"))
    })?;
    let data_directory = app.path().app_data_dir().map_err(|error| {
        CommandError::persistence_failed(format!("could not resolve data directory: {error}"))
    })?;
    let persistence = Persistence::new(config_directory, data_directory.clone());
    let media_library = MediaLibrary::new(data_directory);
    let settings = persistence
        .load_settings()
        .map_err(|error| CommandError::persistence_failed(error.to_string()))?;
    let history = persistence
        .load_history()
        .map_err(|error| CommandError::persistence_failed(error.to_string()))?;
    let mut timer = TimerState::new(settings).expect("persisted timer settings are valid");
    let now = SystemClock::new();
    let count = history.daily_completed_focus_count(now.sample().utc_seconds);
    timer.set_daily_completed_focus_count(count);
    Ok(AppState::new(
        FocusTimer::new(timer, now),
        history,
        media_library,
        persistence,
    ))
}

pub fn record_shutdown(app: &AppHandle) {
    let state = app.state::<AppState>();
    if state.shutdown_recorded.swap(true, Ordering::AcqRel) {
        return;
    }
    let Ok(mut timer) = state.timer.try_lock() else {
        eprintln!("skipped shutdown session record because the timer is busy");
        return;
    };
    let checkpoint = timer.checkpoint();
    let Ok(outcome) = timer.end_for_shutdown() else {
        return;
    };
    if let Err(error) = commands::persist_outcome_on_exit(&state, &outcome) {
        timer.restore(checkpoint);
        eprintln!(
            "failed to persist shutdown session record: {}",
            error.message
        );
    }
}

pub fn start_media_watcher(app: AppHandle) -> Result<(), CommandError> {
    let state = app.state::<AppState>();
    let directory = state.media_library.directory().to_path_buf();
    state
        .media_library
        .ensure_directory()
        .map_err(|error| CommandError::persistence_failed(error.to_string()))?;
    let watcher_app = app.clone();
    let mut watcher = RecommendedWatcher::new(
        move |result: Result<Event, notify::Error>| {
            if result.is_err() {
                return;
            }
            let state = watcher_app.state::<AppState>();
            if state.media_reconcile_pending.swap(true, Ordering::AcqRel) {
                return;
            }
            let app = watcher_app.clone();
            tauri::async_runtime::spawn(async move {
                tokio::time::sleep(Duration::from_millis(120)).await;
                let state = app.state::<AppState>();
                let library = state.media_library.clone();
                let change = tauri::async_runtime::spawn_blocking(move || library.reconcile())
                    .await
                    .ok()
                    .and_then(Result::ok);
                if let Some(change) = change {
                    if !change.unavailable_ids.is_empty() {
                        let outcome = {
                            let mut timer = state.timer.lock().await;
                            let checkpoint = timer.checkpoint();
                            let outcome =
                                timer.reconcile_unavailable_media(&change.unavailable_ids);
                            if let Err(error) = commands::persist_outcome(&state, &outcome).await {
                                timer.restore(checkpoint);
                                eprintln!("failed to persist media fallback: {}", error.message);
                                state
                                    .media_reconcile_pending
                                    .store(false, Ordering::Release);
                                return;
                            }
                            outcome
                        };
                        if let Err(error) = events::publish_transition(&app, &outcome) {
                            eprintln!("failed to publish media fallback: {}", error.message);
                        }
                    }
                    if let Err(error) = events::publish_media_library(&app, &change) {
                        eprintln!("failed to publish media library change: {}", error.message);
                    }
                }
                state
                    .media_reconcile_pending
                    .store(false, Ordering::Release);
            });
        },
        Config::default(),
    )
    .map_err(|error| CommandError::persistence_failed(error.to_string()))?;
    watcher
        .watch(&directory, RecursiveMode::NonRecursive)
        .map_err(|error| CommandError::persistence_failed(error.to_string()))?;
    *state
        .media_watcher
        .lock()
        .expect("media watcher lock poisoned") = Some(watcher);
    Ok(())
}

pub fn start_scheduler(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_secs(1));
        interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
        loop {
            interval.tick().await;
            let transition = {
                let state = app.state::<AppState>();
                let mut timer = state.timer.lock().await;
                let checkpoint = timer.checkpoint();
                match timer.reconcile_time() {
                    Ok(Some(mut outcome)) => {
                        if let Err(error) = commands::persist_outcome(&state, &outcome).await {
                            timer.restore(checkpoint);
                            Err(error)
                        } else {
                            let count = state
                                .history
                                .lock()
                                .await
                                .daily_completed_focus_count(timer.current_utc_seconds());
                            timer.set_daily_completed_focus_count(count);
                            outcome.snapshot = timer.snapshot();
                            Ok(Some(outcome))
                        }
                    }
                    Ok(None) => Ok(None),
                    Err(error) => Err(CommandError::from(error)),
                }
            };

            match transition {
                Ok(Some(outcome)) => {
                    if let Err(error) = events::publish_transition(&app, &outcome) {
                        eprintln!("failed to publish timer transition: {}", error.message);
                    }
                }
                Ok(None) => {
                    let state = app.state::<AppState>();
                    let mut timer = state.timer.lock().await;
                    let count = state
                        .history
                        .lock()
                        .await
                        .daily_completed_focus_count(timer.current_utc_seconds());
                    timer.set_daily_completed_focus_count(count);
                    let snapshot = timer.heartbeat_snapshot();
                    if let Err(error) = events::publish_snapshot(&app, &snapshot) {
                        eprintln!("failed to publish timer heartbeat: {}", error.message);
                    }
                }
                Err(error) => {
                    eprintln!("failed to reconcile timer: {}", error.message);
                }
            }
        }
    });
}
