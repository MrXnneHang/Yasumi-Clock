use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

pub const MIN_DURATION_MINUTES: u32 = 1;
pub const MAX_DURATION_MINUTES: u32 = 240;
pub const MIN_CYCLE_TARGET: u32 = 1;
pub const MAX_CYCLE_TARGET: u32 = 12;

#[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(transparent)]
pub struct PresetId(String);

impl PresetId {
    pub fn new(value: impl Into<String>) -> Result<Self, SettingsError> {
        let value = value.into();
        if value.is_empty()
            || value.len() > 48
            || !value
                .bytes()
                .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
        {
            return Err(SettingsError::InvalidPresetId);
        }
        Ok(Self(value))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl From<PresetId> for String {
    fn from(value: PresetId) -> Self {
        value.0
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", content = "minutes", rename_all = "camelCase")]
pub enum FocusDurationPlan {
    Fixed(u32),
    Sequence(Vec<u32>),
}

impl FocusDurationPlan {
    pub fn duration_minutes(&self, cycle_focus_count: u32) -> u32 {
        match self {
            Self::Fixed(minutes) => *minutes,
            Self::Sequence(minutes) => {
                let index = usize::try_from(cycle_focus_count).unwrap_or(usize::MAX);
                minutes
                    .get(index)
                    .or_else(|| minutes.last())
                    .copied()
                    .unwrap_or(MIN_DURATION_MINUTES)
            }
        }
    }

    fn validate(&self) -> Result<(), SettingsError> {
        let durations = match self {
            Self::Fixed(minutes) => std::slice::from_ref(minutes),
            Self::Sequence(minutes) if minutes.is_empty() => {
                return Err(SettingsError::EmptyDurationSequence);
            }
            Self::Sequence(minutes) => minutes.as_slice(),
        };

        if durations
            .iter()
            .any(|minutes| !(MIN_DURATION_MINUTES..=MAX_DURATION_MINUTES).contains(minutes))
        {
            return Err(SettingsError::InvalidDuration);
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Preset {
    pub id: PresetId,
    pub name: String,
    pub focus_duration: FocusDurationPlan,
    pub short_break_minutes: u32,
    pub long_break_minutes: u32,
    pub cycles_before_long_break: u32,
    pub force_rest: bool,
}

impl Preset {
    pub fn validate(&self) -> Result<(), SettingsError> {
        if self.name.trim().is_empty() {
            return Err(SettingsError::EmptyPresetName);
        }
        self.focus_duration.validate()?;
        validate_duration(self.short_break_minutes)?;
        validate_duration(self.long_break_minutes)?;
        if !(MIN_CYCLE_TARGET..=MAX_CYCLE_TARGET).contains(&self.cycles_before_long_break) {
            return Err(SettingsError::InvalidCycleTarget);
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSettings {
    pub presets: BTreeMap<PresetId, Preset>,
}

impl AppSettings {
    pub fn defaults() -> Self {
        let presets = [
            preset("custom", "自定义模式", 25, 5, 15, 4),
            preset("student", "学生模式", 45, 10, 30, 3),
            preset("professional", "专注工作", 25, 5, 15, 4),
            preset("fragmented-time", "碎片时间", 15, 3, 10, 4),
        ]
        .into_iter()
        .map(|preset| (preset.id.clone(), preset))
        .collect();
        Self { presets }
    }

    pub fn validate(&self) -> Result<(), SettingsError> {
        if self.presets.is_empty() {
            return Err(SettingsError::NoPresets);
        }
        for (id, preset) in &self.presets {
            if id != &preset.id {
                return Err(SettingsError::PresetKeyMismatch);
            }
            preset.validate()?;
        }
        Ok(())
    }

    pub fn preset(&self, id: &PresetId) -> Option<&Preset> {
        self.presets.get(id)
    }
}

impl Default for AppSettings {
    fn default() -> Self {
        Self::defaults()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SettingsError {
    InvalidPresetId,
    EmptyPresetName,
    InvalidDuration,
    EmptyDurationSequence,
    InvalidCycleTarget,
    NoPresets,
    PresetKeyMismatch,
}

fn validate_duration(minutes: u32) -> Result<(), SettingsError> {
    if (MIN_DURATION_MINUTES..=MAX_DURATION_MINUTES).contains(&minutes) {
        Ok(())
    } else {
        Err(SettingsError::InvalidDuration)
    }
}

fn preset(
    id: &str,
    name: &str,
    focus_minutes: u32,
    short_break_minutes: u32,
    long_break_minutes: u32,
    cycles_before_long_break: u32,
) -> Preset {
    Preset {
        id: PresetId::new(id).expect("built-in preset IDs are valid"),
        name: name.to_owned(),
        focus_duration: FocusDurationPlan::Fixed(focus_minutes),
        short_break_minutes,
        long_break_minutes,
        cycles_before_long_break,
        force_rest: false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_preserve_legacy_preset_durations() {
        let settings = AppSettings::defaults();
        settings.validate().unwrap();

        let student = settings.preset(&PresetId::new("student").unwrap()).unwrap();
        assert_eq!(student.focus_duration, FocusDurationPlan::Fixed(45));
        assert_eq!(student.short_break_minutes, 10);
        assert_eq!(student.long_break_minutes, 30);
        assert_eq!(student.cycles_before_long_break, 3);
    }

    #[test]
    fn sequence_uses_cycle_index_and_repeats_last_value() {
        let sequence = FocusDurationPlan::Sequence(vec![30, 25, 20]);
        assert_eq!(sequence.duration_minutes(0), 30);
        assert_eq!(sequence.duration_minutes(2), 20);
        assert_eq!(sequence.duration_minutes(20), 20);
        assert!(sequence.validate().is_ok());
    }

    #[test]
    fn rejects_invalid_ids_empty_sequences_and_mismatched_keys() {
        assert_eq!(PresetId::new(""), Err(SettingsError::InvalidPresetId));
        assert_eq!(
            PresetId::new("Not-Valid"),
            Err(SettingsError::InvalidPresetId)
        );
        assert_eq!(
            PresetId::new("has space"),
            Err(SettingsError::InvalidPresetId)
        );

        let mut settings = AppSettings::defaults();
        let custom = PresetId::new("custom").unwrap();
        settings.presets.get_mut(&custom).unwrap().focus_duration =
            FocusDurationPlan::Sequence(Vec::new());
        assert_eq!(
            settings.validate(),
            Err(SettingsError::EmptyDurationSequence)
        );

        let mut settings = AppSettings::defaults();
        settings.presets.get_mut(&custom).unwrap().id = PresetId::new("renamed").unwrap();
        assert_eq!(settings.validate(), Err(SettingsError::PresetKeyMismatch));

        assert_eq!(
            AppSettings {
                presets: BTreeMap::new()
            }
            .validate(),
            Err(SettingsError::NoPresets)
        );
    }

    #[test]
    fn rejects_zero_duration_and_invalid_cycle_target() {
        let mut settings = AppSettings::defaults();
        let id = PresetId::new("custom").unwrap();
        settings.presets.get_mut(&id).unwrap().short_break_minutes = 0;
        assert_eq!(settings.validate(), Err(SettingsError::InvalidDuration));

        settings.presets.get_mut(&id).unwrap().short_break_minutes = 5;
        settings
            .presets
            .get_mut(&id)
            .unwrap()
            .cycles_before_long_break = 0;
        assert_eq!(settings.validate(), Err(SettingsError::InvalidCycleTarget));
    }
}
