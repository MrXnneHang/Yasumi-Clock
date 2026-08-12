use std::{
    collections::{HashMap, HashSet},
    fs::{self, OpenOptions},
    io::{self, Write},
    path::{Path, PathBuf},
};

use atomic_write_file::AtomicWriteFile;
use chrono::{Local, TimeZone, Timelike};
use serde::{Deserialize, Serialize};

use crate::domain::{AppSettings, SessionHistoryBatch, SessionHistoryEvent, SessionPhase};

const SETTINGS_SCHEMA_VERSION: u32 = 2;
const HISTORY_SCHEMA_VERSION: u32 = 1;

#[derive(Debug)]
pub enum PersistenceError {
    Io(io::Error),
    Json(serde_json::Error),
    UnsupportedSchema(u32),
    CorruptHistory { line: usize },
}

impl std::fmt::Display for PersistenceError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Io(error) => write!(formatter, "persistence I/O failed: {error}"),
            Self::Json(error) => write!(formatter, "persistence data is invalid: {error}"),
            Self::UnsupportedSchema(version) => {
                write!(
                    formatter,
                    "unsupported persistence schema version: {version}"
                )
            }
            Self::CorruptHistory { line } => {
                write!(formatter, "session history is corrupt at line {line}")
            }
        }
    }
}

impl std::error::Error for PersistenceError {}

impl From<io::Error> for PersistenceError {
    fn from(error: io::Error) -> Self {
        Self::Io(error)
    }
}

impl From<serde_json::Error> for PersistenceError {
    fn from(error: serde_json::Error) -> Self {
        Self::Json(error)
    }
}

#[derive(Clone, Debug)]
pub struct Persistence {
    settings_v1_path: PathBuf,
    settings_v2_path: PathBuf,
    history_path: PathBuf,
}

