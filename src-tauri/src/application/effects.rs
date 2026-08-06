use serde::{Deserialize, Serialize};

use crate::domain::{AppSettings, CompletedSession, SessionPhase, TimerSnapshot};

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum AppEffect {
    PublishTimerSnapshot,
    PublishSettings(AppSettings),
    PersistRuntimeState,
    AppendSessionRecord(CompletedSession),
    ShowRestOverlay { phase: SessionPhase, force: bool },
    HideRestOverlay,
    ShowLastMinuteOverlay,
    HideLastMinuteOverlay,
    PlayNotification,
    StartWhiteNoise,
    StopWhiteNoise,
    ArmIdleReminder,
    CancelIdleReminder,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TransitionOutcome {
    pub snapshot: TimerSnapshot,
    pub effects: Vec<AppEffect>,
}
