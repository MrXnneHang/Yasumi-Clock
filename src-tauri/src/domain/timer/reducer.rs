use crate::domain::{
    AppSettings, CompletedSession, SessionEndReason, SessionMetadata,
    settings::{validate_focus_duration, validate_rest_duration},
};

use super::model::{
    DomainError, DomainEvent, SessionPhase, TimeSample, TimerAction, TimerState, TimerStatus,
};

impl TimerState {
    pub fn update_settings(
        &mut self,
        settings: AppSettings,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::ChangeSettings)?;
        settings.validate().map_err(DomainError::InvalidSettings)?;
        self.settings = settings;
        self.bump_revision();
        Ok(vec![DomainEvent::SnapshotChanged])
    }

    pub fn start_focus(
        &mut self,
        now: TimeSample,
        duration_override_minutes: Option<u32>,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::StartFocus)?;
        let minutes = duration_override_minutes.unwrap_or(self.settings.focus_duration_minutes);
        validate_focus_duration(minutes).map_err(DomainError::InvalidSettings)?;
        self.settings.focus_duration_minutes = minutes;
        self.begin_session(SessionPhase::Focus, u64::from(minutes) * 60, now);
        self.bump_revision();
        self.validate()?;
        Ok(vec![DomainEvent::SnapshotChanged])
    }

    pub fn start_rest(
        &mut self,
        now: TimeSample,
        duration_override_minutes: Option<u32>,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::StartRest)?;
        let minutes = duration_override_minutes.unwrap_or(self.settings.rest_duration_minutes);
        validate_rest_duration(minutes).map_err(DomainError::InvalidSettings)?;
        self.settings.rest_duration_minutes = minutes;
        self.begin_session(SessionPhase::Rest, u64::from(minutes) * 60, now);
        self.bump_revision();
        self.validate()?;
        Ok(vec![DomainEvent::RestStarted, DomainEvent::SnapshotChanged])
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
        let mut events = self.end_active_session(now.utc_seconds, SessionEndReason::Interrupted);
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
        Ok(vec![DomainEvent::SnapshotChanged])
    }

    pub fn adjust_rest_duration(
        &mut self,
        delta_minutes: i32,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::AdjustRestDuration)?;
        let adjusted = adjusted_minutes(self.settings.rest_duration_minutes, delta_minutes).ok_or(
            DomainError::InvalidSettings(crate::domain::SettingsError::InvalidRestDuration),
        )?;
        validate_rest_duration(adjusted).map_err(DomainError::InvalidSettings)?;
        self.settings.rest_duration_minutes = adjusted;
        self.bump_revision();
        Ok(vec![DomainEvent::SnapshotChanged])
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

        let completed_phase = self.phase.ok_or(DomainError::InvalidState)?;
        let mut events = self.end_active_session_at_deadline(SessionEndReason::Completed);
        if completed_phase == SessionPhase::Focus {
            self.progress.record_completed_focus();
        }
        self.return_to_idle();
        self.bump_revision();
        if completed_phase == SessionPhase::Rest {
            events.push(DomainEvent::RestEnded);
        }
        events.push(DomainEvent::SnapshotChanged);
        self.validate()?;
        Ok(events)
    }

    fn begin_session(&mut self, phase: SessionPhase, duration_seconds: u64, now: TimeSample) {
        self.status = TimerStatus::Running;
        self.phase = Some(phase);
        self.deadline_monotonic_seconds =
            Some(now.monotonic_seconds.saturating_add(duration_seconds));
        self.deadline_utc_seconds = Some(add_utc(now.utc_seconds, duration_seconds));
        self.paused_remaining_seconds = None;
        self.paused_at_monotonic_seconds = None;
        self.active_session = Some(SessionMetadata {
            phase,
            planned_duration_seconds: duration_seconds,
            started_at_utc_seconds: now.utc_seconds,
            accumulated_pause_seconds: 0,
            pause_count: 0,
        });
    }

    fn end_active_session_at_deadline(&mut self, reason: SessionEndReason) -> Vec<DomainEvent> {
        let ended_at = self.deadline_utc_seconds.unwrap_or_default();
        self.end_active_session(ended_at, reason)
    }

    fn end_active_session(
        &mut self,
        ended_at_utc_seconds: i64,
        reason: SessionEndReason,
    ) -> Vec<DomainEvent> {
        self.active_session
            .take()
            .map(|metadata| {
                vec![DomainEvent::SessionEnded(CompletedSession {
                    metadata,
                    ended_at_utc_seconds,
                    reason,
                })]
            })
            .unwrap_or_default()
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
    fn starts_pauses_resumes_and_ends_focus_without_erasing_daily_progress() {
        let mut timer = state();
        timer.progress.daily_completed_focus_count = 7;
        timer.start_focus(now(10), None).unwrap();
        assert_eq!(timer.snapshot(10).remaining_seconds, 20 * 60);

        timer.pause(now(70)).unwrap();
        assert_eq!(timer.status, TimerStatus::Paused);
        assert_eq!(timer.snapshot(1_000).remaining_seconds, 19 * 60);
        timer.resume(now(170)).unwrap();
        assert_eq!(timer.deadline_monotonic_seconds, Some(1_310));
        let events = timer.end(now(200)).unwrap();
        assert!(!events.contains(&DomainEvent::RestEnded));
        assert_eq!(timer.status, TimerStatus::Idle);
        assert_eq!(timer.progress.daily_completed_focus_count, 7);
        timer.validate().unwrap();
    }

    #[test]
    fn focus_and_rest_start_independently_and_validate_overrides() {
        let mut timer = state();
        timer.start_focus(now(0), Some(60)).unwrap();
        assert_eq!(timer.deadline_monotonic_seconds, Some(3_600));
        timer.end(now(1)).unwrap();
        timer.start_rest(now(2), Some(30)).unwrap();
        assert_eq!(timer.phase, Some(SessionPhase::Rest));
        assert_eq!(timer.deadline_monotonic_seconds, Some(1_802));

        let mut invalid = state();
        assert_eq!(
            invalid.start_focus(now(0), Some(0)),
            Err(DomainError::InvalidSettings(
                crate::domain::SettingsError::InvalidFocusDuration
            ))
        );
        assert_eq!(
            invalid.start_rest(now(0), Some(4)),
            Err(DomainError::InvalidSettings(
                crate::domain::SettingsError::InvalidRestDuration
            ))
        );
    }

    #[test]
    fn completed_focus_and_rest_both_return_idle_without_auto_transition() {
        let mut timer = state();
        timer.start_focus(now(0), Some(5)).unwrap();
        timer.reconcile_time(now(5 * 60)).unwrap();
        assert_eq!(timer.status, TimerStatus::Idle);
        assert_eq!(timer.phase, None);
        assert_eq!(timer.progress.daily_completed_focus_count, 1);

        timer.start_rest(now(301), Some(5)).unwrap();
        let events = timer.reconcile_time(now(601)).unwrap();
        assert!(events.contains(&DomainEvent::RestEnded));
        assert_eq!(timer.status, TimerStatus::Idle);
        assert_eq!(timer.progress.daily_completed_focus_count, 1);
    }

    #[test]
    fn delayed_tick_does_not_start_another_activity() {
        let mut timer = state();
        timer.start_focus(now(0), Some(5)).unwrap();
        timer.reconcile_time(now(11 * 60)).unwrap();
        assert_eq!(timer.status, TimerStatus::Idle);
        assert_eq!(timer.phase, None);
        assert_eq!(timer.progress.daily_completed_focus_count, 1);
    }

    #[test]
    fn adjustments_follow_independent_focus_and_rest_bounds() {
        let mut timer = state();
        timer.adjust_focus_duration(-19).unwrap();
        assert_eq!(timer.settings.focus_duration_minutes, 1);
        assert!(timer.adjust_focus_duration(-1).is_err());
        timer.adjust_focus_duration(59).unwrap();
        assert_eq!(timer.settings.focus_duration_minutes, 60);
        assert!(timer.adjust_focus_duration(1).is_err());

        timer.adjust_rest_duration(25).unwrap();
        assert_eq!(timer.settings.rest_duration_minutes, 30);
        assert!(timer.adjust_rest_duration(1).is_err());
        timer.adjust_rest_duration(-25).unwrap();
        assert_eq!(timer.settings.rest_duration_minutes, 5);
        assert!(timer.adjust_rest_duration(-1).is_err());
    }

    #[test]
    fn active_timer_rejects_duration_and_settings_changes() {
        let mut timer = state();
        timer.start_rest(now(0), None).unwrap();
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
                TimerAction::StartRest,
                TimerAction::AdjustFocusDuration,
                TimerAction::AdjustRestDuration,
                TimerAction::ChangeSettings,
            ]
        );
        timer.start_rest(now(0), None).unwrap();
        assert_eq!(
            timer.allowed_actions(),
            vec![TimerAction::Pause, TimerAction::End]
        );
        timer.pause(now(60)).unwrap();
        assert_eq!(
            timer.allowed_actions(),
            vec![TimerAction::Resume, TimerAction::End]
        );
    }

    #[test]
    fn update_settings_validates_before_mutating() {
        let mut timer = state();
        let revision = timer.revision;
        let invalid = AppSettings {
            focus_duration_minutes: 20,
            rest_duration_minutes: 4,
        };
        assert_eq!(
            timer.update_settings(invalid),
            Err(DomainError::InvalidSettings(
                crate::domain::SettingsError::InvalidRestDuration
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
            .start_focus(TimeSample::new(0, 1_700_000_000), Some(45))
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
        timer.start_focus(now(0), None).unwrap();
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
        assert!(value.get("restDurationMinutes").is_some());
        let _: TimerSnapshot = serde_json::from_value(value).unwrap();
    }
}
