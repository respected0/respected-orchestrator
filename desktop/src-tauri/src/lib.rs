pub mod approval;
pub mod image_consent;
pub mod preview;
pub mod engine_connector;

use engine_connector::{ConnectError, Connection, Status};
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
    let launch = engine_connector::discover_env().map_err(problem)?;
    let mut c = Connection::connect(&launch).map_err(problem)?;
    let status = c.status().map_err(problem)?;
    *slot = Some(c);
    Ok(status)
}

/// The renderer may only *ask* to apply a run. The decision is made in a native dialog the WebView cannot reach, and the
/// answer comes back as data (never the token, never a handle to the human connection).
#[tauri::command]
async fn request_apply(run_id: String, state: tauri::State<'_, Mutex<Option<approval::Pair>>>, gate: tauri::State<'_, approval::Gate>) -> Result<serde_json::Value, String> {
    let mut slot = state.try_lock().map_err(|_| "Another approval is in progress.".to_string())?;
    if slot.is_none() {
        let launch = engine_connector::discover_env().map_err(|e| format!("{e:?}"))?;
        *slot = Some(approval::Pair::connect(&launch).map_err(|e| format!("{e:?}"))?);
    }
    #[cfg(windows)]
    let result = approval::request_apply(&run_id, slot.as_mut().unwrap(), &approval::NativeDialog, &gate);
    #[cfg(not(windows))]
    let result: Result<serde_json::Value, approval::ApprovalError> = { let _ = (&run_id, &gate); Err(approval::ApprovalError::Engine("Native approval is only available on Windows.".into())) };
    if matches!(result, Err(approval::ApprovalError::Transport(_))) { *slot = None; }
    result.map_err(|e| format!("{e:?}"))
}

type PairSlot<'a> = tauri::State<'a, Mutex<Option<approval::Pair>>>;

/// Runs one image-consent step on the pair of engine connections. The renderer names run/image ids and a provider; the dialog text is built
/// from the engine's own records (image_consent.rs), in an OS dialog the WebView cannot reach.
fn consent_step(state: &PairSlot<'_>, step: impl FnOnce(&mut approval::Pair) -> Result<serde_json::Value, image_consent::ConsentError>) -> Result<serde_json::Value, String> {
    let mut slot = state.try_lock().map_err(|_| "Another confirmation is in progress.".to_string())?;
    if slot.is_none() {
        let launch = engine_connector::discover_env().map_err(|e| format!("{e:?}"))?;
        *slot = Some(approval::Pair::connect(&launch).map_err(|e| format!("{e:?}"))?);
    }
    let result = step(slot.as_mut().unwrap());
    if matches!(result, Err(image_consent::ConsentError::Transport(_))) { *slot = None; }
    result.map_err(|e| format!("{e:?}"))
}

#[tauri::command]
async fn attach_image(run_id: String, stage_id: String, sha256: String, regions: u64, state: PairSlot<'_>, gate: tauri::State<'_, approval::Gate>) -> Result<serde_json::Value, String> {
    #[cfg(windows)]
    return consent_step(&state, |pair| image_consent::request_attach(&run_id, &stage_id, &sha256, regions, pair, &approval::NativeDialog, &gate));
    #[cfg(not(windows))]
    { let _ = (&run_id, &stage_id, &sha256, regions, &state, &gate); Err("Native confirmation is only available on Windows.".into()) }
}

#[tauri::command]
async fn share_image(run_id: String, attachment_id: String, provider: String, state: PairSlot<'_>, gate: tauri::State<'_, approval::Gate>) -> Result<serde_json::Value, String> {
    #[cfg(windows)]
    return consent_step(&state, |pair| image_consent::request_share(&run_id, &attachment_id, &provider, pair, &approval::NativeDialog, &gate));
    #[cfg(not(windows))]
    { let _ = (&run_id, &attachment_id, &provider, &state, &gate); Err("Native confirmation is only available on Windows.".into()) }
}

