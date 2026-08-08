use std::{
    fs,
    io::{self, Read},
    path::{Path, PathBuf},
};

use uuid::Uuid;

use crate::domain::MediaRef;

const MAX_MEDIA_BYTES: u64 = 100 * 1024 * 1024;

#[derive(Debug)]
pub enum MediaLibraryError {
    InvalidFormat,
    InvalidMedia,
    MediaTooLarge,
    Io(io::Error),
}

impl std::fmt::Display for MediaLibraryError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidFormat => write!(formatter, "only MP4 video files are supported"),
            Self::InvalidMedia => write!(formatter, "media file is invalid"),
            Self::MediaTooLarge => write!(formatter, "media file exceeds the maximum size"),
            Self::Io(error) => write!(formatter, "media library I/O failed: {error}"),
        }
    }
}

impl std::error::Error for MediaLibraryError {}

impl From<io::Error> for MediaLibraryError {
    fn from(error: io::Error) -> Self {
        Self::Io(error)
    }
}

#[derive(Clone, Debug)]
pub struct MediaLibrary {
    root: PathBuf,
}

impl MediaLibrary {
    pub fn new(data_directory: PathBuf) -> Self {
        Self {
            root: data_directory.join("media"),
        }
    }

    pub fn import(&self, source: &Path) -> Result<MediaRef, MediaLibraryError> {
        if fs::metadata(source)?.len() > MAX_MEDIA_BYTES {
            return Err(MediaLibraryError::MediaTooLarge);
        }
        detect_mp4(source)?;

        fs::create_dir_all(&self.root)?;
        self.remove_incomplete_imports()?;
        let id = Uuid::new_v4().to_string();
        let destination = self.path_for(&id);
        let temporary = self.root.join(format!(".{id}.importing"));
        if let Err(error) = copy_file(source, &temporary) {
            let _ = fs::remove_file(&temporary);
            return Err(error);
        }
        if let Err(error) = fs::rename(&temporary, &destination) {
            let _ = fs::remove_file(&temporary);
            return Err(error.into());
        }

        Ok(MediaRef::Imported { id })
    }

    pub fn contains(&self, media: &MediaRef) -> bool {
        match media {
            MediaRef::Builtin { .. } => true,
            MediaRef::Imported { id } => valid_id(id) && self.path_for(id).is_file(),
        }
    }

    pub fn path(&self, id: &str) -> Option<PathBuf> {
        valid_id(id)
            .then(|| self.path_for(id))
            .filter(|path| path.is_file())
    }

    pub fn imported_media(&self) -> Result<Vec<MediaRef>, MediaLibraryError> {
        let entries = match fs::read_dir(&self.root) {
            Ok(entries) => entries,
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(Vec::new()),
            Err(error) => return Err(error.into()),
        };
        let mut media: Vec<_> = entries
            .filter_map(Result::ok)
            .filter_map(|entry| media_ref_from_path(&entry.path()))
            .collect();
        media.sort_by(|left, right| match (left, right) {
            (MediaRef::Imported { id: left }, MediaRef::Imported { id: right }) => left.cmp(right),
            _ => std::cmp::Ordering::Equal,
        });
        Ok(media)
    }

    fn path_for(&self, id: &str) -> PathBuf {
        self.root.join(format!("{id}.mp4"))
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

fn media_ref_from_path(path: &Path) -> Option<MediaRef> {
    let id = path.file_stem()?.to_str()?;
    (path.extension()?.eq_ignore_ascii_case("mp4") && valid_id(id))
        .then(|| MediaRef::Imported { id: id.to_owned() })
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
    fn imports_valid_mp4_to_a_uuid_filename_without_source_path() {
        let root = directory("import");
        let source = root.join("source name.mp4");
        fs::create_dir_all(&root).unwrap();
        write_media(&source, b"\0\0\0\x18ftypisom media");
        let library = MediaLibrary::new(root.join("data"));

        let media = library.import(&source).unwrap();

        let MediaRef::Imported { id } = media else {
            panic!("import must return an imported reference");
        };
        assert!(Uuid::parse_str(&id).is_ok());
        let stored = library.path(&id).unwrap();
        assert_eq!(
            stored.file_name().unwrap().to_string_lossy(),
            format!("{id}.mp4")
        );
        assert_ne!(stored, source);
        assert_eq!(fs::read(stored).unwrap(), b"\0\0\0\x18ftypisom media");
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

    #[test]
    fn one_import_is_available_for_every_animation_role() {
        let root = directory("shared");
        let source = root.join("animation.mp4");
        fs::create_dir_all(&root).unwrap();
        write_media(&source, b"\0\0\0\x18ftypisom media");
        let library = MediaLibrary::new(root.join("data"));
        let imported = library.import(&source).unwrap();

        assert!(library.contains(&imported));
        assert_eq!(library.imported_media().unwrap(), vec![imported]);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn resolves_media_only_by_valid_opaque_identifier() {
        let root = directory("find");
        let source = root.join("animation.mp4");
        fs::create_dir_all(&root).unwrap();
        write_media(&source, b"\0\0\0\x18ftypisom media");
        let library = MediaLibrary::new(root.join("data"));
        let MediaRef::Imported { id } = library.import(&source).unwrap() else {
            panic!("import must return an imported reference");
        };

        assert!(library.path(&id).is_some());
        assert!(library.path("../animation").is_none());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn removes_incomplete_imports_before_copying_new_media() {
        let root = directory("stale-temp");
        let source = root.join("animation.mp4");
        fs::create_dir_all(&root).unwrap();
        write_media(&source, b"\0\0\0\x18ftypisom media");
        let library = MediaLibrary::new(root.join("data"));
        fs::create_dir_all(&library.root).unwrap();
        write_media(&library.root.join("stale.importing"), b"partial");

        library.import(&source).unwrap();

        assert!(!library.root.join("stale.importing").exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_unknown_identifiers_when_resolving_media() {
        let root = directory("unknown-id");
        let library = MediaLibrary::new(root.join("data"));

        assert!(!library.contains(&MediaRef::Imported {
            id: "../../source".into(),
        }));
        fs::remove_dir_all(root).unwrap_or_default();
    }
}
