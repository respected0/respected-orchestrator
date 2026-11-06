//! Engine connector (B3-01.03): the shell starts the engine itself and talks to it over the child's own stdio,
//! so there is no port or pipe another process could own. No raw command dispatch: only `hello` + `engine.health`.
use serde::Serialize;
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};

pub const IPC: &str = "1";
pub const PRODUCT_ID: &str = "respected-orchestrator";

#[derive(Debug, Clone)]
pub struct Launch {
    pub program: PathBuf,
    pub args: Vec<String>,
    pub env: Vec<(String, String)>,
}

#[derive(Debug, Serialize, PartialEq)]
#[serde(tag = "kind", content = "detail")]
pub enum ConnectError {
    /// No engine installed where the installer puts it.
    NotInstalled(String),
    /// Started but did not answer the handshake sensibly (broken install, not our engine, garbage output).
    BrokenInstall(String),
    /// Answered, but as another product.
    WrongOwner(String),
    /// Speaks another IPC version.
    VersionMismatch(String),
    /// The engine process went away mid-session.
    Disconnected(String),
}

impl ConnectError {
    pub fn hint(&self) -> &'static str {
        match self {
            ConnectError::NotInstalled(_) | ConnectError::BrokenInstall(_) => "Respected Orchestrator kurucusunu yeniden çalıştırın (Onar).",
            ConnectError::WrongOwner(_) => "Reddedildi: bu program Respected Orchestrator'ın motoru değil.",
            ConnectError::VersionMismatch(_) => "Uygulamayı ve motoru aynı sürüme güncelleyin.",
            ConnectError::Disconnected(_) => "Motor durdu; yeniden bağlanmayı deneyin.",
        }
    }
}

#[derive(Debug, Serialize, PartialEq)]
pub struct Status {
    pub version: String,
    pub healthy: bool,
}

/// The engine launcher's file name inside an install folder (ADR-025).
pub const LAUNCHER: &str = "respected-orchestrator.exe";

fn sha256_hex(path: &std::path::Path) -> std::io::Result<String> {
    use sha2::{Digest, Sha256};
    let mut file = std::fs::File::open(path)?;
    let mut hasher = Sha256::new();
    std::io::copy(&mut file, &mut hasher)?;
    Ok(hasher.finalize().iter().map(|b| format!("{b:02x}")).collect())
}

/// The launcher must be exactly the file the package manifest recorded, before it is ever started (ADR-025).
/// `dev_override`: the contract's RESPECTED_APP_DIR test/dev folder may have no manifest; an installed folder must.
pub fn verify_launcher(dir: &std::path::Path, dev_override: bool) -> Result<(), ConnectError> {
    let broken = |m: String| ConnectError::BrokenInstall(m);
    let manifest = dir.join("distribution.json");
    if !manifest.is_file() {
        return if dev_override { Ok(()) } else { Err(broken("distribution.json is missing from the install folder".into())) };
    }
    let text = std::fs::read_to_string(&manifest).map_err(|e| broken(format!("distribution.json unreadable: {e}")))?;
    let doc: Value = serde_json::from_str(&text).map_err(|_| broken("distribution.json is not valid JSON".into()))?;
    let expected = doc["files"][LAUNCHER].as_str().ok_or_else(|| broken("the launcher is not listed in distribution.json".into()))?;
    let actual = sha256_hex(&dir.join(LAUNCHER)).map_err(|e| broken(format!("the launcher cannot be read: {e}")))?;
    if !actual.eq_ignore_ascii_case(expected) {
        return Err(broken("the engine launcher does not match distribution.json".into()));
    }
    Ok(())
}

/// Installed engine, searched in this order: `RESPECTED_APP_DIR` (the contract's test/dev override; when set it is the only place looked at),
/// the folder this program itself lives in, then `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app` (PRODUCT_CONTRACT section 2).
/// The launcher is hash-checked against `distribution.json` before it is returned.
pub fn discover(app_dir: Option<PathBuf>, exe_dir: Option<PathBuf>, local_app_data: Option<PathBuf>) -> Result<Launch, ConnectError> {
    let candidates: Vec<(PathBuf, bool)> = match app_dir {
        Some(dir) => vec![(dir, true)],
        None => exe_dir.into_iter().map(|d| (d, false))
            .chain(local_app_data.map(|p| (p.join("Respected").join("RespectedOrchestrator").join("app"), false))).collect(),
    };
    let mut first_missing: Option<PathBuf> = None;
    for (dir, dev_override) in candidates {
        let exe = dir.join(LAUNCHER);
        if !exe.is_file() {
            first_missing.get_or_insert(exe);
            continue;
        }
        verify_launcher(&dir, dev_override)?;
        return Ok(Launch { program: exe, args: vec!["_ipc".into()], env: vec![] });
    }
    Err(ConnectError::NotInstalled(first_missing.map(|p| p.display().to_string()).unwrap_or_else(|| "no program folder".into())))
}

