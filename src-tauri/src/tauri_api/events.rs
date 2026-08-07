use tauri::{AppHandle, Emitter};

use crate::{
    application::{AppEffect, TransitionOutcome},
    domain::{AppSettings, TimerSnapshot},
};

use super::CommandError;

pub const TIMER_SNAPSHOT_EVENT: &str = "timer://snapshot";
pub const SETTINGS_CHANGED_EVENT: &str = "settings://changed";

pub fn publish_transition(
    app: &AppHandle,
    outcome: &TransitionOutcome,
) -> Result<(), CommandError> {
    for effect in &outcome.effects {
        match effect {
            AppEffect::PublishTimerSnapshot => publish_snapshot(app, &outcome.snapshot)?,
            AppEffect::PublishSettings(settings) => publish_settings(app, settings)?,
            AppEffect::PersistRuntimeState
            | AppEffect::AppendSessionRecord(_)
            | AppEffect::ShowRestOverlay
            | AppEffect::HideRestOverlay
            | AppEffect::ShowLastMinuteOverlay
            | AppEffect::HideLastMinuteOverlay
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
    app.emit_to("main", TIMER_SNAPSHOT_EVENT, snapshot)
        .map_err(|error| CommandError::event_publish_failed(error.to_string()))
}

fn publish_settings(app: &AppHandle, settings: &AppSettings) -> Result<(), CommandError> {
    app.emit_to("main", SETTINGS_CHANGED_EVENT, settings)
        .map_err(|error| CommandError::event_publish_failed(error.to_string()))
}
