use serde::{Deserialize, Serialize};

use super::timer::SessionPhase;

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionMetadata {
    pub phase: SessionPhase,
    pub planned_duration_seconds: u64,
    pub started_at_utc_seconds: i64,
    pub accumulated_pause_seconds: u64,
    pub pause_count: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum SessionEndReason {
    Completed,
    Interrupted,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompletedSession {
    pub metadata: SessionMetadata,
    pub ended_at_utc_seconds: i64,
    pub reason: SessionEndReason,
}
