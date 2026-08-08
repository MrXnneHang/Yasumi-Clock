use std::{
    fs,
    io::{Read, Seek, SeekFrom},
};

use tauri::http::{
    Method, Request, Response, StatusCode,
    header::{ACCEPT_RANGES, CONTENT_LENGTH, CONTENT_RANGE, CONTENT_TYPE, RANGE},
};

use crate::tauri_api::AppState;

const MAX_RANGE_BYTES: u64 = 100 * 1024 * 1024;

pub fn respond(state: &AppState, request: &Request<Vec<u8>>) -> Response<Vec<u8>> {
    if !matches!(request.method(), &Method::GET | &Method::HEAD) {
        return empty(StatusCode::METHOD_NOT_ALLOWED);
    }

    let Some(id) = media_id(request.uri().path()) else {
        return empty(StatusCode::NOT_FOUND);
    };
    let Some(path) = state.media_library.path(id) else {
        return empty(StatusCode::NOT_FOUND);
    };
    let Ok(metadata) = fs::metadata(&path) else {
        return empty(StatusCode::NOT_FOUND);
    };
    let length = metadata.len();
    let range = match requested_range(request, length) {
        Ok(range) => range,
        Err(()) => return range_not_satisfiable(length),
    };
    let (start, end, status) =
        range.unwrap_or_else(|| (0, length.saturating_sub(1), StatusCode::OK));
    let content_length = end.saturating_sub(start).saturating_add(1);
    let mut builder = Response::builder()
        .status(status)
        .header(CONTENT_TYPE, "video/mp4")
        .header(ACCEPT_RANGES, "bytes")
        .header(CONTENT_LENGTH, content_length);
    if status == StatusCode::PARTIAL_CONTENT {
        builder = builder.header(CONTENT_RANGE, format!("bytes {start}-{end}/{length}"));
    }
    if request.method() == Method::HEAD {
        return builder.body(Vec::new()).expect("valid response headers");
    }

    let Ok(body) = read_range(&path, start, content_length) else {
        return empty(StatusCode::NOT_FOUND);
    };
    builder.body(body).expect("valid response headers")
}

fn media_id(path: &str) -> Option<&str> {
    let id = path.strip_prefix('/')?;
    (!id.is_empty() && !id.contains('/')).then_some(id)
}

fn requested_range(
    request: &Request<Vec<u8>>,
    length: u64,
) -> Result<Option<(u64, u64, StatusCode)>, ()> {
    let Some(value) = request.headers().get(RANGE) else {
        return Ok(None);
    };
    let value = value.to_str().map_err(|_| ())?;
    let (start, end) = parse_range(value, length)?;
    Ok(Some((start, end, StatusCode::PARTIAL_CONTENT)))
}

fn parse_range(value: &str, length: u64) -> Result<(u64, u64), ()> {
    let bytes = value.strip_prefix("bytes=").ok_or(())?;
    if bytes.contains(',') || length == 0 {
        return Err(());
    }
    let (start, end) = bytes.split_once('-').ok_or(())?;
    let (start, end) = if start.is_empty() {
        let suffix = end.parse::<u64>().map_err(|_| ())?;
        if suffix == 0 {
            return Err(());
        }
        let size = suffix.min(length).min(MAX_RANGE_BYTES);
        (length - size, length - 1)
    } else {
        let start = start.parse::<u64>().map_err(|_| ())?;
        if start >= length {
            return Err(());
        }
        let end = if end.is_empty() {
            length - 1
        } else {
            end.parse::<u64>().map_err(|_| ())?.min(length - 1)
        };
        (start, end)
    };
    if end < start || end - start + 1 > MAX_RANGE_BYTES {
        return Err(());
    }
    Ok((start, end))
}

fn read_range(path: &std::path::Path, start: u64, length: u64) -> std::io::Result<Vec<u8>> {
    let capacity = usize::try_from(length).map_err(|_| std::io::Error::other("range too large"))?;
    let mut file = fs::File::open(path)?;
    file.seek(SeekFrom::Start(start))?;
    let mut contents = vec![0; capacity];
    file.read_exact(&mut contents)?;
    Ok(contents)
}

fn empty(status: StatusCode) -> Response<Vec<u8>> {
    Response::builder()
        .status(status)
        .body(Vec::new())
        .expect("valid empty response")
}

fn range_not_satisfiable(length: u64) -> Response<Vec<u8>> {
    Response::builder()
        .status(StatusCode::RANGE_NOT_SATISFIABLE)
        .header(CONTENT_RANGE, format!("bytes */{length}"))
        .body(Vec::new())
        .expect("valid range response")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::infrastructure::MediaLibrary;

    #[test]
    fn accepts_only_a_single_path_id() {
        assert_eq!(media_id("/id"), Some("id"));
        assert_eq!(media_id("/nested/id"), None);
        assert_eq!(media_id("/"), None);
        assert_eq!(media_id("id"), None);
    }

    #[test]
    fn parses_closed_open_and_suffix_ranges() {
        assert_eq!(parse_range("bytes=2-5", 10), Ok((2, 5)));
        assert_eq!(parse_range("bytes=2-", 10), Ok((2, 9)));
        assert_eq!(parse_range("bytes=-3", 10), Ok((7, 9)));
    }

    #[test]
    fn responds_with_a_ranged_mp4_body_from_the_managed_library() {
        let root =
            std::env::temp_dir().join(format!("yasumi-media-protocol-{}", uuid::Uuid::new_v4()));
        let library = MediaLibrary::new(root.join("data"));
        let source = root.join("source.mp4");
        fs::create_dir_all(&root).unwrap();
        fs::write(&source, b"\0\0\0\x18ftypisom media").unwrap();
        let crate::domain::MediaRef::Imported { id } = library.import(&source).unwrap() else {
            panic!("import must return an imported reference");
        };
        let request = Request::builder()
            .method(Method::GET)
            .uri(format!("/{}", id))
            .header(RANGE, "bytes=4-7")
            .body(Vec::new())
            .unwrap();
        let state = AppState::new(
            crate::application::FocusTimer::new(
                crate::domain::TimerState::new(crate::domain::AppSettings::default()).unwrap(),
                crate::infrastructure::SystemClock::new(),
            ),
            crate::infrastructure::HistoryIndex::default(),
            library,
            crate::infrastructure::Persistence::new(root.join("config"), root.join("data")),
        );

        let response = respond(&state, &request);

        assert_eq!(response.status(), StatusCode::PARTIAL_CONTENT);
        assert_eq!(response.headers()[CONTENT_TYPE], "video/mp4");
        assert_eq!(response.headers()[CONTENT_RANGE], "bytes 4-7/18");
        assert_eq!(response.body(), b"ftyp");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_invalid_and_multi_ranges() {
        assert!(parse_range("items=2-5", 10).is_err());
        assert!(parse_range("bytes=10-11", 10).is_err());
        assert!(parse_range("bytes=2-5,7-8", 10).is_err());
        assert!(parse_range("bytes=-0", 10).is_err());
    }
}
