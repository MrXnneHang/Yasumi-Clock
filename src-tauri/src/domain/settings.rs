use serde::{Deserialize, Serialize};

pub const DEFAULT_FOCUS_DURATION_MINUTES: u32 = 20;
pub const MIN_FOCUS_DURATION_MINUTES: u32 = 0;
pub const MAX_FOCUS_DURATION_MINUTES: u32 = 60;

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum BuiltinMediaId {
    Play,
    Work,
    Mayi,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", tag = "kind")]
pub enum MediaRef {
    Builtin { id: BuiltinMediaId },
    Imported { id: String },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum RestPlaybackMode {
    Once,
    Loop,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AnimationSettings {
    pub idle: MediaRef,
    pub focus: MediaRef,
    pub rest: MediaRef,
    pub rest_playback: RestPlaybackMode,
}

impl AnimationSettings {
    pub const fn defaults() -> Self {
        Self {
            idle: MediaRef::Builtin {
                id: BuiltinMediaId::Play,
            },
            focus: MediaRef::Builtin {
                id: BuiltinMediaId::Work,
            },
            rest: MediaRef::Builtin {
                id: BuiltinMediaId::Mayi,
            },
            rest_playback: RestPlaybackMode::Once,
        }
    }

    fn validate(&self) -> Result<(), SettingsError> {
        validate_media_ref(&self.idle, MediaRole::Idle)?;
        validate_media_ref(&self.focus, MediaRole::Focus)?;
        validate_media_ref(&self.rest, MediaRole::Rest)
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSettings {
    pub focus_duration_minutes: u32,
    pub animations: AnimationSettings,
}

impl AppSettings {
    pub const fn defaults() -> Self {
        Self {
            focus_duration_minutes: DEFAULT_FOCUS_DURATION_MINUTES,
            animations: AnimationSettings::defaults(),
        }
    }

    pub fn validate(&self) -> Result<(), SettingsError> {
        validate_focus_duration(self.focus_duration_minutes)?;
        self.animations.validate()
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
    InvalidMediaReference,
}

#[derive(Clone, Copy)]
enum MediaRole {
    Idle,
    Focus,
    Rest,
}

fn validate_media_ref(media: &MediaRef, role: MediaRole) -> Result<(), SettingsError> {
    match media {
        MediaRef::Builtin { id } => match (role, id) {
            (MediaRole::Idle, BuiltinMediaId::Play)
            | (MediaRole::Focus, BuiltinMediaId::Work)
            | (MediaRole::Rest, BuiltinMediaId::Mayi) => Ok(()),
            _ => Err(SettingsError::InvalidMediaReference),
        },
        MediaRef::Imported { id } if id.is_empty() => Err(SettingsError::InvalidMediaReference),
        MediaRef::Imported { .. } => Ok(()),
    }
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
        assert_eq!(settings.animations, AnimationSettings::defaults());
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
    fn rejects_incompatible_builtins_and_allows_imported_video_for_every_role() {
        let mut settings = AppSettings::defaults();
        settings.animations.idle = MediaRef::Builtin {
            id: BuiltinMediaId::Work,
        };
        assert_eq!(
            settings.validate(),
            Err(SettingsError::InvalidMediaReference)
        );

        let imported = MediaRef::Imported {
            id: "media-1".into(),
        };
        settings.animations.idle = imported.clone();
        settings.animations.focus = imported.clone();
        settings.animations.rest = imported;
        settings.validate().unwrap();
    }

    #[test]
    fn committed_settings_fixture_matches_rust_serialization() {
        let actual = serde_json::to_value(AppSettings::defaults()).unwrap();
        let expected: serde_json::Value =
            serde_json::from_str(include_str!("../../../contracts/app-settings.json")).unwrap();
        assert_eq!(actual, expected);
    }
}
