use serde::Serialize;
use tauri::{AppHandle, Manager, State, WebviewWindow};
use tauri_plugin_dialog::DialogExt;

use crate::{
    application::{AppEffect, TransitionOutcome},
    domain::{
        AppSettings, DomainError, MediaRef, SessionPhase, TimerAction, TimerSnapshot, TimerStatus,
    },
};

use super::{
    AppState, CommandError, events::publish_transition, window_coordinator::show_settings_window,
};

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SettingsState {
    pub(crate) settings: AppSettings,
    pub(crate) revision: u64,
}

#[tauri::command]
pub async fn get_timer_snapshot(state: State<'_, AppState>) -> Result<TimerSnapshot, CommandError> {
    Ok(state.timer.lock().await.snapshot())
}

#[tauri::command]
pub async fn start_focus_session(
    app: AppHandle,
    state: State<'_, AppState>,
    duration_override_minutes: Option<u32>,
    work_item_id: Option<String>,
) -> Result<TimerSnapshot, CommandError> {
    mutate(&app, &state, |timer| {
        timer.start_focus(duration_override_minutes, work_item_id)
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
pub async fn end_rest(
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<TimerSnapshot, CommandError> {
    mutate(&app, &state, end_running_rest).await
}

pub async fn end_rest_from_overlay_close(app: &AppHandle) -> Result<(), CommandError> {
    let state = app.state::<AppState>();
    match mutate(app, &state, end_running_rest).await {
        Ok(_) => Ok(()),
        Err(error) if error.code == "action_not_allowed" => {
            super::window_coordinator::hide_rest_overlay(app)
                .map_err(|error| CommandError::event_publish_failed(error.to_string()))?;
            Ok(())
        }
        Err(error) => Err(error),
    }
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
pub async fn get_settings_state(state: State<'_, AppState>) -> Result<SettingsState, CommandError> {
    let timer = state.timer.lock().await;
    Ok(SettingsState {
        settings: timer.settings(),
        revision: timer.snapshot().revision,
    })
}

#[tauri::command]
pub fn open_settings_window(app: AppHandle, window: WebviewWindow) -> Result<(), CommandError> {
    if window.label() != "main" {
        return Err(CommandError::action_not_allowed());
    }
    show_settings_window(&app)
        .map(|_| ())
        .map_err(|error| CommandError::event_publish_failed(error.to_string()))
}

#[tauri::command]
pub async fn list_imported_media(
    state: State<'_, AppState>,
) -> Result<Vec<MediaRef>, CommandError> {
    let library = state.media_library.clone();
    tauri::async_runtime::spawn_blocking(move || library.imported_media())
        .await
        .map_err(|_| CommandError::state_unavailable())?
        .map_err(CommandError::from)
}

#[tauri::command]
pub async fn import_animation_media(
    app: AppHandle,
    window: WebviewWindow,
    state: State<'_, AppState>,
) -> Result<Option<MediaRef>, CommandError> {
    if window.label() != "settings" {
        return Err(CommandError::action_not_allowed());
    }
    let selected = tauri::async_runtime::spawn_blocking(move || {
        app.dialog()
            .file()
            .add_filter("MP4 video", &["mp4"])
            .blocking_pick_file()
            .and_then(|file| file.into_path().ok())
    })
    .await
    .map_err(|_| CommandError::state_unavailable())?;
    let Some(source) = selected else {
        return Ok(None);
    };

    let library = state.media_library.clone();
    let media = tauri::async_runtime::spawn_blocking(move || library.import(&source))
        .await
        .map_err(|_| CommandError::state_unavailable())?
        .map_err(CommandError::from)?;
    Ok(Some(media))
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
        if !settings_references_available(&settings, &state) {
            return Err(CommandError::invalid_media_reference());
        }
        let checkpoint = timer.checkpoint();
        let mut outcome = timer
            .update_settings(settings)
            .map_err(CommandError::from)?;
        if let Err(error) = persist_outcome(&state, &outcome).await {
            timer.restore(checkpoint);
            return Err(error);
        }
        outcome.snapshot = timer.snapshot();
        outcome
    };
    publish_transition(&app, &outcome)?;
    Ok(outcome.snapshot)
}

pub async fn persist_outcome(
    state: &AppState,
    outcome: &TransitionOutcome,
) -> Result<(), CommandError> {
    for effect in &outcome.effects {
        match effect {
            AppEffect::PersistSettings(settings) => state
                .persistence
                .save_settings(settings)
                .map_err(|error| CommandError::persistence_failed(error.to_string()))?,
            AppEffect::PersistSessionHistory(batch) => {
                state
                    .persistence
                    .append_history(batch)
                    .map_err(|error| CommandError::persistence_failed(error.to_string()))?;
                state.history.lock().await.append(batch.clone());
            }
            _ => {}
        }
    }
    Ok(())
}

pub fn persist_outcome_on_exit(
    state: &AppState,
    outcome: &TransitionOutcome,
) -> Result<(), CommandError> {
    for effect in &outcome.effects {
        match effect {
            AppEffect::PersistSettings(settings) => state
                .persistence
                .save_settings(settings)
                .map_err(|error| CommandError::persistence_failed(error.to_string()))?,
            AppEffect::PersistSessionHistory(batch) => state
                .persistence
                .append_history(batch)
                .map_err(|error| CommandError::persistence_failed(error.to_string()))?,
            _ => {}
        }
    }
    Ok(())
}

fn settings_references_available(settings: &AppSettings, state: &AppState) -> bool {
    [
        &settings.animations.idle,
        &settings.animations.focus,
        &settings.animations.rest,
    ]
    .into_iter()
    .all(|media| state.media_library.contains(media))
}

fn end_running_rest(
    timer: &mut super::state::RuntimeTimer,
) -> Result<TransitionOutcome, DomainError> {
    let snapshot = timer.snapshot();
    if snapshot.status != TimerStatus::Running || snapshot.phase != Some(SessionPhase::Rest) {
        return Err(DomainError::ActionNotAllowed(TimerAction::End));
    }
    timer.end()
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
        let checkpoint = timer.checkpoint();
        let mut outcome = transition(&mut timer).map_err(CommandError::from)?;
        if let Err(error) = persist_outcome(state.inner(), &outcome).await {
            timer.restore(checkpoint);
            return Err(error);
        }
        let count = state
            .history
            .lock()
            .await
            .daily_completed_focus_count(timer.current_utc_seconds());
        timer.set_daily_completed_focus_count(count);
        outcome.snapshot = timer.snapshot();
        outcome
    };
    publish_transition(app, &outcome)?;
    Ok(outcome.snapshot)
}
