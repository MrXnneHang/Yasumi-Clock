pub mod commands;
mod error;
mod events;
mod state;
mod window_coordinator;

use std::time::Duration;

use tauri::{AppHandle, Manager};

use crate::{
    application::{Clock, FocusTimer},
    domain::TimerState,
    infrastructure::{Persistence, SystemClock},
};

pub use error::CommandError;
pub use state::AppState;

pub fn initial_state(app: &tauri::App) -> Result<AppState, CommandError> {
    let persistence = Persistence::new(
        app.path().app_config_dir().map_err(|error| {
            CommandError::persistence_failed(format!("could not resolve config directory: {error}"))
        })?,
        app.path().app_data_dir().map_err(|error| {
            CommandError::persistence_failed(format!("could not resolve data directory: {error}"))
        })?,
    );
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
        persistence,
    ))
}

pub fn record_shutdown(app: &AppHandle) {
    let state = app.state::<AppState>();
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
