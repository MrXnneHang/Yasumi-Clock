use crate::domain::{
    AppSettings, CompletedSession, SessionEndReason, SessionHistoryBatch, SessionMetadata,
    settings::validate_focus_duration,
};
use uuid::Uuid;

use super::model::{
    DomainError, DomainEvent, SessionPhase, TimeSample, TimerAction, TimerState, TimerStatus,
    focus_duration_seconds, rest_duration_minutes,
};

impl TimerState {
    pub fn set_theme_mode(&mut self, theme_mode: crate::domain::ThemeMode) -> Vec<DomainEvent> {
        if self.settings.theme_mode == theme_mode {
            return Vec::new();
        }
        self.settings.theme_mode = theme_mode;
        self.bump_revision();
        vec![
            DomainEvent::SettingsChanged(self.settings.clone()),
            DomainEvent::SnapshotChanged,
        ]
    }

    pub fn update_settings(
        &mut self,
        settings: AppSettings,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::ChangeSettings)?;
        settings.validate().map_err(DomainError::InvalidSettings)?;
        self.settings = settings.clone();
        self.bump_revision();
        Ok(vec![
            DomainEvent::SettingsChanged(settings),
            DomainEvent::SnapshotChanged,
        ])
    }

    pub fn reconcile_unavailable_media(&mut self, unavailable_ids: &[String]) -> Vec<DomainEvent> {
        let mut settings = self.settings.clone();
        let unavailable = |media: &crate::domain::MediaRef| matches!(media, crate::domain::MediaRef::Imported { id } if unavailable_ids.contains(id));
        if unavailable(&settings.animations.idle) {
            settings.animations.idle = crate::domain::MediaRef::Builtin {
                id: crate::domain::BuiltinMediaId::Play,
            };
        }
        if unavailable(&settings.animations.focus) {
            settings.animations.focus = crate::domain::MediaRef::Builtin {
                id: crate::domain::BuiltinMediaId::Work,
            };
        }
        if unavailable(&settings.animations.rest) {
            settings.animations.rest = crate::domain::MediaRef::Builtin {
                id: crate::domain::BuiltinMediaId::Mayi,
            };
        }
        if settings == self.settings {
            return Vec::new();
        }
        self.settings = settings.clone();
        self.bump_revision();
        vec![
            DomainEvent::SettingsChanged(settings),
            DomainEvent::SnapshotChanged,
        ]
    }

    pub fn start_focus(
        &mut self,
        now: TimeSample,
        duration_override_minutes: Option<u32>,
        work_item_id: Option<String>,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::StartFocus)?;
        let minutes = duration_override_minutes.unwrap_or(self.settings.focus_duration_minutes);
        validate_focus_duration(minutes).map_err(DomainError::InvalidSettings)?;
        let settings_changed = self.settings.focus_duration_minutes != minutes;
        if settings_changed {
            self.settings.focus_duration_minutes = minutes;
        }
        self.begin_session(
            SessionPhase::Focus,
            focus_duration_seconds(minutes),
            now,
            work_item_id,
            None,
        );
        let started = self
            .active_session
            .as_ref()
            .expect("new focus session is active")
            .started_event();
        self.bump_revision();
        self.validate()?;
        let mut events = vec![DomainEvent::SessionHistory(SessionHistoryBatch::new(vec![
            started,
        ]))];
        if settings_changed {
            events.push(DomainEvent::SettingsChanged(self.settings.clone()));
        }
        events.push(DomainEvent::SnapshotChanged);
        Ok(events)
    }

    pub fn pause(&mut self, now: TimeSample) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::Pause)?;
        let remaining = self
            .deadline_monotonic_seconds
            .ok_or(DomainError::InvalidState)?
            .saturating_sub(now.monotonic_seconds);
        self.status = TimerStatus::Paused;
        self.deadline_monotonic_seconds = None;
        self.deadline_utc_seconds = None;
        self.paused_remaining_seconds = Some(remaining);
        self.paused_at_monotonic_seconds = Some(now.monotonic_seconds);
        if let Some(session) = &mut self.active_session {
            session.pause_count = session.pause_count.saturating_add(1);
        }
        self.bump_revision();
        self.validate()?;
        Ok(vec![DomainEvent::SnapshotChanged])
    }

    pub fn resume(&mut self, now: TimeSample) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::Resume)?;
        let remaining = self
            .paused_remaining_seconds
            .take()
            .ok_or(DomainError::InvalidState)?;
        let paused_at = self
            .paused_at_monotonic_seconds
            .take()
            .ok_or(DomainError::InvalidState)?;
        let paused_seconds = now.monotonic_seconds.saturating_sub(paused_at);
        if let Some(session) = &mut self.active_session {
            session.accumulated_pause_seconds = session
                .accumulated_pause_seconds
                .saturating_add(paused_seconds);
        }
        self.status = TimerStatus::Running;
        self.deadline_monotonic_seconds = Some(now.monotonic_seconds.saturating_add(remaining));
        self.deadline_utc_seconds = Some(add_utc(now.utc_seconds, remaining));
        self.bump_revision();
        self.validate()?;
        Ok(vec![DomainEvent::SnapshotChanged])
    }

    pub fn end(&mut self, now: TimeSample) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::End)?;
        let was_rest = self.phase == Some(SessionPhase::Rest);
        let ended = self
            .end_active_session(now.utc_seconds, SessionEndReason::Ended)
            .ok_or(DomainError::InvalidState)?;
        let mut events = vec![DomainEvent::SessionHistory(SessionHistoryBatch::new(vec![
            ended.history_event(),
        ]))];
        self.return_to_idle();
        self.bump_revision();
        if was_rest {
            events.push(DomainEvent::RestEnded);
        }
        events.push(DomainEvent::SnapshotChanged);
        self.validate()?;
        Ok(events)
    }

    pub fn adjust_focus_duration(
        &mut self,
        delta_minutes: i32,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::AdjustFocusDuration)?;
        let adjusted = adjusted_minutes(self.settings.focus_duration_minutes, delta_minutes)
            .ok_or(DomainError::InvalidSettings(
                crate::domain::SettingsError::InvalidFocusDuration,
            ))?;
        validate_focus_duration(adjusted).map_err(DomainError::InvalidSettings)?;
        self.settings.focus_duration_minutes = adjusted;
        self.bump_revision();
        Ok(vec![
            DomainEvent::SettingsChanged(self.settings.clone()),
            DomainEvent::SnapshotChanged,
        ])
    }

    pub fn reconcile_time(&mut self, now: TimeSample) -> Result<Vec<DomainEvent>, DomainError> {
        if self.status != TimerStatus::Running {
            return Ok(Vec::new());
        }
        let deadline = self
            .deadline_monotonic_seconds
            .ok_or(DomainError::InvalidState)?;
        if now.monotonic_seconds < deadline {
            return Ok(Vec::new());
        }

        match self.phase.ok_or(DomainError::InvalidState)? {
            SessionPhase::Focus => self.complete_focus(deadline, now),
            SessionPhase::Rest => {
                let completed = self
                    .end_active_session_at_deadline(SessionEndReason::Completed)
                    .ok_or(DomainError::InvalidState)?;
                self.return_to_idle();
                self.bump_revision();
                let events = vec![
                    DomainEvent::SessionHistory(SessionHistoryBatch::new(vec![
                        completed.history_event(),
                    ])),
                    DomainEvent::RestEnded,
                    DomainEvent::SnapshotChanged,
                ];
                self.validate()?;
                Ok(events)
            }
        }
    }

    fn complete_focus(
        &mut self,
        focus_deadline_monotonic: u64,
        now: TimeSample,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        let focus_deadline_utc = self.deadline_utc_seconds.ok_or(DomainError::InvalidState)?;
        let completed_focus = self
            .end_active_session_at_deadline(SessionEndReason::Completed)
            .ok_or(DomainError::InvalidState)?;

        let focus_minutes = if completed_focus.metadata.planned_duration_seconds == 1 {
            0
        } else {
            u32::try_from(completed_focus.metadata.planned_duration_seconds / 60)
                .expect("validated focus duration fits in u32")
        };
        let rest_seconds = u64::from(rest_duration_minutes(focus_minutes)) * 60;
        let rest_deadline_monotonic = focus_deadline_monotonic.saturating_add(rest_seconds);
        let rest_deadline_utc = add_utc(focus_deadline_utc, rest_seconds);
        let rest = SessionMetadata {
            session_id: Uuid::new_v4().to_string(),
            work_item_id: completed_focus.metadata.work_item_id.clone(),
            origin_session_id: Some(completed_focus.metadata.session_id.clone()),
            phase: SessionPhase::Rest,
            planned_duration_seconds: rest_seconds,
            started_at_utc_seconds: focus_deadline_utc,
            accumulated_pause_seconds: 0,
            pause_count: 0,
        };
        let mut history = vec![completed_focus.history_event(), rest.started_event()];
        self.active_session = Some(rest);

        let mut events = Vec::new();
        if now.monotonic_seconds >= rest_deadline_monotonic {
            let completed_rest = self
                .end_active_session(rest_deadline_utc, SessionEndReason::Completed)
                .ok_or(DomainError::InvalidState)?;
            history.push(completed_rest.history_event());
            self.return_to_idle();
            events.push(DomainEvent::RestEnded);
        } else {
            self.status = TimerStatus::Running;
            self.phase = Some(SessionPhase::Rest);
            self.deadline_monotonic_seconds = Some(rest_deadline_monotonic);
            self.deadline_utc_seconds = Some(rest_deadline_utc);
            self.paused_remaining_seconds = None;
            self.paused_at_monotonic_seconds = None;
            events.push(DomainEvent::RestStarted);
        }

        self.bump_revision();
        events.insert(
            0,
            DomainEvent::SessionHistory(SessionHistoryBatch::new(history)),
        );
        events.push(DomainEvent::SnapshotChanged);
        self.validate()?;
        Ok(events)
    }

    fn begin_session(
        &mut self,
        phase: SessionPhase,
        duration_seconds: u64,
        now: TimeSample,
        work_item_id: Option<String>,
        origin_session_id: Option<String>,
    ) {
        self.status = TimerStatus::Running;
        self.phase = Some(phase);
        self.deadline_monotonic_seconds =
            Some(now.monotonic_seconds.saturating_add(duration_seconds));
        self.deadline_utc_seconds = Some(add_utc(now.utc_seconds, duration_seconds));
        self.paused_remaining_seconds = None;
        self.paused_at_monotonic_seconds = None;
        self.active_session = Some(SessionMetadata {
            session_id: Uuid::new_v4().to_string(),
            work_item_id,
            origin_session_id,
            phase,
            planned_duration_seconds: duration_seconds,
            started_at_utc_seconds: now.utc_seconds,
            accumulated_pause_seconds: 0,
            pause_count: 0,
        });
    }

    fn end_active_session_at_deadline(
        &mut self,
        reason: SessionEndReason,
    ) -> Option<CompletedSession> {
        let ended_at = self.deadline_utc_seconds.unwrap_or_default();
        self.end_active_session(ended_at, reason)
    }

    fn end_active_session(
        &mut self,
        ended_at_utc_seconds: i64,
        reason: SessionEndReason,
    ) -> Option<CompletedSession> {
        self.active_session.take().map(|metadata| CompletedSession {
            metadata,
            ended_at_utc_seconds,
            reason,
        })
    }

    fn return_to_idle(&mut self) {
        self.status = TimerStatus::Idle;
        self.phase = None;
        self.deadline_monotonic_seconds = None;
        self.deadline_utc_seconds = None;
        self.paused_remaining_seconds = None;
        self.paused_at_monotonic_seconds = None;
        self.active_session = None;
    }

    fn require_action(&self, action: TimerAction) -> Result<(), DomainError> {
        if self.allowed_actions().contains(&action) {
            Ok(())
        } else {
            Err(DomainError::ActionNotAllowed(action))
        }
    }

    fn bump_revision(&mut self) {
        self.revision = self.revision.saturating_add(1);
    }
}

