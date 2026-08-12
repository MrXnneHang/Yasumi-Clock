use tauri::{AppHandle, Emitter};

use crate::{
    application::{AppEffect, TransitionOutcome},
    domain::{AppSettings, TimerSnapshot},
    tauri_api::commands::SettingsState,
};

use super::{CommandError, window_coordinator};

pub const TIMER_SNAPSHOT_EVENT: &str = "timer://snapshot";
pub const SETTINGS_CHANGED_EVENT: &str = "settings://changed";

pub fn publish_transition(
    app: &AppHandle,
    outcome: &TransitionOutcome,
) -> Result<(), CommandError> {
    for effect in &outcome.effects {
        match effect {
            AppEffect::PublishTimerSnapshot => publish_snapshot(app, &outcome.snapshot)?,
            AppEffect::PublishSettings(settings) => {
                publish_settings(app, settings, outcome.snapshot.revision)?
            }
            AppEffect::ShowRestOverlay
            | AppEffect::HideRestOverlay
            | AppEffect::ShowLastMinuteOverlay
            | AppEffect::HideLastMinuteOverlay => {
                window_coordinator::apply_window_effect(app, effect)
                    .map_err(|error| CommandError::event_publish_failed(error.to_string()))?;
            }
            AppEffect::PersistSettings(_)
            | AppEffect::PersistSessionHistory(_)
            | AppEffect::PlayNotification
            | AppEffect::StartWhiteNoise
            | AppEffect::StopWhiteNoise
            | AppEffect::ArmIdleReminder
            | AppEffect::CancelIdleReminder => {}
        }
    }
    Ok(())
}

pub fn publish_snapshot(app: &AppHandle, snapshot: &TimerSnapshot) -> Result<(), CommandError> {
    app.emit(TIMER_SNAPSHOT_EVENT, snapshot)
        .map_err(|error| CommandError::event_publish_failed(error.to_string()))
}

fn publish_settings(
    app: &AppHandle,
    settings: &AppSettings,
    revision: u64,
) -> Result<(), CommandError> {
    app.emit(
        SETTINGS_CHANGED_EVENT,
        SettingsState {
            settings: settings.clone(),
            revision,
        },
    )
    .map_err(|error| CommandError::event_publish_failed(error.to_string()))
}
