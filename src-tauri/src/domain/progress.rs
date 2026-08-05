use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Default, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TimerProgress {
    pub cycle_focus_count: u32,
    pub daily_completed_focus_count: u32,
}

impl TimerProgress {
    pub fn complete_focus(&mut self, cycle_target: u32) -> bool {
        self.daily_completed_focus_count = self.daily_completed_focus_count.saturating_add(1);
        self.cycle_focus_count = self.cycle_focus_count.saturating_add(1);

        if self.cycle_focus_count >= cycle_target {
            self.cycle_focus_count = 0;
            true
        } else {
            false
        }
    }

    pub fn reset_cycle(&mut self) {
        self.cycle_focus_count = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn long_break_resets_cycle_without_erasing_daily_progress() {
        let mut progress = TimerProgress {
            cycle_focus_count: 3,
            daily_completed_focus_count: 8,
        };

        assert!(progress.complete_focus(4));
        assert_eq!(progress.cycle_focus_count, 0);
        assert_eq!(progress.daily_completed_focus_count, 9);

        progress.reset_cycle();
        assert_eq!(progress.daily_completed_focus_count, 9);
    }
}