/// `discover` with the real environment: the override, this program's own folder, the per-user install folder.
pub fn discover_env() -> Result<Launch, ConnectError> {
    discover(
        std::env::var_os("RESPECTED_APP_DIR").map(PathBuf::from),
        std::env::current_exe().ok().and_then(|p| p.parent().map(PathBuf::from)),
        std::env::var_os("LOCALAPPDATA").map(PathBuf::from),
    )
}

impl Launch {
    /// The same engine, started as the native presence connection. The renderer never gets a handle to it.
    pub fn human(&self) -> Launch {
        let mut l = self.clone();
        l.args.push("--human".into());
        l
    }
}

pub struct Connection {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
    token: String,
    n: u64,
    pub version: String,
}

fn token() -> String {
    let mut b = [0u8; 24];
    getrandom::fill(&mut b).expect("os random");
    b.iter().map(|x| format!("{x:02x}")).collect()
}

impl Connection {
    pub fn connect(launch: &Launch) -> Result<Connection, ConnectError> {
        let token = token();
        let mut cmd = Command::new(&launch.program);
        cmd.args(&launch.args).envs(launch.env.iter().cloned()).env("RESPECTED_IPC_TOKEN", &token)
            .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
        #[cfg(windows)]
        std::os::windows::process::CommandExt::creation_flags(&mut cmd, 0x0800_0000); // CREATE_NO_WINDOW
        let mut child = cmd.spawn().map_err(|e| ConnectError::NotInstalled(e.to_string()))?;
        let stdin = child.stdin.take().unwrap();
        let stdout = BufReader::new(child.stdout.take().unwrap());
        let mut c = Connection { child, stdin, stdout, token, n: 0, version: String::new() };
        let hello = c.call("hello")?;
        if hello["ipc"] != IPC || hello["result"]["ipc"] != IPC {
            return Err(ConnectError::VersionMismatch(hello["ipc"].to_string()));
        }
        let manifest = c.call("engine.manifest")?;
        match manifest["result"]["product_id"].as_str() {
            Some(PRODUCT_ID) => {}
            other => return Err(ConnectError::WrongOwner(format!("{other:?}"))),
        }
        c.version = manifest["result"]["product_version"].as_str().unwrap_or("").to_string();
        Ok(c)
    }

    /// One request, the engine's whole reply (including `ok:false`): transport failures are errors, engine refusals are data.
    pub fn raw(&mut self, cmd: &str, payload: Value) -> Result<Value, ConnectError> {
        self.n += 1;
        let req = json!({"ipc": IPC, "id": format!("shell-{:08}", self.n), "session": self.token, "cmd": cmd, "payload": payload});
        let gone = |e: String| ConnectError::Disconnected(e);
        writeln!(self.stdin, "{req}").and_then(|_| self.stdin.flush()).map_err(|e| gone(e.to_string()))?;
        let mut line = String::new();
        if self.stdout.read_line(&mut line).map_err(|e| gone(e.to_string()))? == 0 {
            return Err(gone("engine closed the connection".into()));
        }
        serde_json::from_str(&line).map_err(|_| ConnectError::BrokenInstall(line.chars().take(120).collect()))
    }

    fn call(&mut self, cmd: &str) -> Result<Value, ConnectError> {
        let v = self.raw(cmd, json!({}))?;
        if v["ok"] != true {
            return Err(ConnectError::BrokenInstall(v["error"].to_string()));
        }
        Ok(v)
    }

    pub fn status(&mut self) -> Result<Status, ConnectError> {
        let h = self.call("engine.health")?;
        Ok(Status { version: self.version.clone(), healthy: h["result"]["status"] == "healthy" })
    }

    /// Number of runs a live worker still holds (read-only; closing the window never touches them).
    pub fn active_runs(&mut self) -> Result<usize, ConnectError> {
        let v = self.call("runs.active")?;
        Ok(v["result"]["runs"].as_object().map(|m| m.len()).unwrap_or(0))
    }

