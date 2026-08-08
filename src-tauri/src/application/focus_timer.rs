use crate::domain::{AppSettings, DomainError, DomainEvent, TimeSample, TimerSnapshot, TimerState};

use super::{AppEffect, Clock, TransitionOutcome};

pub struct FocusTimer<C> {
    state: TimerState,
    clock: C,
}

impl<C: Clock> FocusTimer<C> {
    pub fn new(state: TimerState, clock: C) -> Self {
        Self { state, clock }
    }

    pub fn checkpoint(&self) -> TimerState {
        self.state.clone()
    }

    pub fn restore(&mut self, state: TimerState) {
        self.state = state;
    }

    pub fn set_daily_completed_focus_count(&mut self, count: u32) {
        self.state.set_daily_completed_focus_count(count);
    }

    pub fn current_utc_seconds(&self) -> i64 {
        self.clock.sample().utc_seconds
    }

    pub fn snapshot(&self) -> TimerSnapshot {
        self.state.snapshot(self.clock.sample().monotonic_seconds)
    }

    pub fn settings(&self) -> AppSettings {
        self.state.settings.clone()
    }

    pub fn start_focus(
        &mut self,
        duration_override_minutes: Option<u32>,
        work_item_id: Option<String>,
    ) -> Result<TransitionOutcome, DomainError> {
        self.transition(|state, now| {
            state.start_focus(now, duration_override_minutes, work_item_id)
        })
    }

    pub fn pause(&mut self) -> Result<TransitionOutcome, DomainError> {
        self.transition(TimerState::pause)
    }

    pub fn resume(&mut self) -> Result<TransitionOutcome, DomainError> {
        self.transition(TimerState::resume)
    }

    pub fn end(&mut self) -> Result<TransitionOutcome, DomainError> {
        self.transition(TimerState::end)
    }

    pub fn end_for_shutdown(&mut self) -> Result<TransitionOutcome, DomainError> {
        let now = self.clock.sample();
        let events = self.state.end(now)?;
        Ok(self.outcome(events))
    }

    pub fn adjust_focus_duration(
        &mut self,
        delta_minutes: i32,
    ) -> Result<TransitionOutcome, DomainError> {
        let events = self.state.adjust_focus_duration(delta_minutes)?;
        Ok(self.outcome(events))
    }

    pub fn update_settings(
        &mut self,
        settings: AppSettings,
    ) -> Result<TransitionOutcome, DomainError> {
        let events = self.state.update_settings(settings)?;
        Ok(self.outcome(events))
    }

    pub fn reconcile_time(&mut self) -> Result<Option<TransitionOutcome>, DomainError> {
        let now = self.clock.sample();
        let events = self.state.reconcile_time(now)?;
        if events.is_empty() {
            Ok(None)
        } else {
            Ok(Some(self.outcome(events)))
        }
    }

    pub fn heartbeat_snapshot(&self) -> TimerSnapshot {
        self.snapshot()
    }

    fn transition(
        &mut self,
        transition: impl FnOnce(&mut TimerState, TimeSample) -> Result<Vec<DomainEvent>, DomainError>,
    ) -> Result<TransitionOutcome, DomainError> {
        let now = self.clock.sample();
        let events = transition(&mut self.state, now)?;
        Ok(self.outcome(events))
    }

    fn outcome(&self, events: Vec<DomainEvent>) -> TransitionOutcome {
        TransitionOutcome {
            snapshot: self.snapshot(),
            effects: events.into_iter().flat_map(map_event).collect(),
        }
    }
}

fn map_event(event: DomainEvent) -> Vec<AppEffect> {
    match event {
        DomainEvent::SettingsChanged(settings) => vec![
            AppEffect::PersistSettings(settings.clone()),
            AppEffect::PublishSettings(settings),
        ],
        DomainEvent::SnapshotChanged => vec![AppEffect::PublishTimerSnapshot],
        DomainEvent::SessionHistory(events) => vec![AppEffect::PersistSessionHistory(events)],
        DomainEvent::RestStarted => vec![
            AppEffect::ShowRestOverlay,
            AppEffect::StopWhiteNoise,
            AppEffect::PlayNotification,
        ],
        DomainEvent::RestEnded => vec![AppEffect::HideRestOverlay],
    }
}

