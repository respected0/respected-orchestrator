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
            ConnectError::NotInstalled(_) | ConnectError::BrokenInstall(_) => "Run the Respected Orchestrator installer again (repair).",
            ConnectError::WrongOwner(_) => "Refused: the program is not Respected Orchestrator's engine.",
            ConnectError::VersionMismatch(_) => "Update the app and the engine to the same release.",
            ConnectError::Disconnected(_) => "The engine stopped; reconnect.",
        }
    }
}

#[derive(Debug, Serialize, PartialEq)]
pub struct Status {
    pub version: String,
    pub healthy: bool,
}

/// Installed engine: `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app\respected-orchestrator.exe` (PRODUCT_CONTRACT §2).
/// `RESPECTED_APP_DIR` is the contract's test/dev override for the program folder.
pub fn discover(app_dir: Option<PathBuf>, local_app_data: Option<PathBuf>) -> Result<Launch, ConnectError> {
    let dir = app_dir.or_else(|| local_app_data.map(|p| p.join("Respected").join("RespectedOrchestrator").join("app")));
    let exe = dir.map(|d| d.join("respected-orchestrator.exe"));
    match exe {
        Some(p) if p.is_file() => Ok(Launch { program: p, args: vec!["_ipc".into()], env: vec![] }),
        Some(p) => Err(ConnectError::NotInstalled(p.display().to_string())),
        None => Err(ConnectError::NotInstalled("no program folder".into())),
    }
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
        assert!(matches!(discover(Some(dir), None), Err(ConnectError::NotInstalled(_))));
        assert!(matches!(discover(None, None), Err(ConnectError::NotInstalled(_))));
        assert!(matches!(Connection::connect(&Launch { program: "definitely-not-an-engine.exe".into(), args: vec![], env: vec![] }), Err(ConnectError::NotInstalled(_))));
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
