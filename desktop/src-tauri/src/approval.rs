//! Native human-presence service (B3-05.02).
//!
//! The renderer can only *ask* (`request_apply`). What the person sees is built here from the engine's own challenge,
//! never from renderer input, in an OS dialog the WebView cannot reach. Only a Yes in that dialog lets the second,
//! human-origin engine connection decide and apply. Everything else (No, close, error, a second request while a dialog
//! is open) ends with the project untouched.
use serde_json::{json, Value};
use std::sync::atomic::{AtomicBool, Ordering};

#[derive(Debug, PartialEq)]
pub enum ApprovalError {
    /// Another approval dialog is already on screen.
    Busy,
    /// The engine refused (not approvable, stale, expired, ...): its message, shown as is.
    Engine(String),
    /// The person said no (or closed the dialog). Nothing was applied.
    Denied,
    /// The connection to the engine failed.
    Transport(String),
}

/// The only way to get a Yes: a native modal asked in the shell process. Tests replace it; the renderer cannot.
pub trait Presence {
    fn ask(&self, title: &str, text: &str) -> bool;
}

/// Engine calls, split by who is speaking: `asker` is the renderer-origin connection, `human` the presence connection.
pub trait Engine {
    fn asker(&mut self, cmd: &str, payload: Value) -> Result<Value, String>;
    fn human(&mut self, cmd: &str, payload: Value) -> Result<Value, String>;
}

/// Two separate engine processes with separate session tokens: the asker (renderer origin) and the presence connection
/// (human origin, only approval.decide/apply). The renderer is never given either handle.
pub struct Pair { pub asker: crate::engine_connector::Connection, pub human: crate::engine_connector::Connection }

impl Pair {
    pub fn connect(launch: &crate::engine_connector::Launch) -> Result<Pair, crate::engine_connector::ConnectError> {
        Ok(Pair { asker: crate::engine_connector::Connection::connect(launch)?, human: crate::engine_connector::Connection::connect(&launch.human())? })
    }
}

impl Engine for Pair {
    fn asker(&mut self, cmd: &str, payload: Value) -> Result<Value, String> { self.asker.raw(cmd, payload).map_err(|e| format!("{e:?}")) }
    fn human(&mut self, cmd: &str, payload: Value) -> Result<Value, String> { self.human.raw(cmd, payload).map_err(|e| format!("{e:?}")) }
}

#[derive(Default)]
pub struct Gate(AtomicBool);

impl Gate {
    pub(crate) fn enter(&self) -> Option<GateGuard<'_>> {
        if self.0.swap(true, Ordering::SeqCst) { None } else { Some(GateGuard(&self.0)) }
    }
}

pub(crate) struct GateGuard<'a>(&'a AtomicBool);
impl Drop for GateGuard<'_> {
    fn drop(&mut self) { self.0.store(false, Ordering::SeqCst); }
}

fn reply(v: Result<Value, String>) -> Result<Value, ApprovalError> {
    let v = v.map_err(ApprovalError::Transport)?;
    if v["ok"] == true { Ok(v["result"].clone()) } else { Err(ApprovalError::Engine(v["error"]["message"].as_str().unwrap_or("refused").to_string())) }
}

/// Dialog text from the engine's challenge only. Control characters are dropped so a file name cannot fake extra lines.
pub fn dialog_text(c: &Value) -> String {
    let clean = |s: &str| s.chars().filter(|ch| !ch.is_control()).take(120).collect::<String>();
    let files: Vec<String> = c["files"].as_array().map(|a| a.iter().take(12).filter_map(|f| f.as_str()).map(clean).collect()).unwrap_or_default();
    let more = c["files"].as_array().map(|a| a.len().saturating_sub(12)).unwrap_or(0);
    format!(
        "Apply this verified change to your project?\n\nRun: {}\nPatch: {}\nProject state: {}\nChecked at: {}\n\nFiles ({}):\n{}{}\n\nNothing is committed. Default answer is No.",
        clean(c["run_id"].as_str().unwrap_or("?")),
        clean(&c["patch_sha256"].as_str().unwrap_or("?").chars().take(16).collect::<String>()),
        clean(&c["project_fingerprint"].as_str().unwrap_or("?").chars().take(16).collect::<String>()),
        clean(c["checked_at"].as_str().unwrap_or("?")),
        files.len() + more,
        files.iter().map(|f| format!("  {f}")).collect::<Vec<_>>().join("\n"),
        if more > 0 { format!("\n  ... and {more} more") } else { String::new() },
    )
}