#[derive(Clone, Debug, Default)]
pub struct HistoryIndex {
    batch_ids: HashSet<String>,
    events: Vec<SessionHistoryEvent>,
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct SettingsDocumentV2 {
    schema_version: u32,
    settings: AppSettings,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct SettingsDocumentV1 {
    schema_version: u32,
    settings: SettingsV1,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct SettingsV1 {
    focus_duration_minutes: u32,
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct HistoryBatch {
    schema_version: u32,
    batch_id: String,
    events: Vec<SessionHistoryEvent>,
}

impl Persistence {
    pub fn new(config_directory: PathBuf, data_directory: PathBuf) -> Self {
        Self {
            settings_v1_path: config_directory.join("settings.v1.json"),
            settings_v2_path: config_directory.join("settings.v2.json"),
            history_path: data_directory.join("session-history.v1.jsonl"),
        }
    }

    pub fn load_settings(&self) -> Result<AppSettings, PersistenceError> {
        match fs::read_to_string(&self.settings_v2_path) {
            Ok(contents) => load_settings_v2(&contents),
            Err(error) if error.kind() == io::ErrorKind::NotFound => self.migrate_settings_v1(),
            Err(error) => Err(error.into()),
        }
    }

    pub fn save_settings(&self, settings: &AppSettings) -> Result<(), PersistenceError> {
        validate_settings(settings)?;
        let contents = serde_json::to_vec_pretty(&SettingsDocumentV2 {
            schema_version: SETTINGS_SCHEMA_VERSION,
            settings: settings.clone(),
        })?;
        atomic_replace(&self.settings_v2_path, &contents)
    }

    fn migrate_settings_v1(&self) -> Result<AppSettings, PersistenceError> {
        let contents = match fs::read_to_string(&self.settings_v1_path) {
            Ok(contents) => contents,
            Err(error) if error.kind() == io::ErrorKind::NotFound => {
                return Ok(AppSettings::defaults());
            }
            Err(error) => return Err(error.into()),
        };
        let document: SettingsDocumentV1 = serde_json::from_str(&contents)?;
        ensure_schema(document.schema_version, 1)?;
        let settings = AppSettings {
            focus_duration_minutes: document.settings.focus_duration_minutes,
            ..AppSettings::defaults()
        };
        validate_settings(&settings)?;
        self.save_settings(&settings)?;
        Ok(settings)
    }

    pub fn load_history(&self) -> Result<HistoryIndex, PersistenceError> {
        let contents = match fs::read_to_string(&self.history_path) {
            Ok(contents) => contents,
            Err(error) if error.kind() == io::ErrorKind::NotFound => {
                return Ok(HistoryIndex::default());
            }
            Err(error) => return Err(error.into()),
        };

        let ends_with_newline = contents.ends_with('\n');
        let lines: Vec<_> = contents.split('\n').collect();
        let mut history = HistoryIndex::default();
        for (index, line) in lines.iter().enumerate() {
            let line = line.trim_end_matches('\r');
            if line.is_empty() {
                continue;
            }
            match serde_json::from_str::<HistoryBatch>(line) {
                Ok(batch) => {
                    ensure_schema(batch.schema_version, HISTORY_SCHEMA_VERSION)?;
                    history.append(SessionHistoryBatch {
                        batch_id: batch.batch_id,
                        events: batch.events,
                    });
                }
                Err(_) if index + 1 == lines.len() && !ends_with_newline => break,
                Err(_) => return Err(PersistenceError::CorruptHistory { line: index + 1 }),
            }
        }
        Ok(history)
    }

    pub fn append_history(&self, batch: &SessionHistoryBatch) -> Result<(), PersistenceError> {
        if batch.events.is_empty() || self.load_history()?.contains_batch(&batch.batch_id) {
            return Ok(());
        }
        let parent = self.history_path.parent().expect("history path has parent");
        fs::create_dir_all(parent)?;
        truncate_incomplete_final_line(&self.history_path)?;
        let mut line = serde_json::to_vec(&HistoryBatch {
            schema_version: HISTORY_SCHEMA_VERSION,
            batch_id: batch.batch_id.clone(),
            events: batch.events.clone(),
        })?;
        line.push(b'\n');
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.history_path)?;
        file.write_all(&line)?;
        file.sync_data()?;
        Ok(())
    }
}

impl HistoryIndex {
    pub fn append(&mut self, batch: SessionHistoryBatch) {
        if self.batch_ids.insert(batch.batch_id) {
            self.events.extend(batch.events);
        }
    }

    pub fn contains_batch(&self, batch_id: &str) -> bool {
        self.batch_ids.contains(batch_id)
    }

    pub fn daily_completed_focus_count(&self, now_utc_seconds: i64) -> u32 {
        let logical_day = logical_day_key(now_utc_seconds);
        let phases: HashMap<String, SessionPhase> =
            self.events
                .iter()
                .fold(HashMap::new(), |mut phases, event| {
                    if let SessionHistoryEvent::Started {
                        session_id, phase, ..
                    } = event
                    {
                        phases.insert(session_id.clone(), *phase);
                    }
                    phases
                });
        let mut counted = HashSet::new();
        self.events
            .iter()
            .filter_map(|event| match event {
                SessionHistoryEvent::Completed {
                    session_id,
                    ended_at_utc_seconds,
                    ..
                } if phases.get(session_id).copied() == Some(SessionPhase::Focus)
                    && logical_day_key(*ended_at_utc_seconds) == logical_day
                    && counted.insert(session_id) =>
                {
                    Some(())
                }
                _ => None,
            })
            .count()
            .try_into()
            .unwrap_or(u32::MAX)
    }
}

fn load_settings_v2(contents: &str) -> Result<AppSettings, PersistenceError> {
    let value: serde_json::Value = serde_json::from_str(contents)?;
    let schema_version = value
        .get("schemaVersion")
        .and_then(serde_json::Value::as_u64)
        .and_then(|version| u32::try_from(version).ok())
        .ok_or_else(|| {
            PersistenceError::Json(serde_json::Error::io(io::Error::new(
                io::ErrorKind::InvalidData,
                "settings schema version is missing or invalid",
            )))
        })?;
    ensure_schema(schema_version, SETTINGS_SCHEMA_VERSION)?;
    let document: SettingsDocumentV2 = serde_json::from_value(value)?;
    validate_settings(&document.settings)?;
    Ok(document.settings)
}

fn validate_settings(settings: &AppSettings) -> Result<(), PersistenceError> {
    settings.validate().map_err(|error| {
        PersistenceError::Json(serde_json::Error::io(io::Error::new(
            io::ErrorKind::InvalidData,
            format!("settings validation failed: {error:?}"),
        )))
    })
}

fn ensure_schema(version: u32, expected: u32) -> Result<(), PersistenceError> {
    if version == expected {
        Ok(())
    } else {
        Err(PersistenceError::UnsupportedSchema(version))
    }
}

fn logical_day_key(utc_seconds: i64) -> chrono::NaiveDate {
    let local = Local
        .timestamp_opt(utc_seconds, 0)
        .single()
        .unwrap_or_else(|| Local.timestamp_opt(0, 0).unwrap());
    if local.hour() < 5 {
        local.date_naive().pred_opt().unwrap_or(local.date_naive())
    } else {
        local.date_naive()
    }
}

fn truncate_incomplete_final_line(path: &Path) -> Result<(), PersistenceError> {
    let contents = match fs::read(path) {
        Ok(contents) => contents,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(()),
        Err(error) => return Err(error.into()),
    };
    if contents.ends_with(b"\n") {
        return Ok(());
    }
    let final_line = contents
        .rsplit(|byte| *byte == b'\n')
        .next()
        .expect("split always returns one segment");
    if serde_json::from_slice::<HistoryBatch>(final_line).is_ok() {
        let mut file = OpenOptions::new().append(true).open(path)?;
        file.write_all(b"\n")?;
        file.sync_data()?;
        return Ok(());
    }
    let complete_length = contents
        .iter()
        .rposition(|byte| *byte == b'\n')
        .map_or(0, |index| index + 1);
    let file = OpenOptions::new().write(true).open(path)?;
    file.set_len(u64::try_from(complete_length).expect("buffer length fits u64"))?;
    file.sync_all()?;
    Ok(())
}

fn atomic_replace(path: &Path, contents: &[u8]) -> Result<(), PersistenceError> {
    let parent = path.parent().expect("settings path has parent");
    fs::create_dir_all(parent)?;
    let mut file = AtomicWriteFile::options().open(path)?;
    file.write_all(contents)?;
    file.write_all(b"\n")?;
    file.sync_all()?;
    file.commit()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::{
        fs,
        time::{SystemTime, UNIX_EPOCH},
    };

    use super::*;

    fn directory(name: &str) -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("yasumi-clock-{name}-{nonce}"))
    }

    fn started(session_id: &str, phase: SessionPhase, utc_seconds: i64) -> SessionHistoryEvent {
        SessionHistoryEvent::Started {
            session_id: session_id.into(),
            work_item_id: None,
            origin_session_id: None,
            phase,
            started_at_utc_seconds: utc_seconds,
            planned_duration_seconds: 300,
        }
    }

    fn completed(session_id: &str, utc_seconds: i64) -> SessionHistoryEvent {
        SessionHistoryEvent::Completed {
            session_id: session_id.into(),
            ended_at_utc_seconds: utc_seconds,
            accumulated_pause_seconds: 0,
            pause_count: 0,
        }
    }

    #[test]
    fn settings_round_trip_through_versioned_document() {
        let root = directory("settings");
        let persistence = Persistence::new(root.join("config"), root.join("data"));
        let settings = AppSettings {
            focus_duration_minutes: 25,
            ..AppSettings::defaults()
        };
        persistence.save_settings(&settings).unwrap();
        assert_eq!(persistence.load_settings().unwrap(), settings);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn atomically_replaces_existing_settings() {
        let root = directory("settings-replace");
        let persistence = Persistence::new(root.join("config"), root.join("data"));
        persistence
            .save_settings(&AppSettings {
                focus_duration_minutes: 20,
                ..AppSettings::defaults()
            })
            .unwrap();
        persistence
            .save_settings(&AppSettings {
                focus_duration_minutes: 45,
                ..AppSettings::defaults()
            })
            .unwrap();
        assert_eq!(
            persistence.load_settings().unwrap(),
            AppSettings {
                focus_duration_minutes: 45,
                ..AppSettings::defaults()
            }
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn migrates_v1_settings_with_bundled_animation_defaults() {
        let root = directory("migrate-settings");
        let persistence = Persistence::new(root.join("config"), root.join("data"));
        fs::create_dir_all(persistence.settings_v1_path.parent().unwrap()).unwrap();
        fs::write(
            &persistence.settings_v1_path,
            r#"{"schemaVersion":1,"settings":{"focusDurationMinutes":25}}"#,
        )
        .unwrap();

        assert_eq!(
            persistence.load_settings().unwrap(),
            AppSettings {
                focus_duration_minutes: 25,
                ..AppSettings::defaults()
            }
        );
        assert!(persistence.settings_v1_path.exists());
        assert!(persistence.settings_v2_path.exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn loads_existing_v2_settings_with_system_theme_default() {
        let root = directory("settings-v2-theme-default");
        let persistence = Persistence::new(root.join("config"), root.join("data"));
        fs::create_dir_all(persistence.settings_v2_path.parent().unwrap()).unwrap();
        fs::write(
            &persistence.settings_v2_path,
            r#"{"schemaVersion":2,"settings":{"focusDurationMinutes":25,"animations":{"idle":{"kind":"builtin","id":"play"},"focus":{"kind":"builtin","id":"work"},"rest":{"kind":"builtin","id":"mayi"},"restPlayback":"once"}}}"#,
        )
        .unwrap();

        assert_eq!(
            persistence.load_settings().unwrap(),
            AppSettings {
                focus_duration_minutes: 25,
                ..AppSettings::defaults()
            }
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_future_settings_schema() {
        let root = directory("future-settings");
        let persistence = Persistence::new(root.join("config"), root.join("data"));
        fs::create_dir_all(persistence.settings_v2_path.parent().unwrap()).unwrap();
        fs::write(
            &persistence.settings_v2_path,
            r#"{"schemaVersion":3,"settings":{"focusDurationMinutes":20}}"#,
        )
        .unwrap();
        assert!(matches!(
            persistence.load_settings(),
            Err(PersistenceError::UnsupportedSchema(3))
        ));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn appends_and_reads_a_complete_history_batch() {
        let root = directory("history");
        let persistence = Persistence::new(root.join("config"), root.join("data"));
        let batch = SessionHistoryBatch {
            batch_id: "batch-1".into(),
            events: vec![
                started("focus-1", SessionPhase::Focus, 1_700_000_000),
                completed("focus-1", 1_700_000_300),
                started("rest-1", SessionPhase::Rest, 1_700_000_300),
            ],
        };
        persistence.append_history(&batch).unwrap();
        persistence.append_history(&batch).unwrap();
        let history = persistence.load_history().unwrap();
        assert_eq!(history.events, batch.events);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn preserves_a_complete_final_batch_without_a_newline_before_appending() {
        let root = directory("final-batch-without-newline");
        let persistence = Persistence::new(root.join("config"), root.join("data"));
        let first = SessionHistoryBatch {
            batch_id: "batch-1".into(),
            events: vec![started("focus-1", SessionPhase::Focus, 0)],
        };
        persistence.append_history(&first).unwrap();
        let mut contents = fs::read(&persistence.history_path).unwrap();
        contents.pop();
        fs::write(&persistence.history_path, contents).unwrap();
        let second = SessionHistoryBatch {
            batch_id: "batch-2".into(),
            events: vec![completed("focus-1", 300)],
        };
        persistence.append_history(&second).unwrap();
        let history = persistence.load_history().unwrap();
        assert_eq!(history.events, [first.events, second.events].concat());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn derives_completed_focus_count_from_completed_history_events() {
        let utc_seconds = 1_700_000_000;
        let mut history = HistoryIndex::default();
        history.append(SessionHistoryBatch {
            batch_id: "batch-1".into(),
            events: vec![
                started("focus-completed", SessionPhase::Focus, utc_seconds),
                completed("focus-completed", utc_seconds),
                started("focus-ended", SessionPhase::Focus, utc_seconds),
                SessionHistoryEvent::Ended {
                    session_id: "focus-ended".into(),
                    ended_at_utc_seconds: utc_seconds,
                    accumulated_pause_seconds: 0,
                    pause_count: 0,
                },
                started("rest-completed", SessionPhase::Rest, utc_seconds),
                completed("rest-completed", utc_seconds),
            ],
        });
        assert_eq!(history.daily_completed_focus_count(utc_seconds), 1);
    }

    #[test]
    fn attributes_completed_focus_to_its_completion_logical_day() {
        let before_boundary = Local::now().date_naive().and_hms_opt(4, 59, 0).unwrap();
        let after_boundary = Local::now().date_naive().and_hms_opt(5, 1, 0).unwrap();
        let before_utc = Local
            .from_local_datetime(&before_boundary)
            .earliest()
            .unwrap()
            .timestamp();
        let after_utc = Local
            .from_local_datetime(&after_boundary)
            .earliest()
            .unwrap()
            .timestamp();
        let mut history = HistoryIndex::default();
        history.append(SessionHistoryBatch {
            batch_id: "batch-boundary".into(),
            events: vec![
                started("focus-1", SessionPhase::Focus, before_utc),
                completed("focus-1", after_utc),
            ],
        });
        assert_eq!(history.daily_completed_focus_count(after_utc), 1);
        assert_eq!(history.daily_completed_focus_count(before_utc), 0);
    }

    #[test]
    fn ignores_only_an_incomplete_final_history_line() {
        let root = directory("truncated-history");
        let persistence = Persistence::new(root.join("config"), root.join("data"));
        persistence
            .append_history(&SessionHistoryBatch {
                batch_id: "batch-1".into(),
                events: vec![started("focus-1", SessionPhase::Focus, 0)],
            })
            .unwrap();
        let mut file = OpenOptions::new()
            .append(true)
            .open(&persistence.history_path)
            .unwrap();
        file.write_all(b"{\"schemaVersion\":1").unwrap();
        let history = persistence.load_history().unwrap();
        assert_eq!(history.events.len(), 1);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_future_history_schema() {
        let root = directory("future-history");
        let persistence = Persistence::new(root.join("config"), root.join("data"));
        fs::create_dir_all(persistence.history_path.parent().unwrap()).unwrap();
        fs::write(
            &persistence.history_path,
            r#"{"schemaVersion":2,"batchId":"batch-1","events":[]}
"#,
        )
        .unwrap();
        assert!(matches!(
            persistence.load_history(),
            Err(PersistenceError::UnsupportedSchema(2))
        ));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_mid_file_history_corruption() {
        let root = directory("corrupt-history");
        let persistence = Persistence::new(root.join("config"), root.join("data"));
        fs::create_dir_all(persistence.history_path.parent().unwrap()).unwrap();
        fs::write(&persistence.history_path, b"not-json\n{}\n").unwrap();
        assert!(matches!(
            persistence.load_history(),
            Err(PersistenceError::CorruptHistory { line: 1 })
        ));
        fs::remove_dir_all(root).unwrap();
    }
}