#[tauri::command]
async fn revoke_image(run_id: String, attachment_id: String, state: PairSlot<'_>, gate: tauri::State<'_, approval::Gate>) -> Result<serde_json::Value, String> {
    consent_step(&state, |pair| image_consent::request_revoke(&run_id, &attachment_id, pair, &gate))
}

/// Read-only inventory of the MCP servers and skills the installed agent clients already have. The renderer may name at most a
/// project folder; the engine validates it, never runs or contacts anything, and returns redacted data.
#[tauri::command]
fn capability_inventory(project_root: Option<String>, state: tauri::State<Mutex<Option<Connection>>>) -> Result<serde_json::Value, EngineProblem> {
    let problem = |error: ConnectError| EngineProblem { hint: error.hint(), error };
    let mut slot = state.lock().unwrap();
    if slot.is_none() {
        let launch = engine_connector::discover_env().map_err(problem)?;
        *slot = Some(Connection::connect(&launch).map_err(problem)?);
    }
    match slot.as_mut().unwrap().inventory(project_root) {
        Ok(v) => Ok(v),
        Err(e) => { *slot = None; Err(problem(e)) }
    }
}

/// Relays one chat-session command (start, send, interrupt...) to the engine. The renderer names the command but only from the fixed
/// list in engine_connector; the engine checks authority, session ownership and the input again, and treats the text as data.
#[tauri::command]
fn session_call(cmd: String, payload: serde_json::Value, state: tauri::State<Mutex<Option<Connection>>>) -> Result<serde_json::Value, EngineProblem> {
    let problem = |error: ConnectError| EngineProblem { hint: error.hint(), error };
    if !engine_connector::session_command_allowed(&cmd) {
        return Err(problem(ConnectError::Refused(cmd)));
    }
    let mut slot = state.lock().unwrap();
    if slot.is_none() {
        let launch = engine_connector::discover_env().map_err(problem)?;
        *slot = Some(Connection::connect(&launch).map_err(problem)?);
    }
    match slot.as_mut().unwrap().raw(&cmd, payload) {
        Ok(v) => Ok(v),
        Err(e) => { *slot = None; Err(problem(e)) }
    }
}
/// Relays one read-only Beta.4 view to the engine. The renderer names the command but only from `READ_COMMANDS`; the engine checks the
/// origin again and these commands can only read.
#[tauri::command]
fn read_call(cmd: String, payload: serde_json::Value, state: tauri::State<Mutex<Option<Connection>>>) -> Result<serde_json::Value, EngineProblem> {
    let problem = |error: ConnectError| EngineProblem { hint: error.hint(), error };
    if !engine_connector::read_command_allowed(&cmd) {
        return Err(problem(ConnectError::Refused(cmd)));
    }
    let mut slot = state.lock().unwrap();
    if slot.is_none() {
        let launch = engine_connector::discover_env().map_err(problem)?;
        *slot = Some(Connection::connect(&launch).map_err(problem)?);
    }
    match slot.as_mut().unwrap().raw(&cmd, payload) {
        Ok(v) => Ok(v),
        Err(e) => { *slot = None; Err(problem(e)) }
    }
}
static PREVIEW_GENERATION: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);

