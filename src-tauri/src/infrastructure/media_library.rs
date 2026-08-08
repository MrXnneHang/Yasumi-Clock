use std::{
    fs,
    io::{self, Read},
    path::{Path, PathBuf},
};

use uuid::Uuid;

use crate::domain::{MediaFormat, MediaRef};

#[derive(Clone, Copy, Debug, Eq, PartialEq, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum AnimationSlot {
    Idle,
    Focus,
    Rest,
}

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
            Self::InvalidFormat => write!(
                formatter,
                "media format is not allowed for this animation slot"
            ),
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

    pub fn import(
        &self,
        source: &Path,
        slot: AnimationSlot,
    ) -> Result<MediaRef, MediaLibraryError> {
        if fs::metadata(source)?.len() > MAX_MEDIA_BYTES {
            return Err(MediaLibraryError::MediaTooLarge);
        }
        let format = detect_format(source)?;
        if !slot_accepts_format(slot, format) {
            return Err(MediaLibraryError::InvalidFormat);
        }

        fs::create_dir_all(&self.root)?;
        self.remove_incomplete_imports()?;
        let id = Uuid::new_v4().to_string();
        let destination = self.path_for(&id, format);
        let temporary = self.root.join(format!(".{id}.importing"));
        if let Err(error) = copy_file(source, &temporary) {
            let _ = fs::remove_file(&temporary);
            return Err(error);
        }
        if let Err(error) = fs::rename(&temporary, &destination) {
            let _ = fs::remove_file(&temporary);
            return Err(error.into());
        }

        Ok(MediaRef::Imported { id, format })
    }

    pub fn contains(&self, media: &MediaRef) -> bool {
        match media {
            MediaRef::Builtin { .. } => true,
            MediaRef::Imported { id, format } => {
                valid_id(id) && self.path_for(id, *format).is_file()
            }
        }
    }

    pub fn path(&self, id: &str, format: MediaFormat) -> Option<PathBuf> {
        valid_id(id)
            .then(|| self.path_for(id, format))
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
            (MediaRef::Imported { id: left, .. }, MediaRef::Imported { id: right, .. }) => {
                left.cmp(right)
            }
            _ => std::cmp::Ordering::Equal,
        });
        Ok(media)
    }

    fn path_for(&self, id: &str, format: MediaFormat) -> PathBuf {
        self.root.join(format!("{id}.{}", extension(format)))
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
    let format = match path.extension()?.to_str()? {
        "mp4" => MediaFormat::Mp4,
        "gif" => MediaFormat::Gif,
        _ => return None,
    };
    valid_id(id).then(|| MediaRef::Imported {
        id: id.to_owned(),
        format,
    })
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

fn detect_format(source: &Path) -> Result<MediaFormat, MediaLibraryError> {
    let extension = source
        .extension()
        .and_then(|extension| extension.to_str())
        .map(str::to_ascii_lowercase);
    let mut header = [0; 12];
    let read = fs::File::open(source)?.read(&mut header)?;

    match extension.as_deref() {
        Some("gif")
            if header[..read].starts_with(b"GIF87a") || header[..read].starts_with(b"GIF89a") =>
        {
            Ok(MediaFormat::Gif)
        }
        Some("mp4") if read >= 8 && &header[4..8] == b"ftyp" => Ok(MediaFormat::Mp4),
        Some("gif") | Some("mp4") => Err(MediaLibraryError::InvalidMedia),
        _ => Err(MediaLibraryError::InvalidFormat),
    }
}

fn slot_accepts_format(slot: AnimationSlot, format: MediaFormat) -> bool {
    matches!(
        (slot, format),
        (AnimationSlot::Idle | AnimationSlot::Focus, MediaFormat::Mp4)
            | (AnimationSlot::Rest, MediaFormat::Mp4 | MediaFormat::Gif)
    )
}

fn extension(format: MediaFormat) -> &'static str {
    match format {
        MediaFormat::Mp4 => "mp4",
        MediaFormat::Gif => "gif",
    }
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
    fn imports_valid_media_to_a_uuid_filename_without_source_path() {
        let root = directory("import");
        let source = root.join("source name.mp4");
        fs::create_dir_all(&root).unwrap();
        write_media(&source, b"\0\0\0\x18ftypisom media");
        let library = MediaLibrary::new(root.join("data"));

        let media = library.import(&source, AnimationSlot::Focus).unwrap();

        let MediaRef::Imported { id, format } = media else {
            panic!("import must return an imported reference");
        };
        assert_eq!(format, MediaFormat::Mp4);
        assert!(Uuid::parse_str(&id).is_ok());
        let stored = library.path(&id, format).unwrap();
        assert_eq!(
            stored.file_name().unwrap().to_string_lossy(),
            format!("{id}.mp4")
        );
        assert_ne!(stored, source);
        assert_eq!(fs::read(stored).unwrap(), b"\0\0\0\x18ftypisom media");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn accepts_gif_only_for_the_rest_slot() {
        let root = directory("gif");
        let source = root.join("animation.gif");
        fs::create_dir_all(&root).unwrap();
        write_media(&source, b"GIF89a media");
        let library = MediaLibrary::new(root.join("data"));

        assert!(matches!(
            library.import(&source, AnimationSlot::Idle),
            Err(MediaLibraryError::InvalidFormat)
        ));
        assert!(matches!(
            library.import(&source, AnimationSlot::Rest),
            Ok(MediaRef::Imported {
                format: MediaFormat::Gif,
                ..
            })
        ));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_invalid_headers_and_unknown_identifiers() {
        let root = directory("invalid");
        let source = root.join("animation.mp4");
        fs::create_dir_all(&root).unwrap();
        write_media(&source, b"not an mp4");
        let library = MediaLibrary::new(root.join("data"));

        assert!(matches!(
            library.import(&source, AnimationSlot::Focus),
            Err(MediaLibraryError::InvalidMedia)
        ));
        assert!(!library.contains(&MediaRef::Imported {
            id: "../../source".into(),
            format: MediaFormat::Mp4,
        }));
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

        library.import(&source, AnimationSlot::Focus).unwrap();

        assert!(!library.root.join("stale.importing").exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn lists_only_valid_opaque_media_entries() {
        let root = directory("list");
        let library = MediaLibrary::new(root.join("data"));
        fs::create_dir_all(&library.root).unwrap();
        let id = Uuid::new_v4().to_string();
        write_media(&library.root.join(format!("{id}.gif")), b"GIF89a media");
        write_media(&library.root.join("not-media.txt"), b"ignore");

        assert_eq!(
            library.imported_media().unwrap(),
            vec![MediaRef::Imported {
                id,
                format: MediaFormat::Gif,
            }]
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn leaves_no_temporary_files_after_an_import() {
        let root = directory("cleanup");
        let source = root.join("animation.mp4");
        fs::create_dir_all(&root).unwrap();
        write_media(&source, b"\0\0\0\x18ftypisom media");
        let library = MediaLibrary::new(root.join("data"));

        library.import(&source, AnimationSlot::Focus).unwrap();

        assert!(fs::read_dir(library.root).unwrap().all(|entry| {
            !entry
                .unwrap()
                .file_name()
                .to_string_lossy()
                .ends_with(".importing")
        }));
        fs::remove_dir_all(root).unwrap();
    }
}
