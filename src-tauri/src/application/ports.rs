use crate::domain::TimeSample;

pub trait Clock: Send + Sync + 'static {
    fn sample(&self) -> TimeSample;
}