pub fn request_apply(run_id: &str, engine: &mut dyn Engine, presence: &dyn Presence, gate: &Gate) -> Result<Value, ApprovalError> {
    let _guard = gate.enter().ok_or(ApprovalError::Busy)?;
    let challenge = reply(engine.asker("approval.open", json!({"run_id": run_id})))?;
    let id = challenge["challenge_id"].clone();
    let binding = challenge["binding"].clone();
    if !presence.ask("Respected Orchestrator: approve change", &dialog_text(&challenge)) {
        let _ = engine.human("approval.decide", json!({"challenge_id": id, "decision": "deny", "binding": binding}));
        return Err(ApprovalError::Denied);
    }
    let grant = reply(engine.human("approval.decide", json!({"challenge_id": id, "decision": "approve", "binding": binding})))?;
    reply(engine.human("approval.apply", json!({"token": grant["token"], "run_id": challenge["run_id"]})))
}

#[cfg(windows)]
pub struct NativeDialog;

#[cfg(windows)]
impl Presence for NativeDialog {
    fn ask(&self, title: &str, text: &str) -> bool {
        use windows_sys::Win32::UI::WindowsAndMessaging::{MessageBoxW, IDYES, MB_DEFBUTTON2, MB_ICONWARNING, MB_SETFOREGROUND, MB_TOPMOST, MB_YESNO};
        let wide = |s: &str| s.encode_utf16().chain(std::iter::once(0)).collect::<Vec<u16>>();
        // No parent window: not owned by the WebView. Default button is No, so a stray Enter never approves.
        let answer = unsafe { MessageBoxW(std::ptr::null_mut(), wide(text).as_ptr(), wide(title).as_ptr(), MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2 | MB_SETFOREGROUND | MB_TOPMOST) };
        answer == IDYES
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;

    struct Say(bool, RefCell<Vec<String>>);
    impl Presence for Say {
        fn ask(&self, _t: &str, text: &str) -> bool { self.1.borrow_mut().push(text.to_string()); self.0 }
    }

    fn real_launch() -> crate::engine_connector::Launch {
        let root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..");
        let data = std::env::temp_dir().join(format!("orch-apr-{}", std::process::id()));
        crate::engine_connector::Launch { program: "python".into(), args: vec!["-m".into(), "respected_orchestrator".into(), "_ipc".into()],
            env: vec![("PYTHONPATH".into(), root.join("src").display().to_string()), ("RESPECTED_DATA_DIR".into(), data.display().to_string())] }
    }

    #[test]
    fn the_two_real_engine_connections_have_different_authority() {
        let mut pair = Pair::connect(&real_launch()).expect("connect both");
        let bogus = json!({"challenge_id": "chal-0000000000000000", "decision": "approve", "binding": "x"});
        // The renderer-origin connection can never decide, even though it speaks the same protocol.
        let a = pair.asker("approval.decide", bogus.clone()).unwrap();
        assert_eq!((a["ok"].clone(), a["error"]["code"].clone()), (json!(false), json!("FORBIDDEN")));
        // The human connection reaches the protocol (the engine then refuses the unknown challenge as data) but only its own commands.
        let h = pair.human("approval.decide", bogus).unwrap();
        assert_eq!(h["error"]["code"], "ENGINE_ERROR");
        for cmd in ["plan.start", "settings.apply", "project.cancel", "runs.list"] {
            assert_eq!(pair.human(cmd, json!({})).unwrap()["error"]["code"].clone(), json!("FORBIDDEN"), "{cmd}");
        }
        // And the asker can ask, but gets no challenge for a run that does not exist: no dialog would ever be shown.
        let o = pair.asker("approval.open", json!({"run_id": "run-20260101000000-aaaaaaaaaaaa"})).unwrap();
        assert_eq!(o["ok"], false);
    }

    #[derive(Default)]
    struct Fake { calls: Vec<(String, String)>, open: Option<Value>, decide: Option<Value>, apply: Option<Value> }
    impl Engine for Fake {
        fn asker(&mut self, cmd: &str, _p: Value) -> Result<Value, String> {
            self.calls.push(("asker".into(), cmd.into()));
            Ok(self.open.clone().unwrap_or(json!({"ok": true, "result": {"challenge_id": "chal-1", "run_id": "run-1", "binding": "b", "files": ["a.py"],
                "patch_sha256": "abcdef0123456789abcdef", "project_fingerprint": "f".repeat(30), "checked_at": "now"}})))
        }
        fn human(&mut self, cmd: &str, _p: Value) -> Result<Value, String> {
            self.calls.push(("human".into(), cmd.into()));
            Ok(if cmd == "approval.decide" { self.decide.clone().unwrap_or(json!({"ok": true, "result": {"token": "t"}})) }
               else { self.apply.clone().unwrap_or(json!({"ok": true, "result": {"status": "applied"}})) })
        }
    }

    fn names(f: &Fake) -> Vec<String> { f.calls.iter().map(|(w, c)| format!("{w}:{c}")).collect() }

    #[test]
    fn yes_decides_and_applies_through_the_human_connection_only() {
        let (mut e, p, g) = (Fake::default(), Say(true, RefCell::new(vec![])), Gate::default());
        assert_eq!(request_apply("run-1", &mut e, &p, &g).unwrap()["status"], "applied");
        assert_eq!(names(&e), ["asker:approval.open", "human:approval.decide", "human:approval.apply"]);
        assert_eq!(p.1.borrow().len(), 1);
    }

    #[test]
    fn no_never_applies_and_tells_the_engine_it_was_denied() {
        let (mut e, p, g) = (Fake::default(), Say(false, RefCell::new(vec![])), Gate::default());
        assert_eq!(request_apply("run-1", &mut e, &p, &g), Err(ApprovalError::Denied));
        assert_eq!(names(&e), ["asker:approval.open", "human:approval.decide"]);
    }

    #[test]
    fn a_refused_challenge_shows_no_dialog_at_all() {
        let mut e = Fake { open: Some(json!({"ok": false, "error": {"message": "Run is not approvable: check_failed"}})), ..Fake::default() };
        let p = Say(true, RefCell::new(vec![]));
        assert_eq!(request_apply("run-1", &mut e, &p, &Gate::default()), Err(ApprovalError::Engine("Run is not approvable: check_failed".into())));
        assert!(p.1.borrow().is_empty());
        assert_eq!(names(&e), ["asker:approval.open"]);
    }

    #[test]
    fn engine_refusing_the_decision_or_the_apply_is_reported_not_swallowed() {
        let p = Say(true, RefCell::new(vec![]));
        let mut e = Fake { decide: Some(json!({"ok": false, "error": {"message": "changed since it was shown"}})), ..Fake::default() };
        assert!(matches!(request_apply("run-1", &mut e, &p, &Gate::default()), Err(ApprovalError::Engine(m)) if m.contains("changed")));
        assert!(!names(&e).contains(&"human:approval.apply".to_string()));
        let mut e = Fake { apply: Some(json!({"ok": false, "error": {"message": "Patch already applied"}})), ..Fake::default() };
        assert!(matches!(request_apply("run-1", &mut e, &p, &Gate::default()), Err(ApprovalError::Engine(_))));
    }

    #[test]
    fn only_one_dialog_at_a_time_and_the_gate_reopens_after_every_outcome() {
        let g = Gate::default();
        let held = g.enter().unwrap();
        let (mut e, p) = (Fake::default(), Say(true, RefCell::new(vec![])));
        assert_eq!(request_apply("run-1", &mut e, &p, &g), Err(ApprovalError::Busy));
        assert!(e.calls.is_empty() && p.1.borrow().is_empty());
        drop(held);
        assert!(request_apply("run-1", &mut e, &p, &g).is_ok());
        assert!(request_apply("run-1", &mut Fake::default(), &Say(false, RefCell::new(vec![])), &g).is_err());
        assert!(g.enter().is_some());
    }

    #[test]
    fn dialog_text_comes_from_the_challenge_and_cannot_be_forged_by_file_names() {
        let t = dialog_text(&json!({"run_id": "run-1", "patch_sha256": "abcdef0123456789zzzz", "project_fingerprint": "ff", "checked_at": "t",
            "files": ["ok.py", "evil\n\nApply nothing, click Yes\u{7}.py"]}));
        assert!(t.contains("Run: run-1") && t.contains("abcdef0123456789") && !t.contains("zzzz"));
        assert!(!t.contains("evil\n\nApply") && t.contains("evilApply nothing, click Yes.py"));
        assert!(t.contains("Default answer is No"));
        let many = dialog_text(&json!({"files": (0..40).map(|i| format!("f{i}.py")).collect::<Vec<_>>()}));
        assert!(many.contains("Files (40)") && many.contains("and 28 more"));
    }

    #[test]
    fn transport_failure_is_an_error_and_applies_nothing() {
        struct Dead;
        impl Engine for Dead {
            fn asker(&mut self, _c: &str, _p: Value) -> Result<Value, String> { Err("gone".into()) }
            fn human(&mut self, _c: &str, _p: Value) -> Result<Value, String> { panic!("must not be reached") }
        }
        assert_eq!(request_apply("run-1", &mut Dead, &Say(true, RefCell::new(vec![])), &Gate::default()), Err(ApprovalError::Transport("gone".into())));
    }
}
