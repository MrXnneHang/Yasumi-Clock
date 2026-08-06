use serde::{Deserialize, Serialize};

use crate::domain::{
    CompletedSession, PresetId, SessionMetadata, TimerProgress, settings::AppSettings,
};

pub const CLASSIC_DEFAULT_FOCUS_MINUTES: u32 = 20;
pub const CLASSIC_MIN_FOCUS_MINUTES: u32 = 5;
pub const CLASSIC_MAX_FOCUS_MINUTES: u32 = 40;
pub const CLASSIC_FOCUS_STEP_MINUTES: i32 = 5;
pub const CLASSIC_BREAK_MINUTES: u32 = 5;

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
    ShortBreak,
    LongBreak,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", content = "presetId", rename_all = "camelCase")]
pub enum TimerMode {
    Classic,
    Preset(PresetId),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum TimerAction {
    StartFocus,
    Pause,
    Resume,
    Reset,
    DismissBreak,
    AdjustClassicDuration,
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
    pub mode: TimerMode,
    pub classic_focus_minutes: u32,
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
            mode: TimerMode::Classic,
            classic_focus_minutes: CLASSIC_DEFAULT_FOCUS_MINUTES,
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
            TimerStatus::Idle => self.idle_display_seconds(),
        };
        let cycle_target = self.selected_cycle_target();
        TimerSnapshot {
            revision: self.revision,
            status: self.status,
            phase: self.phase,
            mode: self.mode.clone(),
            remaining_seconds,
            deadline_utc_seconds: self.deadline_utc_seconds,
            cycle_focus_count: self.progress.cycle_focus_count,
            cycle_target,
            daily_completed_focus_count: self.progress.daily_completed_focus_count,
            next_phase: self.next_phase(),
            allowed_actions: self.allowed_actions(),
        }
    }

    pub fn allowed_actions(&self) -> Vec<TimerAction> {
        match (self.status, self.phase) {
            (TimerStatus::Idle, _) => vec![
                TimerAction::StartFocus,
                TimerAction::AdjustClassicDuration,
                TimerAction::ChangeSettings,
            ],
            (TimerStatus::Running, Some(SessionPhase::Focus)) => {
                vec![TimerAction::Pause, TimerAction::Reset]
            }
            (TimerStatus::Paused, Some(SessionPhase::Focus)) => {
                vec![TimerAction::Resume, TimerAction::Reset]
            }
            (TimerStatus::Running, Some(_)) => {
                let mut actions = vec![TimerAction::Pause, TimerAction::Reset];
                if !self.selected_force_rest() {
                    actions.push(TimerAction::DismissBreak);
                }
                actions
            }
            (TimerStatus::Paused, Some(_)) => {
                let mut actions = vec![TimerAction::Resume, TimerAction::Reset];
                if !self.selected_force_rest() {
                    actions.push(TimerAction::DismissBreak);
                }
                actions
            }
            _ => Vec::new(),
        }
    }

    pub(crate) fn selected_preset(&self) -> Result<&crate::domain::Preset, DomainError> {
        match &self.mode {
            TimerMode::Classic => Err(DomainError::WrongMode),
            TimerMode::Preset(id) => self
                .settings
                .preset(id)
                .ok_or_else(|| DomainError::UnknownPreset(id.clone())),
        }
    }

    pub(crate) fn selected_force_rest(&self) -> bool {
        self.selected_preset()
            .map(|preset| preset.force_rest)
            .unwrap_or(false)
    }

    pub(crate) fn selected_cycle_target(&self) -> Option<u32> {
        self.selected_preset()
            .map(|preset| preset.cycles_before_long_break)
            .ok()
    }

    pub(crate) fn idle_display_seconds(&self) -> u64 {
        match self.selected_preset() {
            Ok(preset) => {
                u64::from(
                    preset
                        .focus_duration
                        .duration_minutes(self.progress.cycle_focus_count),
                ) * 60
            }
            Err(_) => u64::from(self.classic_focus_minutes) * 60,
        }
    }

    fn next_phase(&self) -> Option<SessionPhase> {
        match self.phase {
            Some(SessionPhase::Focus) => match self.selected_cycle_target() {
                Some(target) if self.progress.cycle_focus_count.saturating_add(1) >= target => {
                    Some(SessionPhase::LongBreak)
                }
                _ => Some(SessionPhase::ShortBreak),
            },
            Some(SessionPhase::ShortBreak | SessionPhase::LongBreak) => None,
            None => Some(SessionPhase::Focus),
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TimerSnapshot {
    pub revision: u64,
    pub status: TimerStatus,
    pub phase: Option<SessionPhase>,
    pub mode: TimerMode,
    pub remaining_seconds: u64,
    pub deadline_utc_seconds: Option<i64>,
    pub cycle_focus_count: u32,
    pub cycle_target: Option<u32>,
    pub daily_completed_focus_count: u32,
    pub next_phase: Option<SessionPhase>,
    pub allowed_actions: Vec<TimerAction>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DomainEvent {
    SnapshotChanged,
    SessionEnded(CompletedSession),
    BreakStarted { phase: SessionPhase, force: bool },
    BreakEnded,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DomainError {
    InvalidSettings(crate::domain::SettingsError),
    InvalidState,
    ActionNotAllowed(TimerAction),
    UnknownPreset(PresetId),
    WrongMode,
    InvalidClassicDuration,
}
