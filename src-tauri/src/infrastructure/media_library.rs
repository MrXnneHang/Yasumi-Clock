use std::{
    collections::{BTreeMap, HashSet},
    fs,
    io::{self, Read, Write},
    path::{Path, PathBuf},
};

use atomic_write_file::AtomicWriteFile;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::domain::MediaRef;

const INDEX_SCHEMA_VERSION: u32 = 1;
const MAX_MEDIA_BYTES: u64 = 100 * 1024 * 1024;

#[derive(Debug)]
pub enum MediaLibraryError {
    InvalidFormat,
    InvalidMedia,
    MediaTooLarge,
    Io(io::Error),
    Json(serde_json::Error),
}

impl std::fmt::Display for MediaLibraryError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidFormat => write!(formatter, "only MP4 video files are supported"),
            Self::InvalidMedia => write!(formatter, "media file is invalid"),
            Self::MediaTooLarge => write!(formatter, "media file exceeds the maximum size"),
            Self::Io(error) => write!(formatter, "media library I/O failed: {error}"),
            Self::Json(error) => write!(formatter, "media library index is invalid: {error}"),
        }
    }
}

impl std::error::Error for MediaLibraryError {}

impl From<io::Error> for MediaLibraryError {
    fn from(error: io::Error) -> Self {
        Self::Io(error)
    }
}

impl From<serde_json::Error> for MediaLibraryError {
    fn from(error: serde_json::Error) -> Self {
        Self::Json(error)
    }
}

#[derive(Clone, Debug)]
pub struct MediaLibrary {
    index_path: PathBuf,
    root: PathBuf,
}

#[derive(Debug, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct MediaIndex {
    schema_version: u32,
    entries: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MediaLibraryChange {
    pub imported: Vec<MediaRef>,
    pub unavailable_ids: Vec<String>,
}

impl MediaLibrary {
    pub fn new(data_directory: PathBuf) -> Self {
        Self {
            index_path: data_directory.join("media-library.v1.json"),
            root: data_directory.join("media"),
        }
    }

    pub fn directory(&self) -> &Path {
        &self.root
    }

    pub fn ensure_directory(&self) -> Result<(), MediaLibraryError> {
        fs::create_dir_all(&self.root)?;
        Ok(())
    }

    pub fn import(&self, source: &Path) -> Result<MediaRef, MediaLibraryError> {
        if fs::metadata(source)?.len() > MAX_MEDIA_BYTES {
            return Err(MediaLibraryError::MediaTooLarge);
        }
        detect_mp4(source)?;

        self.ensure_directory()?;
        self.remove_incomplete_imports()?;
        let id = Uuid::new_v4().to_string();
        let filename = format!("{id}.mp4");
        let destination = self.root.join(&filename);
        let temporary = self.root.join(format!(".{id}.importing"));
        if let Err(error) = copy_file(source, &temporary) {
            let _ = fs::remove_file(&temporary);
            return Err(error);
        }
        if let Err(error) = fs::rename(&temporary, &destination) {
            let _ = fs::remove_file(&temporary);
            return Err(error.into());
        }

        let mut index = self.load_index()?;
        index.entries.insert(id.clone(), filename);
        self.save_index(&index)?;
        Ok(MediaRef::Imported { id })
    }

    pub fn contains(&self, media: &MediaRef) -> bool {
        match media {
            MediaRef::Builtin { .. } => true,
            MediaRef::Imported { id } => self.path(id).is_some(),
        }
    }

    pub fn path(&self, id: &str) -> Option<PathBuf> {
        if !valid_id(id) {
            return None;
        }
        let index = self.load_index().ok()?;
        let filename = index.entries.get(id)?;
        self.safe_path(filename).filter(|path| path.is_file())
    }

    pub fn imported_media(&self) -> Result<Vec<MediaRef>, MediaLibraryError> {
        let index = self.load_index()?;
        Ok(index
            .entries
            .iter()
            .filter_map(|(id, filename)| {
                self.safe_path(filename)
                    .filter(|path| path.is_file())
                    .map(|_| MediaRef::Imported { id: id.clone() })
            })
            .collect())
    }