    /// Read-only MCP/skill inventory (B3-08). Nothing is started, installed or enabled by asking; the engine's whole reply is returned as data.
    pub fn inventory(&mut self, project_root: Option<String>) -> Result<Value, ConnectError> {
        let payload = match project_root { Some(p) => json!({"project_root": p}), None => json!({}) };
        self.raw("capabilities.inventory", payload)
    }

    /// The stored settings as the engine reports them (single source for feature flags such as the local preview).
    pub fn settings_readback(&mut self) -> Result<Value, ConnectError> {
        self.raw("settings.readback", json!({}))
    }

    pub fn kill(&mut self) { let _ = self.child.kill(); let _ = self.child.wait(); }
}

impl Drop for Connection {
    fn drop(&mut self) { self.kill(); }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn py(args: &[&str]) -> Launch {
        Launch { program: "python".into(), args: args.iter().map(|s| s.to_string()).collect(), env: vec![] }
    }

    fn real() -> Launch {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..");
        let data = std::env::temp_dir().join(format!("orch-conn-{}", std::process::id()));
        let mut l = py(&["-m", "respected_orchestrator", "_ipc"]);
        l.env = vec![("PYTHONPATH".into(), root.join("src").display().to_string()), ("RESPECTED_DATA_DIR".into(), data.display().to_string())];
        l
    }

    const FAKE: &str = "import sys,json\nfor l in sys.stdin:\n r=json.loads(l)\n print(json.dumps({'ipc':'IPCV','id':r['id'],'ok':True,'result':{'ipc':'IPCV','product_id':'PROD'}}),flush=True)\n";

    fn fake(ipc: &str, product: &str) -> Launch {
        py(&["-c", &FAKE.replace("IPCV", ipc).replace("PROD", product)])
    }

    #[test]
    fn missing_engine_is_not_installed() {
        let dir = std::env::temp_dir().join("orch-no-engine");
        assert!(matches!(discover(Some(dir), None, None), Err(ConnectError::NotInstalled(_))));
        assert!(matches!(discover(None, None, None), Err(ConnectError::NotInstalled(_))));
        assert!(matches!(Connection::connect(&Launch { program: "definitely-not-an-engine.exe".into(), args: vec![], env: vec![] }), Err(ConnectError::NotInstalled(_))));
    }

