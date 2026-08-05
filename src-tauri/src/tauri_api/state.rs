use tokio::sync::Mutex;

use crate::{application::FocusTimer, infrastructure::SystemClock};

pub type RuntimeTimer = FocusTimer<SystemClock>;

pub struct AppState {
    pub timer: Mutex<RuntimeTimer>,
}

impl AppState {
    pub fn new(timer: RuntimeTimer) -> Self {
        Self {
            timer: Mutex::new(timer),
        }
    }
}