fn adjusted_minutes(current: u32, delta: i32) -> Option<u32> {
    let adjusted = i32::try_from(current).ok()?.checked_add(delta)?;
    u32::try_from(adjusted).ok()
}

fn add_utc(utc_seconds: i64, duration_seconds: u64) -> i64 {
    utc_seconds.saturating_add(i64::try_from(duration_seconds).unwrap_or(i64::MAX))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::domain::{TimerAction, TimerSnapshot};

    fn state() -> TimerState {
        TimerState::new(AppSettings::defaults()).unwrap()
    }

    fn now(seconds: u64) -> TimeSample {
        TimeSample::new(seconds, 1_700_000_000 + i64::try_from(seconds).unwrap())
    }

    #[test]
    fn starts_pauses_resumes_and_ends_focus_without_starting_rest() {
        let mut timer = state();
        timer.progress.daily_completed_focus_count = 7;
        timer.start_focus(now(10), None, None).unwrap();
        timer.pause(now(70)).unwrap();
        assert_eq!(timer.snapshot(1_000).remaining_seconds, 19 * 60);
        timer.resume(now(170)).unwrap();
        assert_eq!(timer.deadline_monotonic_seconds, Some(1_310));

        let events = timer.end(now(200)).unwrap();
        assert!(!events.contains(&DomainEvent::RestStarted));
        assert_eq!(timer.status, TimerStatus::Idle);
        assert_eq!(timer.progress.daily_completed_focus_count, 7);
    }

    #[test]
    fn zero_minute_focus_runs_for_one_second_then_starts_five_minute_rest() {
        let mut timer = state();
        let started = timer
            .start_focus(now(0), Some(0), Some("todo-1".into()))
            .unwrap();
        let focus_session_id = started
            .iter()
            .find_map(|event| match event {
                DomainEvent::SessionHistory(batch) => {
                    batch.events.iter().find_map(|event| match event {
                        crate::domain::SessionHistoryEvent::Started { session_id, .. } => {
                            Some(session_id.clone())
                        }
                        _ => None,
                    })
                }
                _ => None,
            })
            .expect("focus start emits a session ID");
        assert_eq!(timer.deadline_monotonic_seconds, Some(1));

        let events = timer.reconcile_time(now(1)).unwrap();
        assert!(events.contains(&DomainEvent::RestStarted));
        assert_eq!(timer.phase, Some(SessionPhase::Rest));
        assert_eq!(timer.snapshot(1).remaining_seconds, 5 * 60);
        let history = events
            .iter()
            .find_map(|event| match event {
                DomainEvent::SessionHistory(batch) => Some(&batch.events),
                _ => None,
            })
            .expect("focus completion emits a history batch");
        assert!(
            history
                .iter()
                .any(|event| matches!(event, crate::domain::SessionHistoryEvent::Completed { .. }))
        );
        let rest_started = history
            .iter()
            .find_map(|event| match event {
                crate::domain::SessionHistoryEvent::Started {
                    work_item_id,
                    origin_session_id,
                    phase: SessionPhase::Rest,
                    ..
                } => Some((work_item_id, origin_session_id)),
                _ => None,
            })
            .expect("focus completion starts rest history");
        assert_eq!(rest_started.0.as_deref(), Some("todo-1"));
        assert_eq!(rest_started.1.as_deref(), Some(focus_session_id.as_str()));
        let session = timer.active_session.as_ref().unwrap();
        assert_eq!(session.planned_duration_seconds, 5 * 60);
        assert_eq!(session.started_at_utc_seconds, now(1).utc_seconds);
    }

    #[test]
    fn unavailable_imported_media_reverts_each_animation_slot_to_its_builtin() {
        let mut timer = state();
        let unavailable = "59db2ea1-7f57-4e5d-8704-99d00688ff11".to_owned();
        let imported = crate::domain::MediaRef::Imported {
            id: unavailable.clone(),
        };
        timer.settings.animations.idle = imported.clone();
        timer.settings.animations.focus = imported.clone();
        timer.settings.animations.rest = imported;

        let events = timer.reconcile_unavailable_media(&[unavailable]);

        assert!(
            events
                .iter()
                .any(|event| matches!(event, DomainEvent::SettingsChanged(_)))
        );
        assert_eq!(
            timer.settings.animations,
            crate::domain::AnimationSettings::defaults()
        );
    }

    #[test]
    fn completed_focus_starts_derived_rest_and_rest_completion_returns_idle() {
        let mut timer = state();
        let started = timer.start_focus(now(0), Some(26), None).unwrap();
        assert_eq!(timer.settings.focus_duration_minutes, 26);
        assert!(
            started
                .iter()
                .any(|event| matches!(event, DomainEvent::SettingsChanged(_)))
        );
        let events = timer.reconcile_time(now(26 * 60)).unwrap();
        assert!(events.contains(&DomainEvent::RestStarted));
        assert_eq!(timer.phase, Some(SessionPhase::Rest));
        assert_eq!(timer.snapshot(26 * 60).remaining_seconds, 6 * 60);

        let events = timer.reconcile_time(now(32 * 60)).unwrap();
        assert!(events.contains(&DomainEvent::RestEnded));
        assert_eq!(timer.status, TimerStatus::Idle);
        assert_eq!(timer.phase, None);
        assert_eq!(timer.snapshot(32 * 60).remaining_seconds, 26 * 60);
        assert_eq!(timer.progress.daily_completed_focus_count, 0);
    }

    #[test]
    fn delayed_tick_consumes_rest_overrun_without_starting_an_expired_rest() {
        let mut timer = state();
        timer.start_focus(now(0), Some(25), None).unwrap();
        timer.reconcile_time(now(27 * 60)).unwrap();
        assert_eq!(timer.phase, Some(SessionPhase::Rest));
        assert_eq!(timer.snapshot(27 * 60).remaining_seconds, 3 * 60);

        let mut late = state();
        late.start_focus(now(0), Some(25), None).unwrap();
        let events = late.reconcile_time(now(31 * 60)).unwrap();
        assert!(!events.contains(&DomainEvent::RestStarted));
        assert_eq!(late.status, TimerStatus::Idle);
        assert_eq!(late.phase, None);
        assert_eq!(late.progress.daily_completed_focus_count, 0);
        let terminal_events = events
            .iter()
            .filter_map(|event| match event {
                DomainEvent::SessionHistory(batch) => Some(&batch.events),
                _ => None,
            })
            .flatten()
            .filter(|event| matches!(event, crate::domain::SessionHistoryEvent::Completed { .. }))
            .count();
        assert_eq!(terminal_events, 2);
    }

    #[test]
    fn active_rest_rejects_pause_and_resume_but_can_end_early() {
        let mut timer = state();
        timer.start_focus(now(0), Some(5), None).unwrap();
        timer.reconcile_time(now(5 * 60)).unwrap();

        assert_eq!(
            timer.pause(now(5 * 60 + 30)),
            Err(DomainError::ActionNotAllowed(TimerAction::Pause))
        );
        assert_eq!(
            timer.resume(now(5 * 60 + 30)),
            Err(DomainError::ActionNotAllowed(TimerAction::Resume))
        );

        let events = timer.end(now(5 * 60 + 31)).unwrap();
        assert!(events.contains(&DomainEvent::RestEnded));
        assert_eq!(timer.status, TimerStatus::Idle);
    }

    #[test]
    fn adjustments_follow_zero_to_sixty_focus_bounds() {
        let mut timer = state();
        timer.adjust_focus_duration(-20).unwrap();
        assert_eq!(timer.settings.focus_duration_minutes, 0);
        assert_eq!(timer.snapshot(0).remaining_seconds, 1);
        assert!(timer.adjust_focus_duration(-1).is_err());
        timer.adjust_focus_duration(60).unwrap();
        assert_eq!(timer.settings.focus_duration_minutes, 60);
        assert!(timer.adjust_focus_duration(1).is_err());
    }

    #[test]
    fn theme_changes_are_available_during_active_sessions() {
        let mut timer = state();
        let original_animations = timer.settings.animations.clone();
        timer.start_focus(now(0), None, None).unwrap();

        let events = timer.set_theme_mode(crate::domain::ThemeMode::Dark);
        assert_eq!(timer.settings.theme_mode, crate::domain::ThemeMode::Dark);
        assert_eq!(timer.settings.animations, original_animations);
        assert!(events.iter().any(|event| matches!(
            event,
            DomainEvent::SettingsChanged(settings)
                if settings.theme_mode == crate::domain::ThemeMode::Dark
        )));
        assert!(events.contains(&DomainEvent::SnapshotChanged));

        timer.pause(now(60)).unwrap();
        timer.set_theme_mode(crate::domain::ThemeMode::Light);
        assert_eq!(timer.settings.theme_mode, crate::domain::ThemeMode::Light);
    }

    #[test]
    fn active_timer_rejects_duration_and_settings_changes() {
        let mut timer = state();
        timer.start_focus(now(0), None, None).unwrap();
        assert_eq!(
            timer.adjust_focus_duration(1),
            Err(DomainError::ActionNotAllowed(
                TimerAction::AdjustFocusDuration
            ))
        );
        assert_eq!(
            timer.update_settings(AppSettings::defaults()),
            Err(DomainError::ActionNotAllowed(TimerAction::ChangeSettings))
        );
    }

    #[test]
    fn allowed_actions_cover_idle_running_and_paused_states() {
        let mut timer = state();
        assert_eq!(
            timer.allowed_actions(),
            vec![
                TimerAction::StartFocus,
                TimerAction::AdjustFocusDuration,
                TimerAction::ChangeSettings,
            ]
        );
        timer.start_focus(now(0), None, None).unwrap();
        assert_eq!(
            timer.allowed_actions(),
            vec![TimerAction::Pause, TimerAction::End]
        );
        timer.pause(now(60)).unwrap();
        assert_eq!(
            timer.allowed_actions(),
            vec![TimerAction::Resume, TimerAction::End]
        );
        timer.resume(now(60)).unwrap();
        timer.reconcile_time(now(20 * 60)).unwrap();
        assert_eq!(timer.allowed_actions(), vec![TimerAction::End]);
    }

    #[test]
    fn update_settings_validates_before_mutating() {
        let mut timer = state();
        let revision = timer.revision;
        let invalid = AppSettings {
            focus_duration_minutes: 61,
            ..AppSettings::defaults()
        };
        assert_eq!(
            timer.update_settings(invalid),
            Err(DomainError::InvalidSettings(
                crate::domain::SettingsError::InvalidFocusDuration
            ))
        );
        assert_eq!(timer.revision, revision);
    }

    #[test]
    fn committed_snapshot_fixture_matches_rust_serialization() {
        let mut timer = state();
        timer.progress.daily_completed_focus_count = 5;
        timer.revision = 6;
        timer
            .start_focus(TimeSample::new(0, 1_700_000_000), Some(45), None)
            .unwrap();

        let actual = serde_json::to_value(timer.snapshot(0)).unwrap();
        let expected: serde_json::Value =
            serde_json::from_str(include_str!("../../../../contracts/timer-snapshot.json"))
                .unwrap();
        assert_eq!(actual, expected);
    }

    #[test]
    fn snapshots_are_revisioned_and_serialize_with_camel_case_contract() {
        let mut timer = state();
        let initial = timer.snapshot(0);
        timer.start_focus(now(0), None, None).unwrap();
        let running = timer.snapshot(0);
        assert!(running.revision > initial.revision);
        assert_eq!(
            running.allowed_actions,
            vec![TimerAction::Pause, TimerAction::End]
        );

        let value = serde_json::to_value(&running).unwrap();
        assert_eq!(value["status"], "running");
        assert_eq!(value["phase"], "focus");
        assert!(value.get("focusDurationMinutes").is_some());
        assert!(value.get("restDurationMinutes").is_none());
        let _: TimerSnapshot = serde_json::from_value(value).unwrap();
    }
}