    fn scratch(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("orch-pkg-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    /// A folder shaped like an install: a launcher file and a manifest that lists its real hash.
    fn install(dir: &std::path::Path, launcher: &[u8], manifest: bool) {
        std::fs::write(dir.join(LAUNCHER), launcher).unwrap();
        if manifest {
            let h = sha256_hex(&dir.join(LAUNCHER)).unwrap();
            std::fs::write(dir.join("distribution.json"), json!({"schema_version": 1, "files": {LAUNCHER: h}}).to_string()).unwrap();
        }
    }

    #[test]
    fn a_matching_manifest_lets_the_launcher_through_and_any_change_stops_it_before_it_runs() {
        let d = scratch("verify");
        install(&d, b"engine v1", true);
        assert!(discover(None, Some(d.clone()), None).is_ok());
        std::fs::write(d.join(LAUNCHER), b"engine v1 + implant").unwrap(); // tampered after packaging
        assert!(matches!(discover(None, Some(d.clone()), None), Err(ConnectError::BrokenInstall(m)) if m.contains("does not match")));
        assert!(matches!(discover(Some(d.clone()), None, None), Err(ConnectError::BrokenInstall(_))), "a dev override is checked too when a manifest exists");
        std::fs::remove_dir_all(&d).ok();
    }

    #[test]
    fn missing_or_broken_manifests_fail_closed_for_installed_folders_only() {
        let d = scratch("manifest");
        install(&d, b"engine", false);
        assert!(matches!(discover(None, Some(d.clone()), None), Err(ConnectError::BrokenInstall(m)) if m.contains("missing")));
        assert!(discover(Some(d.clone()), None, None).is_ok(), "the dev override may have no manifest");
        for bad in ["not json at all", "{}", "{\"files\": {}}", "{\"files\": {\"respected-orchestrator.exe\": 5}}", "[]", "{\"files\": {\"other.exe\": \"00\"}}"] {
            std::fs::write(d.join("distribution.json"), bad).unwrap();
            assert!(matches!(discover(None, Some(d.clone()), None), Err(ConnectError::BrokenInstall(_))), "{bad}");
        }
        std::fs::remove_dir_all(&d).ok();
    }

    #[test]
    fn the_engine_next_to_the_shell_wins_and_the_explicit_override_is_exclusive() {
        let (own, per_user, other) = (scratch("own"), scratch("peruser"), scratch("override"));
        install(&own, b"own engine", true);
        let app = per_user.join("Respected").join("RespectedOrchestrator").join("app");
        std::fs::create_dir_all(&app).unwrap();
        install(&app, b"per-user engine", true);
        let chosen = discover(None, Some(own.clone()), Some(per_user.clone())).unwrap();
        assert_eq!(chosen.program, own.join(LAUNCHER));
        let fallback = discover(None, Some(scratch("empty")), Some(per_user.clone())).unwrap();
        assert_eq!(fallback.program, app.join(LAUNCHER));
        // an override that points at nothing is NotInstalled; it never falls back to a real install
        assert!(matches!(discover(Some(other.clone()), Some(own.clone()), Some(per_user.clone())), Err(ConnectError::NotInstalled(_))));
        // a tampered engine next to the shell is an error, not a silent fallback to another copy
        std::fs::write(own.join(LAUNCHER), b"tampered").unwrap();
        assert!(matches!(discover(None, Some(own.clone()), Some(per_user.clone())), Err(ConnectError::BrokenInstall(_))));
        for d in [own, per_user, other] { std::fs::remove_dir_all(&d).ok(); }
    }

    #[test]
    fn garbage_output_is_a_broken_install() {
        assert!(matches!(Connection::connect(&py(&["-c", "print('garbage')"])), Err(ConnectError::BrokenInstall(_))));
        assert!(matches!(Connection::connect(&py(&["-c", "pass"])), Err(ConnectError::Disconnected(_))));
    }

    #[test]
    fn other_product_is_refused() {
        assert!(matches!(Connection::connect(&fake("1", "respected-hub")), Err(ConnectError::WrongOwner(_))));
    }

    #[test]
    fn other_ipc_version_is_refused() {
        assert!(matches!(Connection::connect(&fake("2", PRODUCT_ID)), Err(ConnectError::VersionMismatch(_))));
    }

    #[test]
    fn inventory_comes_from_the_engine_as_data_and_changes_nothing() {
        let home = std::env::temp_dir().join(format!("orch-inv-home-{}", std::process::id()));
        std::fs::create_dir_all(home.join(".codex")).unwrap();
        let config = home.join(".codex").join("config.toml");
        std::fs::write(&config, "[mcp_servers.demo]
command = \"definitely-not-installed-xyz\"
[mcp_servers.demo.env]
TOKEN = \"sk-SHOULDNEVERAPPEAR123456\"
").unwrap();
        let before = std::fs::read(&config).unwrap();
        let mut launch = real();
        launch.env.push(("USERPROFILE".into(), home.display().to_string()));
        launch.env.push(("HOME".into(), home.display().to_string()));
        let mut c = Connection::connect(&launch).expect("connect");
        let reply = c.inventory(None).expect("inventory");
        assert_eq!(reply["ok"], true, "{reply}");
        let caps = reply["result"]["capabilities"].as_array().unwrap();
        assert_eq!(caps.len(), 1);
        assert_eq!(caps[0]["name"], "demo");
        assert_eq!(caps[0]["status"]["installed"]["state"], false);
        assert_eq!(caps[0]["status"]["verified"]["state"], false);
        assert_eq!(caps[0]["status"]["trusted"]["state"], false);
        assert!(!reply.to_string().contains("SHOULDNEVERAPPEAR"));
        assert_eq!(std::fs::read(&config).unwrap(), before);
        assert_eq!(c.inventory(Some("relative/dir".into())).unwrap()["error"]["code"], "BAD_REQUEST");
        std::fs::remove_dir_all(&home).ok();
    }

    #[test]
    fn real_engine_handshake_crash_and_reconnect() {
        let launch = real();
        let mut c = Connection::connect(&launch).expect("connect");
        assert!(!c.version.is_empty());
        assert_eq!(c.status().unwrap().version, c.version);
        c.kill();
        assert!(matches!(c.status(), Err(ConnectError::Disconnected(_))));
        let mut again = Connection::connect(&launch).expect("reconnect");
        assert!(again.status().is_ok());
    }
}
