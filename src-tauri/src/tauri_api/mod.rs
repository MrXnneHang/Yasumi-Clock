pub mod commands;
mod error;
mod events;
mod state;

use std::time::Duration;

use tauri::{AppHandle, Manager};

use crate::{
    application::FocusTimer,
    domain::{AppSettings, TimerState},
    infrastructure::SystemClock,
};

pub use error::CommandError;
pub use state::AppState;

pub fn initial_state() -> AppState {
    let settings = AppSettings::defaults();
    let timer = TimerState::new(settings).expect("built-in timer settings are valid");
    AppState::new(FocusTimer::new(timer, SystemClock::new()))
}

pub fn start_scheduler(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_secs(1));
        interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
        loop {
            interval.tick().await;
            let (transition, snapshot) = {
                let state = app.state::<AppState>();
                let mut timer = state.timer.lock().await;
                let transition = timer.reconcile_time();
                let snapshot = timer.heartbeat_snapshot();
                (transition, snapshot)
            };

            match transition {
                Ok(Some(outcome)) => {
                    if let Err(error) = events::publish_transition(&app, &outcome) {
                        eprintln!("failed to publish timer transition: {}", error.message);
                    }
                }
                Ok(None) => {
                    if let Err(error) = events::publish_snapshot(&app, &snapshot) {
                        eprintln!("failed to publish timer heartbeat: {}", error.message);
                    }
                }
                Err(error) => {
                    let error = CommandError::from(error);
                    eprintln!("failed to reconcile timer: {}", error.message);
                }
            }
        }
    });
}
