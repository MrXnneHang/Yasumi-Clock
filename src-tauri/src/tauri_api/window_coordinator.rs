use std::fmt;

use tauri::{
    App, AppHandle, Manager, PhysicalPosition, PhysicalSize, WebviewWindow, WebviewWindowBuilder,
    WindowEvent,
};

use crate::application::AppEffect;

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub enum AuxiliaryWindow {
    RestOverlay,
    Settings,
    LastMinuteOverlay,
}

impl AuxiliaryWindow {
    fn label(self) -> &'static str {
        match self {
            Self::RestOverlay => "rest-overlay",
            Self::Settings => "settings",
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
    fn create(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError>;
    fn show(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError>;
    fn focus(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError>;
    fn hide(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError>;
    fn destroy(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError>;
}

struct WindowCoordinator<P> {
    port: P,
}

impl<P: WindowPort> WindowCoordinator<P> {
    fn new(port: P) -> Self {
        Self { port }
    }

    fn destroy_auxiliary(&self) -> Result<(), WindowCoordinatorError> {
        for window in [
            AuxiliaryWindow::Settings,
            AuxiliaryWindow::RestOverlay,
            AuxiliaryWindow::LastMinuteOverlay,
        ] {
            if self.port.is_registered(window) {
                self.port.destroy(window)?;
            }
        }
        Ok(())
    }

    fn apply(&self, action: WindowAction) -> Result<WindowLifecycle, WindowCoordinatorError> {
        let window = match action {
            WindowAction::ShowOrFocus(window) | WindowAction::Hide(window) => window,
        };
        if !self.port.is_registered(window) {
            return Ok(match action {
                WindowAction::ShowOrFocus(AuxiliaryWindow::Settings) => {
                    self.port.create(AuxiliaryWindow::Settings)?;
                    self.port.show(AuxiliaryWindow::Settings)?;
                    self.port.focus(AuxiliaryWindow::Settings)?;
                    WindowLifecycle::Applied
                }
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

    fn create(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
        create_window_from_config(self.app, window)
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

    fn destroy(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
        self.app
            .get_webview_window(window.label())
            .expect("registered window is available")
            .destroy()
            .map_err(|error| WindowCoordinatorError::new(error.to_string()))
    }
}

pub fn create_rest_overlay(app: &App) -> Result<(), WindowCoordinatorError> {
    create_window_from_config(app.handle(), AuxiliaryWindow::RestOverlay)?;
    let rest_overlay = app
        .get_webview_window(AuxiliaryWindow::RestOverlay.label())
        .expect("rest-overlay window is registered");
    position_rest_overlay(app, &rest_overlay)?;
    register_rest_overlay_close_handler(app.handle().clone(), &rest_overlay);
    Ok(())
}

fn create_window_from_config(
    app: &AppHandle,
    window: AuxiliaryWindow,
) -> Result<(), WindowCoordinatorError> {
    let config = app
        .config()
        .app
        .windows
        .iter()
        .find(|config| config.label == window.label())
        .expect("auxiliary window configuration is required");
    WebviewWindowBuilder::from_config(app, config)
        .map_err(|error| WindowCoordinatorError::new(error.to_string()))?
        .build()
        .map_err(|error| WindowCoordinatorError::new(error.to_string()))?;
    Ok(())
}

fn position_rest_overlay(
    app: &App,
    rest_overlay: &WebviewWindow,
) -> Result<(), WindowCoordinatorError> {
    let main = app
        .get_webview_window("main")
        .expect("main window is registered");
    let monitor = match main
        .current_monitor()
        .map_err(|error| WindowCoordinatorError::new(error.to_string()))?
    {
        Some(monitor) => monitor,
        None => app
            .primary_monitor()
            .map_err(|error| WindowCoordinatorError::new(error.to_string()))?
            .ok_or_else(|| {
                WindowCoordinatorError::new("no monitor is available for rest overlay")
            })?,
    };
    let area = monitor.work_area();
    let (size, position) = overlay_bounds(area.position, area.size);
    rest_overlay
        .set_size(size)
        .map_err(|error| WindowCoordinatorError::new(error.to_string()))?;
    rest_overlay
        .set_position(position)
        .map_err(|error| WindowCoordinatorError::new(error.to_string()))?;
    Ok(())
}

fn overlay_bounds(
    area_position: PhysicalPosition<i32>,
    area_size: PhysicalSize<u32>,
) -> (PhysicalSize<u32>, PhysicalPosition<i32>) {
    let width = area_size.width.saturating_mul(5) / 6;
    let height = area_size.height.saturating_mul(5) / 6;
    let x = area_position
        .x
        .saturating_add(((area_size.width - width) / 2) as i32);
    let y = area_position
        .y
        .saturating_add(((area_size.height - height) / 2) as i32);
    (
        PhysicalSize::new(width, height),
        PhysicalPosition::new(x, y),
    )
}

fn register_rest_overlay_close_handler(app: AppHandle, rest_overlay: &WebviewWindow) {
    rest_overlay.on_window_event(move |event| {
        if let WindowEvent::CloseRequested { api, .. } = event {
            api.prevent_close();
            let app = app.clone();
            tauri::async_runtime::spawn(async move {
                if let Err(error) =
                    crate::tauri_api::commands::end_rest_from_overlay_close(&app).await
                {
                    eprintln!("failed to end rest from overlay close: {}", error.message);
                }
            });
        }
    });
}

pub fn register_main_close_handler(app: &AppHandle) -> Result<(), WindowCoordinatorError> {
    let main = app
        .get_webview_window("main")
        .expect("main window is registered");
    let app = app.clone();
    main.on_window_event(move |event| {
        if let WindowEvent::CloseRequested { api, .. } = event {
            api.prevent_close();
            crate::tauri_api::record_shutdown(&app);
            if let Err(error) = destroy_auxiliary_windows(&app) {
                eprintln!("failed to destroy auxiliary windows: {error}");
            }
            app.exit(0);
        }
    });
    Ok(())
}

pub fn destroy_auxiliary_windows(app: &AppHandle) -> Result<(), WindowCoordinatorError> {
    WindowCoordinator::new(TauriWindowPort { app }).destroy_auxiliary()
}

pub fn apply_window_effect(
    app: &AppHandle,
    effect: &AppEffect,
) -> Result<WindowLifecycle, WindowCoordinatorError> {
    WindowCoordinator::new(TauriWindowPort { app }).apply(action_for(effect))
}

pub fn show_settings_window(app: &AppHandle) -> Result<WindowLifecycle, WindowCoordinatorError> {
    WindowCoordinator::new(TauriWindowPort { app })
        .apply(WindowAction::ShowOrFocus(AuxiliaryWindow::Settings))
}

pub fn hide_rest_overlay(app: &AppHandle) -> Result<WindowLifecycle, WindowCoordinatorError> {
    WindowCoordinator::new(TauriWindowPort { app })
        .apply(WindowAction::Hide(AuxiliaryWindow::RestOverlay))
}

#[tauri::command]
pub async fn temporarily_hide_rest_overlay(
    app: AppHandle,
    window: WebviewWindow,
    state: tauri::State<'_, super::AppState>,
) -> Result<crate::domain::TimerSnapshot, super::CommandError> {
    if window.label() != "rest-overlay" {
        return Err(super::CommandError::action_not_allowed());
    }
    let timer = state.timer.lock().await;
    let session_id = running_rest_id(&timer).ok_or_else(super::CommandError::action_not_allowed)?;
    if !window
        .is_visible()
        .map_err(|error| super::CommandError::event_publish_failed(error.to_string()))?
    {
        return Err(super::CommandError::action_not_allowed());
    }
    hide_rest_overlay(&app)
        .map_err(|error| super::CommandError::event_publish_failed(error.to_string()))?;
    let snapshot = timer.snapshot();
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(std::time::Duration::from_secs(15)).await;
        let state = app.state::<super::AppState>();
        let timer = state.timer.lock().await;
        if !state
            .shutdown_recorded
            .load(std::sync::atomic::Ordering::Acquire)
            && running_rest_id(&timer).as_deref() == Some(session_id.as_str())
        {
            if let Err(error) = apply_window_effect(&app, &AppEffect::ShowRestOverlay) {
                eprintln!("failed to restore rest overlay: {error}");
            }
        }
    });
    Ok(snapshot)
}

fn running_rest_id<C: crate::application::Clock>(
    timer: &crate::application::FocusTimer<C>,
) -> Option<String> {
    let snapshot = timer.snapshot();
    if snapshot.status != crate::domain::TimerStatus::Running
        || snapshot.phase != Some(crate::domain::SessionPhase::Rest)
        || snapshot.remaining_seconds == 0
    {
        return None;
    }
    timer
        .checkpoint()
        .active_session
        .map(|session| session.session_id)
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

    #[test]
    fn restore_guard_only_accepts_the_same_unexpired_rest() {
        use crate::{
            application::{Clock, FocusTimer},
            domain::{AppSettings, TimeSample, TimerState},
        };
        use std::sync::{
            Arc,
            atomic::{AtomicU64, Ordering},
        };

        struct TestClock(Arc<AtomicU64>);
        impl Clock for TestClock {
            fn sample(&self) -> TimeSample {
                let seconds = self.0.load(Ordering::Relaxed);
                TimeSample::new(seconds, seconds as i64)
            }
        }
        let now = Arc::new(AtomicU64::new(0));
        let mut timer = FocusTimer::new(
            TimerState::new(AppSettings::defaults()).unwrap(),
            TestClock(now.clone()),
        );
        assert_eq!(running_rest_id(&timer), None);
        timer.start_focus(Some(0), None).unwrap();
        assert_eq!(running_rest_id(&timer), None);
        now.store(1, Ordering::Relaxed);
        timer.reconcile_time().unwrap();
        let first_rest = running_rest_id(&timer).unwrap();
        now.store(16, Ordering::Relaxed);
        assert_eq!(
            running_rest_id(&timer).as_deref(),
            Some(first_rest.as_str())
        );
        assert_eq!(timer.snapshot().remaining_seconds, 285);
        now.store(301, Ordering::Relaxed);
        assert_eq!(running_rest_id(&timer), None);
        timer.end().unwrap();
        assert_eq!(running_rest_id(&timer), None);
        timer.start_focus(Some(0), None).unwrap();
        now.store(302, Ordering::Relaxed);
        timer.reconcile_time().unwrap();
        assert_ne!(running_rest_id(&timer).unwrap(), first_rest);
    }

    #[derive(Default)]
    struct RecordingPort {
        registered: HashSet<AuxiliaryWindow>,
        created: RefCell<Vec<AuxiliaryWindow>>,
        destroyed: RefCell<Vec<AuxiliaryWindow>>,
        operations: RefCell<Vec<WindowAction>>,
    }

    impl RecordingPort {
        fn with_registered(window: AuxiliaryWindow) -> Self {
            Self {
                registered: HashSet::from([window]),
                created: RefCell::default(),
                destroyed: RefCell::default(),
                operations: RefCell::default(),
            }
        }
    }

    impl WindowPort for RecordingPort {
        fn is_registered(&self, window: AuxiliaryWindow) -> bool {
            self.registered.contains(&window)
        }

        fn create(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
            self.created.borrow_mut().push(window);
            Ok(())
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

        fn destroy(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
            self.destroyed.borrow_mut().push(window);
            Ok(())
        }
    }

    impl WindowPort for &RecordingPort {
        fn is_registered(&self, window: AuxiliaryWindow) -> bool {
            (*self).is_registered(window)
        }

        fn create(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
            (*self).create(window)
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

        fn destroy(&self, window: AuxiliaryWindow) -> Result<(), WindowCoordinatorError> {
            (*self).destroy(window)
        }
    }

    #[test]
    fn destroys_registered_auxiliary_windows() {
        let port = RecordingPort::with_registered(AuxiliaryWindow::Settings);
        let coordinator = WindowCoordinator::new(&port);

        coordinator.destroy_auxiliary().unwrap();

        assert_eq!(*port.destroyed.borrow(), [AuxiliaryWindow::Settings]);
    }

    #[test]
    fn does_not_destroy_unregistered_auxiliary_windows() {
        let port = RecordingPort::default();
        let coordinator = WindowCoordinator::new(&port);

        coordinator.destroy_auxiliary().unwrap();

        assert!(port.destroyed.borrow().is_empty());
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
    fn settings_window_is_created_shown_and_focused_on_first_open() {
        let port = RecordingPort::default();
        let coordinator = WindowCoordinator::new(&port);

        assert_eq!(
            coordinator
                .apply(WindowAction::ShowOrFocus(AuxiliaryWindow::Settings))
                .unwrap(),
            WindowLifecycle::Applied
        );
        assert_eq!(*port.created.borrow(), [AuxiliaryWindow::Settings]);
        assert_eq!(
            *port.operations.borrow(),
            [
                WindowAction::ShowOrFocus(AuxiliaryWindow::Settings),
                WindowAction::ShowOrFocus(AuxiliaryWindow::Settings),
            ]
        );
    }

    #[test]
    fn settings_window_shows_and_focuses_an_existing_instance() {
        let port = RecordingPort::with_registered(AuxiliaryWindow::Settings);
        let coordinator = WindowCoordinator::new(&port);

        assert_eq!(
            coordinator
                .apply(WindowAction::ShowOrFocus(AuxiliaryWindow::Settings))
                .unwrap(),
            WindowLifecycle::Applied
        );
        assert!(port.created.borrow().is_empty());
        assert_eq!(
            *port.operations.borrow(),
            [
                WindowAction::ShowOrFocus(AuxiliaryWindow::Settings),
                WindowAction::ShowOrFocus(AuxiliaryWindow::Settings),
            ]
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
    fn centers_overlay_at_five_sixths_of_monitor_work_area() {
        let (size, position) = overlay_bounds(
            PhysicalPosition::new(-1_920, 0),
            PhysicalSize::new(1_920, 1_080),
        );

        assert_eq!(size, PhysicalSize::new(1_600, 900));
        assert_eq!(position, PhysicalPosition::new(-1_760, 90));
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