/// Opens one untrusted local page (B3-06.03). Refused unless the user turned the preview on in the engine settings and listed the port.
/// The page gets its own window label with no capability (no IPC), an incognito profile (no shared cookies or storage), same-origin-only
/// navigation, and is closed after ten minutes. The renderer only supplies the address; every rule is applied here.
#[tauri::command]
async fn preview_open<R: tauri::Runtime>(url: String, app: tauri::AppHandle<R>, state: tauri::State<'_, Mutex<Option<Connection>>>) -> Result<String, String> {
    let settings = {
        let mut slot = state.lock().unwrap();
        if slot.is_none() {
            let launch = engine_connector::discover_env().map_err(|e| format!("{e:?}"))?;
            *slot = Some(Connection::connect(&launch).map_err(|e| format!("{e:?}"))?);
        }
        match slot.as_mut().unwrap().settings_readback() {
            Ok(reply) => preview::settings_from_reply(&reply),
            Err(_) => { *slot = None; preview::Settings { enabled: false, ports: vec![] } }
        }
    };
    let parsed = preview::check_url(&url, &settings).map_err(|d| d.message())?;
    if let Some(old) = app.get_webview_window("preview") { let _ = old.destroy(); }
    let origin = parsed.clone();
    tauri::WebviewWindowBuilder::new(&app, "preview", tauri::WebviewUrl::External(parsed.clone()))
        .title("Önizleme (güvenilmeyen içerik)")
        .inner_size(1000.0, 700.0)
        .incognito(true)
        .on_navigation(move |next| preview::same_origin(&origin, next))
        .build()
        .map_err(|e| format!("pencere açılamadı: {e}"))?;
    let generation = PREVIEW_GENERATION.fetch_add(1, Ordering::SeqCst) + 1;
    let handle = app.clone();
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_secs(preview::OPEN_SECONDS));
        if PREVIEW_GENERATION.load(Ordering::SeqCst) == generation {
            if let Some(w) = handle.get_webview_window("preview") { let _ = w.destroy(); }
        }
    });
    Ok(parsed.to_string())
}

/// Closing the window is only held back to tell the user that active runs keep going; it never stops them.
pub fn must_ask(active_runs: usize, already_confirmed: bool) -> bool { active_runs > 0 && !already_confirmed }

#[derive(Default)]
struct CloseConfirmed(AtomicBool);

/// Second and last renderer command: the user confirmed closing while runs are active.
#[tauri::command]
fn confirm_close<R: tauri::Runtime>(window: tauri::Window<R>, confirmed: tauri::State<CloseConfirmed>) {
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

/// The preview window is untrusted content on a loopback origin: the app-wide guard lets it through, its own per-window rule
/// (`preview::same_origin`) then keeps it on the origin that was opened. Every other window keeps the bundled-origin rule.
pub fn navigation_allowed_for(label: &str, url: &Url) -> bool {
    label == "preview" || navigation_allowed(url)
}

/// Everything except the navigation-guard plugin, generic over the runtime so an integration test can run the real command list
/// and the real capabilities on a mock runtime.
pub fn configure<R: tauri::Runtime>(builder: tauri::Builder<R>) -> tauri::Builder<R> {
    builder
        .manage(Mutex::new(None::<Connection>))
        .manage(CloseConfirmed::default())
        .manage(Mutex::new(None::<approval::Pair>))
        .manage(approval::Gate::default())
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.label() != "main" { return; }
                let active = window.state::<Mutex<Option<Connection>>>().lock().unwrap()
                    .as_mut().and_then(|c| c.active_runs().ok()).unwrap_or(0);
                if must_ask(active, window.state::<CloseConfirmed>().0.load(Ordering::SeqCst)) {
                    api.prevent_close();
                    let _ = window.emit("close-blocked", active);
                }
            }
        })
        .invoke_handler(tauri::generate_handler![engine_status, confirm_close, request_apply, attach_image, share_image, revoke_image, capability_inventory, session_call, read_call, preview_open])
}

pub fn run() {
    configure(tauri::Builder::default())
        .plugin(
            tauri::plugin::Builder::<tauri::Wry, ()>::new("navigation-guard")
                .on_navigation(|webview, url| navigation_allowed_for(webview.label(), url))
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
    fn only_the_preview_window_may_load_a_loopback_page_and_every_other_window_keeps_the_bundled_rule() {
        let local: Url = "http://127.0.0.1:5173/".parse().unwrap();
        assert!(navigation_allowed_for("preview", &local));
        for label in ["main", "other", "preview2", "", "Preview"] {
            assert!(!navigation_allowed_for(label, &local), "{label}");
        }
        assert!(navigation_allowed_for("main", &"tauri://localhost/index.html".parse().unwrap()));
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
