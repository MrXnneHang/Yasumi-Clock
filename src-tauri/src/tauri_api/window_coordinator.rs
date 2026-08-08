use std::fmt;

use tauri::{AppHandle, Manager};

use crate::application::AppEffect;

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub enum AuxiliaryWindow {
    RestOverlay,
    LastMinuteOverlay,
}

impl AuxiliaryWindow {
    fn label(self) -> &'static str {
        match self {
            Self::RestOverlay => "rest-overlay",
            Self::LastMinuteOverlay => "last-minute-overlay",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WindowLifecycle {
    Applied,
    AwaitingRegistration(AuxiliaryWindow),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum WindowAction {
    ShowOrFocus(AuxiliaryWindow),
    Hide(AuxiliaryWindow),
}

#[derive(Debug, Eq, PartialEq)]
pub struct WindowCoordinatorError {
    message: String,
}

impl WindowCoordinatorError {
    fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

impl fmt::Display for WindowCoordinatorError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.message.fmt(formatter)
    }
}

impl std::error::Error for WindowCoordinatorError {}

trait WindowPort {
    fn is_registered(&self, window: AuxiliaryWindow) -> bool;
    fn show(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError>;
    fn focus(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError>;
    fn hide(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError>;
}

struct WindowCoordinator<P> {
    port: P,
}

impl<P: WindowPort> WindowCoordinator<P> {
    fn new(port: P) -> Self {
        Self { port }
    }

    fn apply(&self, action: WindowAction) -> Result<WindowLifecycle, WindowCoordinatorError> {
        let window = match action {
            WindowAction::ShowOrFocus(window) | WindowAction::Hide(window) => window,
        };
        if !self.port.is_registered(window) {
            return Ok(match action {
                WindowAction::ShowOrFocus(_) => WindowLifecycle::AwaitingRegistration(window),
                WindowAction::Hide(_) => WindowLifecycle::Applied,
            });
        }

        match action {
            WindowAction::ShowOrFocus(window) => {
                self.port.show(window)?;
                self.port.focus(window)?;
            }
            WindowAction::Hide(window) => self.port.hide(window)?,
        }
        Ok(WindowLifecycle::Applied)
    }
}

struct TauriWindowPort<'app> {
    app: &'app AppHandle,
}

impl WindowPort for TauriWindowPort<'_> {
    fn is_registered(&self, window: AuxiliaryWindow) -> bool {
        self.app.get_webview_window(window.label()).is_some()
    }

    fn show(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
        self.app
            .get_webview_window(window.label())
            .expect("registered window is available")
            .show()
            .map_err(|error| WindowCoordinatorError::new(error.to_string()))
    }

    fn focus(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
        self.app
            .get_webview_window(window.label())
            .expect("registered window is available")
            .set_focus()
            .map_err(|error| WindowCoordinatorError::new(error.to_string()))
    }

    fn hide(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
        self.app
            .get_webview_window(window.label())
            .expect("registered window is available")
            .hide()
            .map_err(|error| WindowCoordinatorError::new(error.to_string()))
    }
}

pub fn apply_window_effect(
    app: &AppHandle,
    effect: &AppEffect,
) -> Result<WindowLifecycle, WindowCoordinatorError> {
    WindowCoordinator::new(TauriWindowPort { app }).apply(action_for(effect))
}

fn action_for(effect: &AppEffect) -> WindowAction {
    match effect {
        AppEffect::ShowRestOverlay => WindowAction::ShowOrFocus(AuxiliaryWindow::RestOverlay),
        AppEffect::HideRestOverlay => WindowAction::Hide(AuxiliaryWindow::RestOverlay),
        AppEffect::ShowLastMinuteOverlay => {
            WindowAction::ShowOrFocus(AuxiliaryWindow::LastMinuteOverlay)
        }
        AppEffect::HideLastMinuteOverlay => WindowAction::Hide(AuxiliaryWindow::LastMinuteOverlay),
        _ => unreachable!("only window effects are dispatched to the window coordinator"),
    }
}

#[cfg(test)]
mod tests {
    use std::{cell::RefCell, collections::HashSet};

    use super::*;

    #[derive(Default)]
    struct RecordingPort {
        registered: HashSet<AuxiliaryWindow>,
        operations: RefCell<Vec<WindowAction>>,
    }

    impl RecordingPort {
        fn with_registered(window: AuxiliaryWindow) -> Self {
            Self {
                registered: HashSet::from([window]),
                operations: RefCell::default(),
            }
        }
    }

    impl WindowPort for RecordingPort {
        fn is_registered(&self, window: AuxiliaryWindow) -> bool {
            self.registered.contains(&window)
        }

        fn show(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
            self.operations
                .borrow_mut()
                .push(WindowAction::ShowOrFocus(window));
            Ok(())
        }

        fn focus(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
            self.operations
                .borrow_mut()
                .push(WindowAction::ShowOrFocus(window));
            Ok(())
        }

        fn hide(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
            self.operations
                .borrow_mut()
                .push(WindowAction::Hide(window));
            Ok(())
        }
    }

    impl WindowPort for &RecordingPort {
        fn is_registered(&self, window: AuxiliaryWindow) -> bool {
            (*self).is_registered(window)
        }

        fn show(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
            (*self).show(window)
        }

        fn focus(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
            (*self).focus(window)
        }

        fn hide(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
            (*self).hide(window)
        }
    }

    #[test]
    fn show_effect_focuses_an_existing_singleton() {
        let port = RecordingPort::with_registered(AuxiliaryWindow::RestOverlay);
        let coordinator = WindowCoordinator::new(&port);

        assert_eq!(
            coordinator
                .apply(action_for(&AppEffect::ShowRestOverlay))
                .unwrap(),
            WindowLifecycle::Applied
        );
        assert_eq!(
            *port.operations.borrow(),
            [
                WindowAction::ShowOrFocus(AuxiliaryWindow::RestOverlay),
                WindowAction::ShowOrFocus(AuxiliaryWindow::RestOverlay),
            ]
        );
    }

    #[test]
    fn show_effect_waits_for_its_window_registration() {
        let coordinator = WindowCoordinator::new(RecordingPort::default());

        assert_eq!(
            coordinator
                .apply(action_for(&AppEffect::ShowRestOverlay))
                .unwrap(),
            WindowLifecycle::AwaitingRegistration(AuxiliaryWindow::RestOverlay)
        );
    }

    #[test]
    fn hide_effect_hides_an_existing_singleton() {
        let port = RecordingPort::with_registered(AuxiliaryWindow::RestOverlay);
        let coordinator = WindowCoordinator::new(&port);

        assert_eq!(
            coordinator
                .apply(action_for(&AppEffect::HideRestOverlay))
                .unwrap(),
            WindowLifecycle::Applied
        );
        assert_eq!(
            *port.operations.borrow(),
            [WindowAction::Hide(AuxiliaryWindow::RestOverlay)]
        );
    }

    #[test]
    fn hide_effect_is_safe_before_window_registration() {
        let coordinator = WindowCoordinator::new(RecordingPort::default());

        assert_eq!(
            coordinator
                .apply(action_for(&AppEffect::HideRestOverlay))
                .unwrap(),
            WindowLifecycle::Applied
        );
    }

    #[test]
    fn maps_each_overlay_effect_to_its_named_window_action() {
        assert_eq!(
            action_for(&AppEffect::ShowRestOverlay),
            WindowAction::ShowOrFocus(AuxiliaryWindow::RestOverlay)
        );
        assert_eq!(
            action_for(&AppEffect::HideRestOverlay),
            WindowAction::Hide(AuxiliaryWindow::RestOverlay)
        );
        assert_eq!(
            action_for(&AppEffect::ShowLastMinuteOverlay),
            WindowAction::ShowOrFocus(AuxiliaryWindow::LastMinuteOverlay)
        );
        assert_eq!(
            action_for(&AppEffect::HideLastMinuteOverlay),
            WindowAction::Hide(AuxiliaryWindow::LastMinuteOverlay)
        );
    }
}
