use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Default, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TimerProgress {
    pub daily_completed_focus_count: u32,
}

impl TimerProgress {
    pub fn record_completed_focus(&mut self) {
        self.daily_completed_focus_count = self.daily_completed_focus_count.saturating_add(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn completed_focus_updates_daily_history_without_cycle_state() {
        let mut progress = TimerProgress {
            daily_completed_focus_count: 8,
        };

        progress.record_completed_focus();
        assert_eq!(progress.daily_completed_focus_count, 9);
    }
}
