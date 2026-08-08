use tokio::sync::Mutex;

use crate::{
    application::FocusTimer,
    infrastructure::{HistoryIndex, Persistence, SystemClock},
};

pub type RuntimeTimer = FocusTimer<SystemClock>;

pub struct AppState {
    pub timer: Mutex<RuntimeTimer>,
    pub history: Mutex<HistoryIndex>,
    pub persistence: Persistence,
}

impl AppState {
    pub fn new(timer: RuntimeTimer, history: HistoryIndex, persistence: Persistence) -> Self {
        Self {
            timer: Mutex::new(timer),
            history: Mutex::new(history),
            persistence,
        }
    }
}
