use tauri::{AppHandle, State};

use crate::{
    application::TransitionOutcome,
    domain::{AppSettings, TimerSnapshot},
};

use super::{AppState, CommandError, events::publish_transition};

#[tauri::command]
pub async fn get_timer_snapshot(state: State<'_, AppState>) -> Result<TimerSnapshot, CommandError> {
    Ok(state.timer.lock().await.snapshot())
}

#[tauri::command]
pub async fn start_focus_session(
    app: AppHandle,
    state: State<'_, AppState>,
    duration_override_minutes: Option<u32>,
) -> Result<TimerSnapshot, CommandError> {
    mutate(&app, &state, |timer| {
        timer.start_focus(duration_override_minutes)
    })
    .await
}

#[tauri::command]
pub async fn pause_timer(
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<TimerSnapshot, CommandError> {
    mutate(&app, &state, |timer| timer.pause()).await
}

#[tauri::command]
pub async fn resume_timer(
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<TimerSnapshot, CommandError> {
    mutate(&app, &state, |timer| timer.resume()).await
}

#[tauri::command]
pub async fn end_timer(
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<TimerSnapshot, CommandError> {
    mutate(&app, &state, |timer| timer.end()).await
}

#[tauri::command]
pub async fn adjust_focus_duration(
    app: AppHandle,
    state: State<'_, AppState>,
    delta_minutes: i32,
) -> Result<TimerSnapshot, CommandError> {
    mutate(&app, &state, |timer| {
        timer.adjust_focus_duration(delta_minutes)
    })
    .await
}

#[tauri::command]
pub async fn get_settings(state: State<'_, AppState>) -> Result<AppSettings, CommandError> {
    Ok(state.timer.lock().await.settings())
}

#[tauri::command]
pub async fn update_settings(
    app: AppHandle,
    state: State<'_, AppState>,
    settings: AppSettings,
    expected_revision: u64,
) -> Result<TimerSnapshot, CommandError> {
    let outcome = {
        let mut timer = state.timer.lock().await;
        let actual_revision = timer.snapshot().revision;
        if actual_revision != expected_revision {
            return Err(CommandError::stale_revision(
                expected_revision,
                actual_revision,
            ));
        }
        timer
            .update_settings(settings)
            .map_err(CommandError::from)?
    };
    publish_transition(&app, &outcome)?;
    Ok(outcome.snapshot)
}

async fn mutate(
    app: &AppHandle,
    state: &State<'_, AppState>,
    transition: impl FnOnce(
        &mut super::state::RuntimeTimer,
    ) -> Result<TransitionOutcome, crate::domain::DomainError>,
) -> Result<TimerSnapshot, CommandError> {
    let outcome = {
        let mut timer = state.timer.lock().await;
        transition(&mut timer).map_err(CommandError::from)?
    };
    publish_transition(app, &outcome)?;
    Ok(outcome.snapshot)
}
