use serde::{Deserialize, Serialize};

pub const DEFAULT_FOCUS_DURATION_MINUTES: u32 = 20;
pub const MIN_FOCUS_DURATION_MINUTES: u32 = 0;
pub const MAX_FOCUS_DURATION_MINUTES: u32 = 60;
pub const DEFAULT_REST_DURATION_MINUTES: u32 = 5;
pub const MIN_REST_DURATION_MINUTES: u32 = 5;
pub const MAX_REST_DURATION_MINUTES: u32 = 30;

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSettings {
    pub focus_duration_minutes: u32,
    pub rest_duration_minutes: u32,
}

impl AppSettings {
    pub const fn defaults() -> Self {
        Self {
            focus_duration_minutes: DEFAULT_FOCUS_DURATION_MINUTES,
            rest_duration_minutes: DEFAULT_REST_DURATION_MINUTES,
        }
    }

    pub fn validate(&self) -> Result<(), SettingsError> {
        validate_focus_duration(self.focus_duration_minutes)?;
        validate_rest_duration(self.rest_duration_minutes)
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
    InvalidRestDuration,
}

pub fn validate_focus_duration(minutes: u32) -> Result<(), SettingsError> {
    if (MIN_FOCUS_DURATION_MINUTES..=MAX_FOCUS_DURATION_MINUTES).contains(&minutes) {
        Ok(())
    } else {
        Err(SettingsError::InvalidFocusDuration)
    }
}

pub fn validate_rest_duration(minutes: u32) -> Result<(), SettingsError> {
    if (MIN_REST_DURATION_MINUTES..=MAX_REST_DURATION_MINUTES).contains(&minutes) {
        Ok(())
    } else {
        Err(SettingsError::InvalidRestDuration)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_are_valid_and_keep_focus_and_rest_independent() {
        let settings = AppSettings::defaults();
        assert_eq!(settings.focus_duration_minutes, 20);
        assert_eq!(settings.rest_duration_minutes, 5);
        settings.validate().unwrap();
    }

    #[test]
    fn validates_focus_and_rest_boundaries() {
        for minutes in [0, 1, 30, 60] {
            assert!(validate_focus_duration(minutes).is_ok());
        }
        for minutes in [5, 15, 30] {
            assert!(validate_rest_duration(minutes).is_ok());
        }
        assert_eq!(
            validate_focus_duration(61),
            Err(SettingsError::InvalidFocusDuration)
        );
        assert_eq!(
            validate_rest_duration(4),
            Err(SettingsError::InvalidRestDuration)
        );
        assert_eq!(
            validate_rest_duration(31),
            Err(SettingsError::InvalidRestDuration)
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