    pub fn reconcile(&self) -> Result<MediaLibraryChange, MediaLibraryError> {
        let mut index = self.load_index()?;
        let actual = self.media_filenames()?;
        let indexed: HashSet<_> = index.entries.values().cloned().collect();
        let missing: Vec<_> = index
            .entries
            .iter()
            .filter_map(|(id, filename)| (!actual.contains(filename)).then(|| id.clone()))
            .collect();
        let added: Vec<_> = actual.difference(&indexed).cloned().collect();
        let mut unavailable_ids = Vec::new();

        if missing.len() == 1 && added.len() == 1 {
            index.entries.insert(missing[0].clone(), added[0].clone());
        } else {
            for id in missing {
                index.entries.remove(&id);
                unavailable_ids.push(id);
            }
        }
        if !unavailable_ids.is_empty()
            || (added.len() == 1 && index.entries.values().any(|name| name == &added[0]))
        {
            self.save_index(&index)?;
        }

        let imported = index
            .entries
            .keys()
            .cloned()
            .map(|id| MediaRef::Imported { id })
            .collect();
        Ok(MediaLibraryChange {
            imported,
            unavailable_ids,
        })
    }

    fn load_index(&self) -> Result<MediaIndex, MediaLibraryError> {
        match fs::read_to_string(&self.index_path) {
            Ok(contents) => {
                let index: MediaIndex = serde_json::from_str(&contents)?;
                if index.schema_version != INDEX_SCHEMA_VERSION {
                    return Err(MediaLibraryError::InvalidMedia);
                }
                Ok(index)
            }
            Err(error) if error.kind() == io::ErrorKind::NotFound => self.migrate_legacy_index(),
            Err(error) => Err(error.into()),
        }
    }

    fn migrate_legacy_index(&self) -> Result<MediaIndex, MediaLibraryError> {
        let mut entries = BTreeMap::new();
        if let Ok(paths) = fs::read_dir(&self.root) {
            for path in paths.flatten().map(|entry| entry.path()) {
                let Some(filename) = path.file_name().and_then(|name| name.to_str()) else {
                    continue;
                };
                let Some(id) = path.file_stem().and_then(|stem| stem.to_str()) else {
                    continue;
                };
                if is_media_filename(filename) && valid_id(id) {
                    entries.insert(id.to_owned(), filename.to_owned());
                }
            }
        }
        let index = MediaIndex {
            schema_version: INDEX_SCHEMA_VERSION,
            entries,
        };
        self.save_index(&index)?;
        Ok(index)
    }

    fn save_index(&self, index: &MediaIndex) -> Result<(), MediaLibraryError> {
        let parent = self.index_path.parent().expect("media index has parent");
        fs::create_dir_all(parent)?;
        let contents = serde_json::to_vec_pretty(index)?;
        let mut file = AtomicWriteFile::options().open(&self.index_path)?;
        file.write_all(&contents)?;
        file.write_all(b"\n")?;
        file.sync_all()?;
        file.commit()?;
        Ok(())
    }

    fn media_filenames(&self) -> Result<HashSet<String>, MediaLibraryError> {
        let entries = match fs::read_dir(&self.root) {
            Ok(entries) => entries,
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(HashSet::new()),
            Err(error) => return Err(error.into()),
        };
        Ok(entries
            .flatten()
            .filter_map(|entry| entry.file_name().into_string().ok())
            .filter(|filename| is_media_filename(filename))
            .collect())
    }

    fn safe_path(&self, filename: &str) -> Option<PathBuf> {
        is_media_filename(filename).then(|| self.root.join(filename))
    }

    fn remove_incomplete_imports(&self) -> Result<(), MediaLibraryError> {
        for entry in fs::read_dir(&self.root)? {
            let path = entry?.path();
            if path
                .extension()
                .is_some_and(|extension| extension == "importing")
            {
                fs::remove_file(path)?;
            }
        }
        Ok(())
    }
}

fn is_media_filename(filename: &str) -> bool {
    Path::new(filename)
        .file_name()
        .and_then(|name| name.to_str())
        == Some(filename)
        && Path::new(filename)
            .extension()
            .is_some_and(|extension| extension.eq_ignore_ascii_case("mp4"))
}

fn copy_file(source: &Path, destination: &Path) -> Result<(), MediaLibraryError> {
    let mut input = fs::File::open(source)?;
    let mut output = fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(destination)?;
    io::copy(&mut input, &mut output)?;
    output.sync_all()?;
    Ok(())
}

fn detect_mp4(source: &Path) -> Result<(), MediaLibraryError> {
    if !source
        .extension()
        .is_some_and(|extension| extension.eq_ignore_ascii_case("mp4"))
    {
        return Err(MediaLibraryError::InvalidFormat);
    }
    let mut header = [0; 12];
    let read = fs::File::open(source)?.read(&mut header)?;
    (read >= 8 && &header[4..8] == b"ftyp")
        .then_some(())
        .ok_or(MediaLibraryError::InvalidMedia)
}

fn valid_id(id: &str) -> bool {
    Uuid::parse_str(id).is_ok()
}

