pub mod engine_connector;

use engine_connector::{ConnectError, Connection, Status};
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use tauri::{Emitter, Manager};
use tauri::Url;

#[derive(serde::Serialize)]
pub struct EngineProblem { error: ConnectError, hint: &'static str }

/// The only command the renderer may call: read-only engine status, no arguments, no raw dispatch.
#[tauri::command]
fn engine_status(state: tauri::State<Mutex<Option<Connection>>>) -> Result<Status, EngineProblem> {
    let problem = |error: ConnectError| EngineProblem { hint: error.hint(), error };
    let mut slot = state.lock().unwrap();
    if let Some(c) = slot.as_mut() {
        match c.status() {
            Ok(s) => return Ok(s),
            Err(_) => *slot = None, // engine went away: drop it and reconnect below
        }
    }
    let launch = engine_connector::discover(
        std::env::var_os("RESPECTED_APP_DIR").map(PathBuf::from),
        std::env::var_os("LOCALAPPDATA").map(PathBuf::from),
    ).map_err(problem)?;
    let mut c = Connection::connect(&launch).map_err(problem)?;
    let status = c.status().map_err(problem)?;
    *slot = Some(c);
    Ok(status)
}

/// Closing the window is only held back to tell the user that active runs keep going; it never stops them.
pub fn must_ask(active_runs: usize, already_confirmed: bool) -> bool { active_runs > 0 && !already_confirmed }

#[derive(Default)]
struct CloseConfirmed(AtomicBool);

/// Second and last renderer command: the user confirmed closing while runs are active.
#[tauri::command]
fn confirm_close(window: tauri::Window, confirmed: tauri::State<CloseConfirmed>) {
    confirmed.0.store(true, Ordering::SeqCst);
    let _ = window.close();
}

/// Only the app's own bundled origin may be shown. Dev server is allowed in debug builds only.
pub fn navigation_allowed(url: &Url) -> bool {
    match (url.scheme(), url.host_str()) {
        ("tauri", Some("localhost")) => true,
        ("http" | "https", Some("tauri.localhost")) => true,
        ("http", Some("127.0.0.1")) => cfg!(debug_assertions) && url.port() == Some(1430),
        _ => false,
    }
}

pub fn run() {
    tauri::Builder::default()
        .manage(Mutex::new(None::<Connection>))
        .manage(CloseConfirmed::default())
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let active = window.state::<Mutex<Option<Connection>>>().lock().unwrap()
                    .as_mut().and_then(|c| c.active_runs().ok()).unwrap_or(0);
                if must_ask(active, window.state::<CloseConfirmed>().0.load(Ordering::SeqCst)) {
                    api.prevent_close();
                    let _ = window.emit("close-blocked", active);
                }
            }
        })
        .invoke_handler(tauri::generate_handler![engine_status, confirm_close])
        .plugin(
            tauri::plugin::Builder::<tauri::Wry, ()>::new("navigation-guard")
                .on_navigation(|_, url| navigation_allowed(url))
                .build(),
        )
        .run(tauri::generate_context!())
        .expect("failed to start Respected Orchestrator");
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ok(s: &str) -> bool { navigation_allowed(&s.parse().unwrap()) }

    #[test]
    fn close_asks_only_when_runs_are_active_and_not_yet_confirmed() {
        assert!(!must_ask(0, false));
        assert!(must_ask(2, false));
        assert!(!must_ask(2, true));
    }

    #[test]
    fn bundled_origin_only() {
        assert!(ok("tauri://localhost/index.html"));
        assert!(ok("http://tauri.localhost/"));
        for bad in ["https://example.com/", "http://evil.localhost/", "file:///C:/Windows/win.ini",
                    "http://127.0.0.1:8080/", "javascript:alert(1)", "about:blank", "http://tauri.localhost.evil.com/"] {
            assert!(!ok(bad), "{bad}");
        }
    }
}
