pub mod engine_connector;

use engine_connector::{ConnectError, Connection, Status};
use std::path::PathBuf;
use std::sync::Mutex;
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
        .invoke_handler(tauri::generate_handler![engine_status])
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
    fn bundled_origin_only() {
        assert!(ok("tauri://localhost/index.html"));
        assert!(ok("http://tauri.localhost/"));
        for bad in ["https://example.com/", "http://evil.localhost/", "file:///C:/Windows/win.ini",
                    "http://127.0.0.1:8080/", "javascript:alert(1)", "about:blank", "http://tauri.localhost.evil.com/"] {
            assert!(!ok(bad), "{bad}");
        }
    }
}
