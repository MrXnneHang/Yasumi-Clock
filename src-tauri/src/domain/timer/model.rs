use serde::{Deserialize, Serialize};

use crate::domain::{CompletedSession, SessionMetadata, TimerProgress, settings::AppSettings};

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum TimerStatus {
    Idle,
    Running,
    Paused,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum SessionPhase {
    Focus,
    Rest,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum TimerAction {
    StartFocus,
    StartRest,
    Pause,
    Resume,
    End,
    AdjustFocusDuration,
    AdjustRestDuration,
    ChangeSettings,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TimeSample {
    pub monotonic_seconds: u64,
    pub utc_seconds: i64,
}

impl TimeSample {
    pub const fn new(monotonic_seconds: u64, utc_seconds: i64) -> Self {
        Self {
            monotonic_seconds,
            utc_seconds,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TimerState {
    pub revision: u64,
    pub status: TimerStatus,
    pub phase: Option<SessionPhase>,
    pub deadline_monotonic_seconds: Option<u64>,
    pub deadline_utc_seconds: Option<i64>,
    pub paused_remaining_seconds: Option<u64>,
    pub paused_at_monotonic_seconds: Option<u64>,
    pub active_session: Option<SessionMetadata>,
    pub progress: TimerProgress,
    pub settings: AppSettings,
}

impl TimerState {
    pub fn new(settings: AppSettings) -> Result<Self, DomainError> {
        settings.validate().map_err(DomainError::InvalidSettings)?;
        Ok(Self {
            revision: 0,
            status: TimerStatus::Idle,
            phase: None,
            deadline_monotonic_seconds: None,
            deadline_utc_seconds: None,
            paused_remaining_seconds: None,
            paused_at_monotonic_seconds: None,
            active_session: None,
            progress: TimerProgress::default(),
            settings,
        })
    }

    pub fn validate(&self) -> Result<(), DomainError> {
        let valid = match self.status {
            TimerStatus::Idle => {
                self.phase.is_none()
                    && self.deadline_monotonic_seconds.is_none()
                    && self.deadline_utc_seconds.is_none()
                    && self.paused_remaining_seconds.is_none()
                    && self.paused_at_monotonic_seconds.is_none()
                    && self.active_session.is_none()
            }
            TimerStatus::Running => {
                self.phase.is_some()
                    && self.deadline_monotonic_seconds.is_some()
                    && self.deadline_utc_seconds.is_some()
                    && self.paused_remaining_seconds.is_none()
                    && self.paused_at_monotonic_seconds.is_none()
                    && self.active_session.is_some()
            }
            TimerStatus::Paused => {
                self.phase.is_some()
                    && self.deadline_monotonic_seconds.is_none()
                    && self.deadline_utc_seconds.is_none()
                    && self.paused_remaining_seconds.is_some()
                    && self.paused_at_monotonic_seconds.is_some()
                    && self.active_session.is_some()
            }
        };
        if valid {
            Ok(())
        } else {
            Err(DomainError::InvalidState)
        }
    }

    pub fn snapshot(&self, now_monotonic_seconds: u64) -> TimerSnapshot {
        let remaining_seconds = match self.status {
            TimerStatus::Running => self
                .deadline_monotonic_seconds
                .unwrap_or(now_monotonic_seconds)
                .saturating_sub(now_monotonic_seconds),
            TimerStatus::Paused => self.paused_remaining_seconds.unwrap_or_default(),
            TimerStatus::Idle => u64::from(self.settings.focus_duration_minutes) * 60,
        };
        TimerSnapshot {
            revision: self.revision,
            status: self.status,
            phase: self.phase,
            remaining_seconds,
            deadline_utc_seconds: self.deadline_utc_seconds,
            focus_duration_minutes: self.settings.focus_duration_minutes,
            rest_duration_minutes: self.settings.rest_duration_minutes,
            daily_completed_focus_count: self.progress.daily_completed_focus_count,
            allowed_actions: self.allowed_actions(),
        }
    }

    pub fn allowed_actions(&self) -> Vec<TimerAction> {
        match self.status {
            TimerStatus::Idle => vec![
                TimerAction::StartFocus,
                TimerAction::StartRest,
                TimerAction::AdjustFocusDuration,
                TimerAction::AdjustRestDuration,
                TimerAction::ChangeSettings,
            ],
            TimerStatus::Running => vec![TimerAction::Pause, TimerAction::End],
            TimerStatus::Paused => vec![TimerAction::Resume, TimerAction::End],
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TimerSnapshot {
    pub revision: u64,
    pub status: TimerStatus,
    pub phase: Option<SessionPhase>,
    pub remaining_seconds: u64,
    pub deadline_utc_seconds: Option<i64>,
    pub focus_duration_minutes: u32,
    pub rest_duration_minutes: u32,
    pub daily_completed_focus_count: u32,
    pub allowed_actions: Vec<TimerAction>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DomainEvent {
    SnapshotChanged,
    SessionEnded(CompletedSession),
    RestStarted,
    RestEnded,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DomainError {
    InvalidSettings(crate::domain::SettingsError),
    InvalidState,
    ActionNotAllowed(TimerAction),
}
