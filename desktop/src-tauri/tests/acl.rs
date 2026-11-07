//! The real embedded capabilities and the real command list, enforced by Tauri's own ACL on a mock runtime (B3-06.03):
//! the app window may call the shell's commands, the preview window (remote origin, no capability) may call none of them.
use respected_orchestrator_desktop_lib::configure;
use tauri::test::{get_ipc_response, mock_builder, MockRuntime, INVOKE_KEY};
use tauri::webview::InvokeRequest;
use tauri::{WebviewUrl, WebviewWindow, WebviewWindowBuilder};

const COMMANDS: [&str; 10] = ["engine_status", "confirm_close", "request_apply", "attach_image", "share_image", "revoke_image", "capability_inventory", "session_call", "read_call", "preview_open"];

fn call(w: &WebviewWindow<MockRuntime>, cmd: &str, from: &str, body: serde_json::Value) -> Result<serde_json::Value, serde_json::Value> {
    let request = InvokeRequest {
        cmd: cmd.into(), callback: tauri::ipc::CallbackFn(0), error: tauri::ipc::CallbackFn(1), url: from.parse().unwrap(),
        body: tauri::ipc::InvokeBody::Json(body), headers: Default::default(), invoke_key: INVOKE_KEY.into(),
    };
    get_ipc_response(w, request).map(|b| b.deserialize::<serde_json::Value>().unwrap_or(serde_json::Value::Null))
}

#[test]
fn the_preview_window_has_no_ipc_while_the_app_window_still_has() {
    std::env::set_var("RESPECTED_APP_DIR", std::env::temp_dir().join("orch-no-engine-acl"));
    let app = configure(mock_builder()).build(tauri::generate_context!()).expect("app");
    let main = WebviewWindowBuilder::new(&app, "main", WebviewUrl::App("index.html".into())).build().unwrap();
    let preview = WebviewWindowBuilder::new(&app, "preview", WebviewUrl::External("http://127.0.0.1:5173/".parse().unwrap())).build().unwrap();

    // positive control: the app window is NOT blocked by the ACL (the command itself answers: no engine is installed there)
    let ok = format!("{:?}", call(&main, "engine_status", "http://tauri.localhost/", serde_json::json!({})));
    assert!(!ok.contains("not allowed"), "the app window must keep its commands: {ok}");
    assert!(ok.contains("NotInstalled"), "{ok}");

    // the relay is a fixed list: a command outside it is refused by our code (not by the ACL) before it reaches the engine
    for cmd in ["approval.decide", "approval.apply", "session.approve", "settings.apply"] {
        let answer = format!("{:?}", call(&main, "session_call", "http://tauri.localhost/", serde_json::json!({"cmd": cmd, "payload": {}})));
        assert!(answer.contains("Refused") && !answer.contains("NotInstalled"), "{cmd} was relayed: {answer}");
    }
    let listed = format!("{:?}", call(&main, "session_call", "http://tauri.localhost/", serde_json::json!({"cmd": "sessions.list", "payload": {"project_id": "proj-1"}})));
    assert!(listed.contains("NotInstalled"), "a listed command reaches the connection: {listed}");

    // read_call is a second fixed list (the Beta.4 read-only views): anything else is refused by our code before it reaches the engine
    for cmd in ["approval.decide", "plan.start", "settings.apply", "session.start", "team.save", "capabilities.activate", "TEAM.VIEW", ""] {
        let answer = format!("{:?}", call(&main, "read_call", "http://tauri.localhost/", serde_json::json!({"cmd": cmd, "payload": {}})));
        assert!(answer.contains("Refused") && !answer.contains("NotInstalled"), "{cmd:?} was relayed by read_call: {answer}");
    }
    for cmd in ["team.view", "capabilities.recommend", "analytics.summary"] {
        let answer = format!("{:?}", call(&main, "read_call", "http://tauri.localhost/", serde_json::json!({"cmd": cmd, "payload": {}})));
        assert!(answer.contains("NotInstalled"), "{cmd} should reach the connection: {answer}");
    }

    // the preview window: every shell command is refused by the ACL before any of our code runs, whatever origin it claims
    for cmd in COMMANDS {
        for from in ["http://127.0.0.1:5173/", "http://127.0.0.1:5173/page?x=1", "http://tauri.localhost/", "tauri://localhost/"] {
            let answer = call(&preview, cmd, from, serde_json::json!({"runId": "run-1", "projectRoot": null, "url": "http://127.0.0.1:5173/"}));
            let text = format!("{answer:?}");
            assert!(answer.is_err() && text.contains("not allowed"), "{cmd} from {from} reached the shell: {text}");
        }
    }
    // and nothing outside our own commands (plugins, events, window control) is open to it either
    for cmd in ["plugin:event|listen", "plugin:event|emit", "plugin:window|close", "plugin:webview|create_webview_window", "plugin:path|resolve_directory",
                "plugin:app|app_hide", "plugin:resources|close"] {
        let answer = call(&preview, cmd, "http://127.0.0.1:5173/", serde_json::json!({}));
        assert!(answer.is_err(), "{cmd}: {answer:?}");
    }
}
