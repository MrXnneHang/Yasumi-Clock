use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use crate::{application::Clock, domain::TimeSample};

pub struct SystemClock {
    monotonic_origin: Instant,
}

impl SystemClock {
    pub fn new() -> Self {
        Self {
            monotonic_origin: Instant::now(),
        }
    }
}

impl Default for SystemClock {
    fn default() -> Self {
        Self::new()
    }
}

impl Clock for SystemClock {
    fn sample(&self) -> TimeSample {
        TimeSample::new(
            self.monotonic_origin.elapsed().as_secs(),
            unix_seconds(SystemTime::now()),
        )
    }
}

fn unix_seconds(time: SystemTime) -> i64 {
    match time.duration_since(UNIX_EPOCH) {
        Ok(duration) => saturating_i64(duration),
        Err(error) => -saturating_i64(error.duration()),
    }
}

fn saturating_i64(duration: Duration) -> i64 {
    i64::try_from(duration.as_secs()).unwrap_or(i64::MAX)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn converts_system_times_on_both_sides_of_the_unix_epoch() {
        assert_eq!(unix_seconds(UNIX_EPOCH + Duration::from_secs(12)), 12);
        assert_eq!(unix_seconds(UNIX_EPOCH - Duration::from_secs(7)), -7);
    }
}