#[cfg(test)]
mod tests {
    use std::{
        fs,
        path::PathBuf,
        time::{SystemTime, UNIX_EPOCH},
    };

    use super::*;

    fn directory(name: &str) -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("yasumi-clock-media-{name}-{nonce}"))
    }

    fn write_media(path: &Path, contents: &[u8]) {
        fs::write(path, contents).unwrap();
    }

    #[test]
    fn migrates_existing_uuid_filenames_when_the_index_is_absent() {
        let root = directory("migration");
        let id = "59db2ea1-7f57-4e5d-8704-99d00688ff11";
        let path = root.join("data").join("media").join(format!("{id}.mp4"));
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        write_media(&path, b"\0\0\0\x18ftypisom media");
        let library = MediaLibrary::new(root.join("data"));

        assert_eq!(
            library.imported_media().unwrap(),
            vec![MediaRef::Imported { id: id.into() }]
        );
        assert!(root.join("data").join("media-library.v1.json").is_file());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn serializes_library_changes_for_the_frontend_event_contract() {
        let actual = serde_json::to_value(MediaLibraryChange {
            imported: vec![MediaRef::Imported {
                id: "59db2ea1-7f57-4e5d-8704-99d00688ff11".into(),
            }],
            unavailable_ids: vec!["3edbfec1-0c3d-45d0-a26c-ecfc4292a8a4".into()],
        })
        .unwrap();

        assert_eq!(
            actual,
            serde_json::json!({
                "imported": [{
                    "kind": "imported",
                    "id": "59db2ea1-7f57-4e5d-8704-99d00688ff11",
                }],
                "unavailableIds": ["3edbfec1-0c3d-45d0-a26c-ecfc4292a8a4"],
            })
        );
    }

    #[test]
    fn imports_valid_mp4_to_a_managed_uuid_reference() {
        let root = directory("import");
        let source = root.join("source name.mp4");
        fs::create_dir_all(&root).unwrap();
        write_media(&source, b"\0\0\0\x18ftypisom media");
        let library = MediaLibrary::new(root.join("data"));

        let MediaRef::Imported { id } = library.import(&source).unwrap() else {
            panic!("import must return an imported reference");
        };

        let stored = library.path(&id).unwrap();
        assert_ne!(stored, source);
        assert_eq!(fs::read(stored).unwrap(), b"\0\0\0\x18ftypisom media");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn preserves_a_media_reference_when_one_managed_file_is_renamed() {
        let root = directory("rename");
        let source = root.join("animation.mp4");
        fs::create_dir_all(&root).unwrap();
        write_media(&source, b"\0\0\0\x18ftypisom media");
        let library = MediaLibrary::new(root.join("data"));
        let MediaRef::Imported { id } = library.import(&source).unwrap() else {
            panic!("import must return an imported reference");
        };
        let renamed = library.directory().join("my animation.mp4");
        fs::rename(library.path(&id).unwrap(), &renamed).unwrap();

        let change = library.reconcile().unwrap();

        assert!(change.unavailable_ids.is_empty());
        assert_eq!(library.path(&id), Some(renamed));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn removes_deleted_media_from_the_library() {
        let root = directory("delete");
        let source = root.join("animation.mp4");
        fs::create_dir_all(&root).unwrap();
        write_media(&source, b"\0\0\0\x18ftypisom media");
        let library = MediaLibrary::new(root.join("data"));
        let MediaRef::Imported { id } = library.import(&source).unwrap() else {
            panic!("import must return an imported reference");
        };
        fs::remove_file(library.path(&id).unwrap()).unwrap();

        let change = library.reconcile().unwrap();

        assert_eq!(change.unavailable_ids, vec![id.clone()]);
        assert!(library.path(&id).is_none());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_gif_unknown_extensions_and_invalid_mp4_headers() {
        let root = directory("invalid");
        fs::create_dir_all(&root).unwrap();
        let gif = root.join("animation.gif");
        let text = root.join("animation.txt");
        let invalid = root.join("animation.mp4");
        write_media(&gif, b"GIF89a media");
        write_media(&text, b"not video");
        write_media(&invalid, b"not an mp4");
        let library = MediaLibrary::new(root.join("data"));

        assert!(matches!(
            library.import(&gif),
            Err(MediaLibraryError::InvalidFormat)
        ));
        assert!(matches!(
            library.import(&text),
            Err(MediaLibraryError::InvalidFormat)
        ));
        assert!(matches!(
            library.import(&invalid),
            Err(MediaLibraryError::InvalidMedia)
        ));
        fs::remove_dir_all(root).unwrap();
    }
}