#[cfg(test)]
mod tests {
    use std::sync::{Arc, Mutex};

    use super::*;
    use crate::{
        application::Clock,
        domain::{AppSettings, SessionPhase, TimerAction, TimerStatus},
    };

    #[derive(Clone)]
    struct ManualClock(Arc<Mutex<TimeSample>>);

    impl ManualClock {
        fn new(sample: TimeSample) -> Self {
            Self(Arc::new(Mutex::new(sample)))
        }

        fn set(&self, sample: TimeSample) {
            *self.0.lock().unwrap() = sample;
        }
    }

    impl Clock for ManualClock {
        fn sample(&self) -> TimeSample {
            *self.0.lock().unwrap()
        }
    }

    fn service() -> (FocusTimer<ManualClock>, ManualClock) {
        let clock = ManualClock::new(TimeSample::new(0, 1_700_000_000));
        let timer = FocusTimer::new(
            TimerState::new(AppSettings::defaults()).unwrap(),
            clock.clone(),
        );
        (timer, clock)
    }

    #[test]
    fn drives_each_timer_command_with_explicit_clock_samples() {
        let (mut timer, clock) = service();
        let started = timer.start_focus(Some(5), None).unwrap();
        assert_eq!(started.snapshot.status, TimerStatus::Running);
        assert!(started.effects.contains(&AppEffect::PublishTimerSnapshot));

        clock.set(TimeSample::new(60, 1_700_000_060));
        assert_eq!(timer.pause().unwrap().snapshot.status, TimerStatus::Paused);
        clock.set(TimeSample::new(120, 1_700_000_120));
        assert_eq!(
            timer.resume().unwrap().snapshot.status,
            TimerStatus::Running
        );
        assert_eq!(timer.end().unwrap().snapshot.status, TimerStatus::Idle);

        timer.adjust_focus_duration(5).unwrap();
        let settings = AppSettings {
            focus_duration_minutes: 25,
        };
        let updated = timer.update_settings(settings.clone()).unwrap();
        assert!(
            updated
                .effects
                .contains(&AppEffect::PublishSettings(settings))
        );
        assert!(
            updated
                .snapshot
                .allowed_actions
                .contains(&TimerAction::StartFocus)
        );
    }

    #[test]
    fn scheduler_completes_focus_into_derived_rest() {
        let (mut timer, clock) = service();
        timer.start_focus(Some(5), None).unwrap();
        clock.set(TimeSample::new(299, 1_700_000_299));
        assert!(timer.reconcile_time().unwrap().is_none());
        assert_eq!(timer.heartbeat_snapshot().remaining_seconds, 1);

        clock.set(TimeSample::new(300, 1_700_000_300));
        let outcome = timer.reconcile_time().unwrap().unwrap();
        assert_eq!(outcome.snapshot.status, TimerStatus::Running);
        assert_eq!(outcome.snapshot.phase, Some(SessionPhase::Rest));
        assert_eq!(outcome.snapshot.remaining_seconds, 5 * 60);
        assert_eq!(outcome.snapshot.daily_completed_focus_count, 0);
        assert!(
            outcome
                .effects
                .iter()
                .any(|effect| matches!(effect, AppEffect::PersistSessionHistory(_)))
        );
        assert!(outcome.effects.contains(&AppEffect::ShowRestOverlay));
    }

    #[test]
    fn active_rest_can_be_ended_and_hides_the_overlay() {
        let (mut timer, clock) = service();
        timer.start_focus(Some(5), None).unwrap();
        clock.set(TimeSample::new(300, 1_700_000_300));
        timer.reconcile_time().unwrap();

        clock.set(TimeSample::new(301, 1_700_000_301));
        let ended = timer.end().unwrap();
        assert_eq!(ended.snapshot.status, TimerStatus::Idle);
        assert!(ended.effects.contains(&AppEffect::HideRestOverlay));
    }
}
