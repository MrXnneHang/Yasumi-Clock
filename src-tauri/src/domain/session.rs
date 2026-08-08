use serde::{Deserialize, Serialize};

use super::timer::SessionPhase;

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionMetadata {
    pub session_id: String,
    pub work_item_id: Option<String>,
    pub origin_session_id: Option<String>,
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
    Ended,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompletedSession {
    pub metadata: SessionMetadata,
    pub ended_at_utc_seconds: i64,
    pub reason: SessionEndReason,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionHistoryBatch {
    pub batch_id: String,
    pub events: Vec<SessionHistoryEvent>,
}

impl SessionHistoryBatch {
    pub fn new(events: Vec<SessionHistoryEvent>) -> Self {
        Self {
            batch_id: uuid::Uuid::new_v4().to_string(),
            events,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(
    tag = "kind",
    rename_all = "camelCase",
    rename_all_fields = "camelCase"
)]
pub enum SessionHistoryEvent {
    Started {
        session_id: String,
        work_item_id: Option<String>,
        origin_session_id: Option<String>,
        phase: SessionPhase,
        started_at_utc_seconds: i64,
        planned_duration_seconds: u64,
    },
    Completed {
        session_id: String,
        ended_at_utc_seconds: i64,
        accumulated_pause_seconds: u64,
        pause_count: u32,
    },
    Ended {
        session_id: String,
        ended_at_utc_seconds: i64,
        accumulated_pause_seconds: u64,
        pause_count: u32,
    },
}

impl SessionMetadata {
    pub fn started_event(&self) -> SessionHistoryEvent {
        SessionHistoryEvent::Started {
            session_id: self.session_id.clone(),
            work_item_id: self.work_item_id.clone(),
            origin_session_id: self.origin_session_id.clone(),
            phase: self.phase,
            started_at_utc_seconds: self.started_at_utc_seconds,
            planned_duration_seconds: self.planned_duration_seconds,
        }
    }
}

impl CompletedSession {
    pub fn history_event(&self) -> SessionHistoryEvent {
        let metadata = &self.metadata;
        match self.reason {
            SessionEndReason::Completed => SessionHistoryEvent::Completed {
                session_id: metadata.session_id.clone(),
                ended_at_utc_seconds: self.ended_at_utc_seconds,
                accumulated_pause_seconds: metadata.accumulated_pause_seconds,
                pause_count: metadata.pause_count,
            },
            SessionEndReason::Ended => SessionHistoryEvent::Ended {
                session_id: metadata.session_id.clone(),
                ended_at_utc_seconds: self.ended_at_utc_seconds,
                accumulated_pause_seconds: metadata.accumulated_pause_seconds,
                pause_count: metadata.pause_count,
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn metadata() -> SessionMetadata {
        SessionMetadata {
            session_id: "focus-1".into(),
            work_item_id: Some("todo-1".into()),
            origin_session_id: None,
            phase: SessionPhase::Focus,
            planned_duration_seconds: 1_500,
            started_at_utc_seconds: 1_700_000_000,
            accumulated_pause_seconds: 12,
            pause_count: 2,
        }
    }

    #[test]
    fn started_event_retains_optional_work_item_attribution() {
        let event = metadata().started_event();
        assert_eq!(
            serde_json::to_value(event).unwrap(),
            serde_json::json!({
                "kind": "started",
                "sessionId": "focus-1",
                "workItemId": "todo-1",
                "originSessionId": null,
                "phase": "focus",
                "startedAtUtcSeconds": 1_700_000_000,
                "plannedDurationSeconds": 1_500
            })
        );
    }

    #[test]
    fn terminal_events_distinguish_completion_from_manual_end() {
        let completed = CompletedSession {
            metadata: metadata(),
            ended_at_utc_seconds: 1_700_001_500,
            reason: SessionEndReason::Completed,
        };
        assert!(matches!(
            completed.history_event(),
            SessionHistoryEvent::Completed { .. }
        ));

        let ended = CompletedSession {
            reason: SessionEndReason::Ended,
            ..completed
        };
        assert!(matches!(
            ended.history_event(),
            SessionHistoryEvent::Ended { .. }
        ));
    }
}
