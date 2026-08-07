use serde::{Deserialize, Serialize};

use crate::domain::{AppSettings, CompletedSession, TimerSnapshot};

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum AppEffect {
    PublishTimerSnapshot,
    PublishSettings(AppSettings),
    PersistRuntimeState,
    AppendSessionRecord(CompletedSession),
    ShowRestOverlay,
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
