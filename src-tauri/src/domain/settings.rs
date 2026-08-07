use serde::{Deserialize, Serialize};

pub const DEFAULT_FOCUS_DURATION_MINUTES: u32 = 20;
pub const MIN_FOCUS_DURATION_MINUTES: u32 = 0;
pub const MAX_FOCUS_DURATION_MINUTES: u32 = 60;

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSettings {
    pub focus_duration_minutes: u32,
}

impl AppSettings {
    pub const fn defaults() -> Self {
        Self {
            focus_duration_minutes: DEFAULT_FOCUS_DURATION_MINUTES,
        }
    }

    pub fn validate(&self) -> Result<(), SettingsError> {
        validate_focus_duration(self.focus_duration_minutes)
    }
}

impl Default for AppSettings {
    fn default() -> Self {
        Self::defaults()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SettingsError {
    InvalidFocusDuration,
}

pub fn validate_focus_duration(minutes: u32) -> Result<(), SettingsError> {
    if (MIN_FOCUS_DURATION_MINUTES..=MAX_FOCUS_DURATION_MINUTES).contains(&minutes) {
        Ok(())
    } else {
        Err(SettingsError::InvalidFocusDuration)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_are_valid() {
        let settings = AppSettings::defaults();
        assert_eq!(settings.focus_duration_minutes, 20);
        settings.validate().unwrap();
    }

    #[test]
    fn validates_focus_boundaries() {
        for minutes in [0, 1, 30, 60] {
            assert!(validate_focus_duration(minutes).is_ok());
        }
        assert_eq!(
            validate_focus_duration(61),
            Err(SettingsError::InvalidFocusDuration)
        );
    }

    #[test]
    fn committed_settings_fixture_matches_rust_serialization() {
        let actual = serde_json::to_value(AppSettings::defaults()).unwrap();
        let expected: serde_json::Value =
            serde_json::from_str(include_str!("../../../contracts/app-settings.json")).unwrap();
        assert_eq!(actual, expected);
    }
}
