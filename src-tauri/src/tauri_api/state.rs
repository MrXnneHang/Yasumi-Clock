use tokio::sync::Mutex;

use crate::{
    application::FocusTimer,
    infrastructure::{HistoryIndex, MediaLibrary, Persistence, SystemClock},
};

pub type RuntimeTimer = FocusTimer<SystemClock>;

pub struct AppState {
    pub timer: Mutex<RuntimeTimer>,
    pub history: Mutex<HistoryIndex>,
    pub media_library: MediaLibrary,
    pub persistence: Persistence,
}

impl AppState {
    pub fn new(
        timer: RuntimeTimer,
        history: HistoryIndex,
        media_library: MediaLibrary,
        persistence: Persistence,
    ) -> Self {
        Self {
            timer: Mutex::new(timer),
            history: Mutex::new(history),
            media_library,
            persistence,
        }
    }
}
