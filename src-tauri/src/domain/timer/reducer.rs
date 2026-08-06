use crate::domain::{AppSettings, CompletedSession, SessionEndReason, SessionMetadata};

use super::model::{
    CLASSIC_BREAK_MINUTES, CLASSIC_MAX_FOCUS_MINUTES, CLASSIC_MIN_FOCUS_MINUTES, DomainError,
    DomainEvent, SessionPhase, TimeSample, TimerAction, TimerMode, TimerState, TimerStatus,
    classic_duration_seconds,
};

impl TimerState {
    pub fn select_mode(&mut self, mode: TimerMode) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::ChangeSettings)?;
        if let TimerMode::Preset(id) = &mode
            && self.settings.preset(id).is_none()
        {
            return Err(DomainError::UnknownPreset(id.clone()));
        }
        self.mode = mode;
        self.bump_revision();
        Ok(vec![DomainEvent::SnapshotChanged])
    }

    pub fn update_settings(
        &mut self,
        settings: AppSettings,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::ChangeSettings)?;
        settings.validate().map_err(DomainError::InvalidSettings)?;
        if let TimerMode::Preset(id) = &self.mode
            && settings.preset(id).is_none()
        {
            return Err(DomainError::UnknownPreset(id.clone()));
        }
        self.settings = settings;
        self.bump_revision();
        Ok(vec![DomainEvent::SnapshotChanged])
    }

    pub fn start_focus(
        &mut self,
        now: TimeSample,
        classic_duration_override_minutes: Option<u32>,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::StartFocus)?;
        let duration_seconds = match &self.mode {
            TimerMode::Classic => {
                let minutes =
                    classic_duration_override_minutes.unwrap_or(self.classic_focus_minutes);
                if !valid_classic_duration(minutes) {
                    return Err(DomainError::InvalidClassicDuration);
                }
                self.classic_focus_minutes = minutes;
                classic_duration_seconds(minutes)
            }
            TimerMode::Preset(id) => {
                let preset = self
                    .settings
                    .preset(id)
                    .ok_or_else(|| DomainError::UnknownPreset(id.clone()))?;
                u64::from(
                    preset
                        .focus_duration
                        .duration_minutes(self.progress.cycle_focus_count),
                ) * 60
            }
        };
        self.begin_session(SessionPhase::Focus, duration_seconds, now);
        self.bump_revision();
        self.validate()?;
        Ok(vec![DomainEvent::SnapshotChanged])
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

    pub fn reset(&mut self, now: TimeSample) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::Reset)?;
        let was_break = matches!(
            self.phase,
            Some(SessionPhase::ShortBreak | SessionPhase::LongBreak)
        );
        let mut events = self.end_active_session(now.utc_seconds, SessionEndReason::Interrupted);
        self.progress.reset_cycle();
        self.return_to_idle();
        self.bump_revision();
        if was_break {
            events.push(DomainEvent::BreakEnded);
        }
        events.push(DomainEvent::SnapshotChanged);
        self.validate()?;
        Ok(events)
    }

    pub fn dismiss_break(&mut self, now: TimeSample) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::DismissBreak)?;
        let mut events = self.end_active_session(now.utc_seconds, SessionEndReason::Dismissed);
        self.return_to_idle();
        self.bump_revision();
        events.push(DomainEvent::BreakEnded);
        events.push(DomainEvent::SnapshotChanged);
        self.validate()?;
        Ok(events)
    }

    pub fn adjust_classic_duration(
        &mut self,
        delta_minutes: i32,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        self.require_action(TimerAction::AdjustClassicDuration)?;
        if self.mode != TimerMode::Classic {
            return Err(DomainError::WrongMode);
        }
        let adjusted = i32::try_from(self.classic_focus_minutes)
            .unwrap_or(i32::MAX)
            .saturating_add(delta_minutes);
        let adjusted = u32::try_from(adjusted).map_err(|_| DomainError::InvalidClassicDuration)?;
        if !valid_classic_duration(adjusted) {
            return Err(DomainError::InvalidClassicDuration);
        }
        self.classic_focus_minutes = adjusted;
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

        match self.phase.ok_or(DomainError::InvalidState)? {
            SessionPhase::Focus => self.complete_focus(deadline, now),
            SessionPhase::ShortBreak | SessionPhase::LongBreak => {
                let mut events = self.end_active_session_at_deadline(SessionEndReason::Completed);
                self.return_to_idle();
                self.bump_revision();
                events.push(DomainEvent::BreakEnded);
                events.push(DomainEvent::SnapshotChanged);
                self.validate()?;
                Ok(events)
            }
        }
    }

    fn complete_focus(
        &mut self,
        expired_deadline_monotonic: u64,
        now: TimeSample,
    ) -> Result<Vec<DomainEvent>, DomainError> {
        let mut events = self.end_active_session_at_deadline(SessionEndReason::Completed);
        let (cycle_target, short_break_minutes, long_break_minutes, force_rest) = match &self.mode {
            TimerMode::Classic => (1, CLASSIC_BREAK_MINUTES, CLASSIC_BREAK_MINUTES, false),
            TimerMode::Preset(id) => {
                let preset = self
                    .settings
                    .preset(id)
                    .ok_or_else(|| DomainError::UnknownPreset(id.clone()))?;
                (
                    preset.cycles_before_long_break,
                    preset.short_break_minutes,
                    preset.long_break_minutes,
                    preset.force_rest,
                )
            }
        };
        let is_long_break =
            self.mode != TimerMode::Classic && self.progress.complete_focus(cycle_target);
        if self.mode == TimerMode::Classic {
            self.progress.daily_completed_focus_count =
                self.progress.daily_completed_focus_count.saturating_add(1);
        }
        let phase = if is_long_break {
            SessionPhase::LongBreak
        } else {
            SessionPhase::ShortBreak
        };
        let duration_seconds = u64::from(if is_long_break {
            long_break_minutes
        } else {
            short_break_minutes
        }) * 60;
        let overrun = now
            .monotonic_seconds
            .saturating_sub(expired_deadline_monotonic);
        let remaining = duration_seconds.saturating_sub(overrun);
        let break_start_utc = add_utc(now.utc_seconds, 0).saturating_sub(i64_from_u64(overrun));
        self.phase = Some(phase);
        self.active_session = Some(SessionMetadata {
            phase,
            planned_duration_seconds: duration_seconds,
            started_at_utc_seconds: break_start_utc,
            accumulated_pause_seconds: 0,
            pause_count: 0,
        });
        events.push(DomainEvent::BreakStarted {
            phase,
            force: force_rest,
        });

        if remaining == 0 {
            let ended = self.end_active_session(now.utc_seconds, SessionEndReason::Completed);
            events.extend(ended);
            self.return_to_idle();
            events.push(DomainEvent::BreakEnded);
        } else {
            self.status = TimerStatus::Running;
            self.deadline_monotonic_seconds = Some(now.monotonic_seconds.saturating_add(remaining));
            self.deadline_utc_seconds = Some(add_utc(now.utc_seconds, remaining));
            self.paused_remaining_seconds = None;
            self.paused_at_monotonic_seconds = None;
        }
        self.bump_revision();
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

fn valid_classic_duration(minutes: u32) -> bool {
    (CLASSIC_MIN_FOCUS_MINUTES..=CLASSIC_MAX_FOCUS_MINUTES).contains(&minutes)
}

fn add_utc(utc_seconds: i64, duration_seconds: u64) -> i64 {
    utc_seconds.saturating_add(i64_from_u64(duration_seconds))
}

fn i64_from_u64(value: u64) -> i64 {
    i64::try_from(value).unwrap_or(i64::MAX)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::domain::{FocusDurationPlan, Preset, PresetId, TimerAction, TimerSnapshot};

    fn state() -> TimerState {
        TimerState::new(AppSettings::defaults()).unwrap()
    }

    fn now(seconds: u64) -> TimeSample {
        TimeSample::new(seconds, 1_700_000_000 + i64::try_from(seconds).unwrap())
    }

    #[test]
    fn starts_pauses_resumes_and_resets_focus_without_erasing_daily_progress() {
        let mut timer = state();
        timer.progress.daily_completed_focus_count = 7;
        timer.start_focus(now(10), None).unwrap();
        assert_eq!(timer.snapshot(10).remaining_seconds, 20 * 60);

        timer.pause(now(70)).unwrap();
        assert_eq!(timer.status, TimerStatus::Paused);
        assert_eq!(timer.snapshot(1_000).remaining_seconds, 19 * 60);
        assert_eq!(timer.active_session.as_ref().unwrap().pause_count, 1);

        timer.resume(now(170)).unwrap();
        assert_eq!(timer.deadline_monotonic_seconds, Some(1_310));
        let session = timer.active_session.as_ref().unwrap();
        assert_eq!(session.pause_count, 1);
        assert_eq!(session.accumulated_pause_seconds, 100);
        let events = timer.reset(now(200)).unwrap();
        assert!(!events.contains(&DomainEvent::BreakEnded));
        assert_eq!(timer.status, TimerStatus::Idle);
        assert_eq!(timer.progress.cycle_focus_count, 0);
        assert_eq!(timer.progress.daily_completed_focus_count, 7);
        timer.validate().unwrap();
    }

    #[test]
    fn classic_duration_accepts_each_minute_from_zero_through_sixty() {
        let mut timer = state();

        timer.start_focus(now(10), Some(0)).unwrap();
        assert_eq!(timer.classic_focus_minutes, 0);
        assert_eq!(timer.deadline_monotonic_seconds, Some(11));
        assert_eq!(timer.snapshot(10).remaining_seconds, 1);
        timer.reset(now(10)).unwrap();
        assert_eq!(timer.snapshot(10).remaining_seconds, 1);

        timer.start_focus(now(20), Some(1)).unwrap();
        assert_eq!(timer.deadline_monotonic_seconds, Some(80));
        timer.reset(now(20)).unwrap();

        timer.start_focus(now(30), Some(37)).unwrap();
        assert_eq!(timer.deadline_monotonic_seconds, Some(2_250));
        timer.reset(now(30)).unwrap();

        timer.start_focus(now(40), Some(60)).unwrap();
        assert_eq!(timer.deadline_monotonic_seconds, Some(3_640));

        let mut invalid = state();
        assert_eq!(
            invalid.start_focus(now(0), Some(61)),
            Err(DomainError::InvalidClassicDuration)
        );
    }

    #[test]
    fn legacy_classic_adjustments_follow_the_zero_to_sixty_bounds() {
        let mut timer = state();
        timer.adjust_classic_duration(-20).unwrap();
        assert_eq!(timer.classic_focus_minutes, 0);
        assert_eq!(timer.snapshot(0).remaining_seconds, 1);
        assert_eq!(
            timer.adjust_classic_duration(-1),
            Err(DomainError::InvalidClassicDuration)
        );
        timer.adjust_classic_duration(37).unwrap();
        assert_eq!(timer.classic_focus_minutes, 37);
        timer.adjust_classic_duration(23).unwrap();
        assert_eq!(timer.classic_focus_minutes, 60);
        assert_eq!(
            timer.adjust_classic_duration(1),
            Err(DomainError::InvalidClassicDuration)
        );
    }

    #[test]
    fn preset_cycle_chooses_short_then_long_break_and_preserves_daily_count() {
        let mut timer = state();
        timer
            .select_mode(TimerMode::Preset(PresetId::new("student").unwrap()))
            .unwrap();
        timer.progress.cycle_focus_count = 1;
        timer.progress.daily_completed_focus_count = 4;
        timer.start_focus(now(0), None).unwrap();
        timer.reconcile_time(now(45 * 60)).unwrap();
        assert_eq!(timer.phase, Some(SessionPhase::ShortBreak));
        assert_eq!(timer.progress.cycle_focus_count, 2);
        assert_eq!(timer.progress.daily_completed_focus_count, 5);
        timer.dismiss_break(now(45 * 60 + 1)).unwrap();

        timer.start_focus(now(3_000), None).unwrap();
        timer.reconcile_time(now(3_000 + 45 * 60)).unwrap();
        assert_eq!(timer.phase, Some(SessionPhase::LongBreak));
        assert_eq!(timer.progress.cycle_focus_count, 0);
        assert_eq!(timer.progress.daily_completed_focus_count, 6);
    }

    #[test]
    fn delayed_tick_consumes_break_overrun_but_never_starts_another_focus() {
        let mut timer = state();
        timer.start_focus(now(0), Some(5)).unwrap();
        timer.reconcile_time(now(5 * 60 + 90)).unwrap();
        assert_eq!(timer.phase, Some(SessionPhase::ShortBreak));
        assert_eq!(timer.snapshot(390).remaining_seconds, 210);

        let mut late = state();
        late.start_focus(now(0), Some(5)).unwrap();
        late.reconcile_time(now(11 * 60)).unwrap();
        assert_eq!(late.status, TimerStatus::Idle);
        assert_eq!(late.phase, None);
        assert_eq!(late.progress.daily_completed_focus_count, 1);
    }

    #[test]
    fn forced_break_rejects_dismiss() {
        let mut settings = AppSettings::defaults();
        let id = PresetId::new("custom").unwrap();
        settings.presets.get_mut(&id).unwrap().force_rest = true;
        let mut timer = TimerState::new(settings).unwrap();
        timer.select_mode(TimerMode::Preset(id)).unwrap();
        timer.start_focus(now(0), None).unwrap();
        timer.reconcile_time(now(25 * 60)).unwrap();
        assert!(!timer.allowed_actions().contains(&TimerAction::DismissBreak));
        assert_eq!(
            timer.dismiss_break(now(25 * 60 + 1)),
            Err(DomainError::ActionNotAllowed(TimerAction::DismissBreak))
        );
    }

    #[test]
    fn sequence_duration_follows_cycle_progress() {
        let mut settings = AppSettings::defaults();
        let id = PresetId::new("declining").unwrap();
        settings.presets.insert(
            id.clone(),
            Preset {
                id: id.clone(),
                name: "减退模式".into(),
                focus_duration: FocusDurationPlan::Sequence(vec![30, 20, 10]),
                short_break_minutes: 5,
                long_break_minutes: 15,
                cycles_before_long_break: 4,
                force_rest: false,
            },
        );
        let mut timer = TimerState::new(settings).unwrap();
        timer.select_mode(TimerMode::Preset(id)).unwrap();
        timer.progress.cycle_focus_count = 2;
        timer.start_focus(now(0), None).unwrap();
        assert_eq!(timer.snapshot(0).remaining_seconds, 10 * 60);
    }

    #[test]
    fn active_timer_rejects_mode_and_settings_changes() {
        let mut timer = state();
        timer.start_focus(now(0), None).unwrap();
        assert_eq!(
            timer.select_mode(TimerMode::Preset(PresetId::new("student").unwrap())),
            Err(DomainError::ActionNotAllowed(TimerAction::ChangeSettings))
        );
        assert_eq!(
            timer.update_settings(AppSettings::defaults()),
            Err(DomainError::ActionNotAllowed(TimerAction::ChangeSettings))
        );
    }

    #[test]
    fn allowed_actions_cover_each_valid_status_and_phase() {
        let mut timer = state();
        assert_eq!(
            timer.allowed_actions(),
            vec![
                TimerAction::StartFocus,
                TimerAction::AdjustClassicDuration,
                TimerAction::ChangeSettings,
            ]
        );

        timer.start_focus(now(0), Some(5)).unwrap();
        assert_eq!(
            timer.allowed_actions(),
            vec![TimerAction::Pause, TimerAction::Reset]
        );
        timer.pause(now(60)).unwrap();
        assert_eq!(
            timer.allowed_actions(),
            vec![TimerAction::Resume, TimerAction::Reset]
        );
        timer.resume(now(120)).unwrap();
        timer.reconcile_time(now(120 + 4 * 60)).unwrap();
        assert_eq!(timer.phase, Some(SessionPhase::ShortBreak));
        assert_eq!(
            timer.allowed_actions(),
            vec![
                TimerAction::Pause,
                TimerAction::Reset,
                TimerAction::DismissBreak,
            ]
        );
        timer.pause(now(121 + 4 * 60)).unwrap();
        assert_eq!(
            timer.allowed_actions(),
            vec![
                TimerAction::Resume,
                TimerAction::Reset,
                TimerAction::DismissBreak,
            ]
        );
    }

    #[test]
    fn break_expiry_returns_idle_and_reset_emits_break_ended_only_for_breaks() {
        let mut timer = state();
        timer.start_focus(now(0), Some(5)).unwrap();
        timer.reconcile_time(now(5 * 60)).unwrap();
        let events = timer.reset(now(5 * 60 + 1)).unwrap();
        assert!(events.contains(&DomainEvent::BreakEnded));
        assert_eq!(timer.status, TimerStatus::Idle);

        timer.start_focus(now(1_000), Some(5)).unwrap();
        timer.reconcile_time(now(1_000 + 5 * 60)).unwrap();
        let events = timer.reconcile_time(now(1_000 + 10 * 60)).unwrap();
        assert!(events.contains(&DomainEvent::BreakEnded));
        assert_eq!(timer.status, TimerStatus::Idle);
        assert_eq!(timer.phase, None);
    }

    #[test]
    fn rejects_unknown_modes_and_invalid_settings_without_mutation() {
        let mut timer = state();
        let revision = timer.revision;
        let unknown = PresetId::new("missing").unwrap();
        assert_eq!(
            timer.select_mode(TimerMode::Preset(unknown.clone())),
            Err(DomainError::UnknownPreset(unknown))
        );
        assert_eq!(timer.revision, revision);

        let mut invalid = AppSettings::defaults();
        invalid
            .presets
            .get_mut(&PresetId::new("custom").unwrap())
            .unwrap()
            .short_break_minutes = 0;
        assert_eq!(
            timer.update_settings(invalid),
            Err(DomainError::InvalidSettings(
                crate::domain::SettingsError::InvalidDuration
            ))
        );
        assert_eq!(timer.revision, revision);
    }

    #[test]
    fn committed_snapshot_fixture_matches_rust_serialization() {
        let mut timer = state();
        timer
            .select_mode(TimerMode::Preset(PresetId::new("student").unwrap()))
            .unwrap();
        timer.progress.cycle_focus_count = 1;
        timer.progress.daily_completed_focus_count = 5;
        timer.revision = 6;
        timer
            .start_focus(TimeSample::new(0, 1_700_000_000), None)
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
            vec![TimerAction::Pause, TimerAction::Reset]
        );

        let value = serde_json::to_value(&running).unwrap();
        assert_eq!(value["status"], "running");
        assert_eq!(value["phase"], "focus");
        assert_eq!(value["mode"]["kind"], "classic");
        assert!(value.get("remainingSeconds").is_some());
        let _: TimerSnapshot = serde_json::from_value(value).unwrap();
    }
}
