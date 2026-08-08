use serde::{Deserialize, Serialize};

use crate::{
    domain::{DomainError, SettingsError},
    infrastructure::MediaLibraryError,
};

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CommandError {
    pub code: String,
    pub message: String,
    pub retryable: bool,
}

impl CommandError {
    pub fn state_unavailable() -> Self {
        Self::new(
            "state_unavailable",
            "The timer service is unavailable.",
            true,
        )
    }

    pub fn stale_revision(expected: u64, actual: u64) -> Self {
        Self::new(
            "stale_revision",
            format!("Expected timer revision {expected}, but the current revision is {actual}."),
            true,
        )
    }

    pub fn persistence_failed(message: impl Into<String>) -> Self {
        Self::new("persistence_failed", message, true)
    }

    pub fn event_publish_failed(message: impl Into<String>) -> Self {
        Self::new("event_publish_failed", message, true)
    }

    pub fn invalid_media_reference() -> Self {
        Self::new(
            "invalid_media_reference",
            "The selected imported media is unavailable.",
            false,
        )
    }

    fn new(code: impl Into<String>, message: impl Into<String>, retryable: bool) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
            retryable,
        }
    }
}

impl From<DomainError> for CommandError {
    fn from(error: DomainError) -> Self {
        match error {
            DomainError::InvalidSettings(settings_error) => settings_error.into(),
            DomainError::InvalidState => {
                Self::new("invalid_state", "The timer state is inconsistent.", false)
            }
            DomainError::ActionNotAllowed(action) => Self::new(
                "action_not_allowed",
                format!("The timer action {action:?} is not allowed in the current state."),
                false,
            ),
        }
    }
}

impl From<SettingsError> for CommandError {
    fn from(error: SettingsError) -> Self {
        Self::new(
            "invalid_settings",
            format!("Settings validation failed: {error:?}."),
            false,
        )
    }
}

impl From<MediaLibraryError> for CommandError {
    fn from(error: MediaLibraryError) -> Self {
        match error {
            MediaLibraryError::InvalidFormat | MediaLibraryError::InvalidMedia => Self::new(
                "invalid_media",
                "The selected file is not a compatible animation media file.",
                false,
            ),
            MediaLibraryError::MediaTooLarge => Self::new(
                "media_too_large",
                "The selected media file exceeds the 100 MB limit.",
                false,
            ),
            MediaLibraryError::Io(_) => Self::new(
                "media_import_failed",
                "The selected media file could not be imported.",
                true,
            ),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::domain::TimerAction;

    #[test]
    fn committed_error_fixture_matches_rust_serialization() {
        let error = CommandError::from(DomainError::ActionNotAllowed(TimerAction::Pause));
        let actual = serde_json::to_value(error).unwrap();
        let expected: serde_json::Value =
            serde_json::from_str(include_str!("../../../contracts/command-error.json")).unwrap();
        assert_eq!(actual, expected);
    }

    #[test]
    fn maps_domain_errors_to_stable_safe_codes() {
        let error = CommandError::from(DomainError::ActionNotAllowed(TimerAction::Pause));
        assert_eq!(error.code, "action_not_allowed");
        assert!(!error.retryable);
        assert!(error.message.contains("Pause"));

        let value = serde_json::to_value(error).unwrap();
        assert_eq!(value["retryable"], false);
        assert!(value.get("code").is_some());
    }
}
