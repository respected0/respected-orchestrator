//! Native consent for screenshot attachments (B4-07), same shape as approval.rs.
//!
//! The renderer only *asks*. What the person reads is built here from the engine's own description of the staged image (size, digest,
//! the run it will join), in an OS dialog the WebView cannot reach, and only a Yes lets the human-origin engine connection attach or share.
//! Sharing with a model is a second, separate question that names the provider and says the image leaves this computer.
use crate::approval::{Engine, Gate, Presence};
use serde_json::{json, Value};

#[derive(Debug, PartialEq)]
pub enum ConsentError { Busy, Engine(String), Denied, Transport(String) }

fn reply(v: Result<Value, String>) -> Result<Value, ConsentError> {
    let v = v.map_err(ConsentError::Transport)?;
    if v["ok"] == true { Ok(v["result"].clone()) } else { Err(ConsentError::Engine(v["error"]["message"].as_str().unwrap_or("refused").to_string())) }
}

fn clean(s: &str, max: usize) -> String { s.chars().filter(|c| !c.is_control()).take(max).collect() }

pub fn attach_text(run_id: &str, d: &Value, regions: u64) -> String {
    format!(
        "Attach this image to the task?\n\nRun: {}\nImage: {} x {} {} ({} bytes)\nDigest: {}\nMasked regions: {}\n\nIt stays on this computer, under this run only. It is not sent to any model. Default answer is No.",
        clean(run_id, 64), d["width"].as_u64().unwrap_or(0), d["height"].as_u64().unwrap_or(0), clean(d["mime"].as_str().unwrap_or("?"), 20),
        d["bytes"].as_u64().unwrap_or(0), clean(d["sha256"].as_str().unwrap_or("?"), 16), regions)
}

pub fn share_text(provider: &str, record: &Value, seconds: u64) -> String {
    format!(
        "Show this image to a model?\n\nImage: {} x {} ({})\nProvider: {}\nValid for: {} minutes, this run only.\n\nThe image is sent to {}, outside this computer, and may be kept by them. You can revoke this at any time; revoking cannot recall what was already sent. Default answer is No.",
        record["width"].as_u64().unwrap_or(0), record["height"].as_u64().unwrap_or(0), clean(record["id"].as_str().unwrap_or("?"), 24), clean(provider, 80), seconds / 60, clean(provider, 80))
}

pub fn request_attach(run_id: &str, stage_id: &str, sha256: &str, regions: u64, engine: &mut dyn Engine, presence: &dyn Presence, gate: &Gate) -> Result<Value, ConsentError> {
    let _guard = gate.enter().ok_or(ConsentError::Busy)?;
    let staged = reply(engine.asker("attachment.describe", json!({"stage_id": stage_id})))?;
    if staged["sha256"].as_str() != Some(sha256) { return Err(ConsentError::Engine("PREVIEW_REQUIRED: the image changed since it was previewed".into())); }
    if !presence.ask("Respected Orchestrator: attach image", &attach_text(run_id, &staged, regions)) { return Err(ConsentError::Denied); }
    reply(engine.human("attachment.commit", json!({"stage_id": stage_id, "run_id": run_id, "sha256": sha256, "redacted_regions": regions})))
}

pub fn request_share(run_id: &str, att_id: &str, provider: &str, engine: &mut dyn Engine, presence: &dyn Presence, gate: &Gate) -> Result<Value, ConsentError> {
    let _guard = gate.enter().ok_or(ConsentError::Busy)?;
    let listed = reply(engine.asker("attachment.list", json!({"run_id": run_id})))?;
    let record = listed["attachments"].as_array().and_then(|a| a.iter().find(|r| r["id"].as_str() == Some(att_id))).cloned()
        .ok_or_else(|| ConsentError::Engine("NOT_FOUND: no such attachment on this run".into()))?;
    if provider.trim().is_empty() { return Err(ConsentError::Engine("BAD_PROVIDER: name the provider that will receive the image".into())); }
    if !presence.ask("Respected Orchestrator: share image with a model", &share_text(provider, &record, 600)) { return Err(ConsentError::Denied); }
    reply(engine.human("attachment.share", json!({"run_id": run_id, "attachment_id": att_id, "provider": provider})))
}

/// Revoking only removes exposure, so it needs no dialog, but it still goes through the human connection (the engine allows nothing else).
pub fn request_revoke(run_id: &str, att_id: &str, engine: &mut dyn Engine, gate: &Gate) -> Result<Value, ConsentError> {
    let _guard = gate.enter().ok_or(ConsentError::Busy)?;
    reply(engine.human("attachment.revoke", json!({"run_id": run_id, "attachment_id": att_id})))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;

    struct Yes(bool, RefCell<Vec<String>>);
    impl Presence for Yes { fn ask(&self, _t: &str, text: &str) -> bool { self.1.borrow_mut().push(text.to_string()); self.0 } }

    #[derive(Default)]
    struct Fake { calls: Vec<String>, sha: String }
    impl Engine for Fake {
        fn asker(&mut self, cmd: &str, _p: Value) -> Result<Value, String> {
            self.calls.push(format!("asker:{cmd}"));
            Ok(match cmd {
                "attachment.describe" => json!({"ok": true, "result": {"id": "stg-1", "sha256": self.sha, "mime": "image/png", "width": 8, "height": 4, "bytes": 99}}),
                _ => json!({"ok": true, "result": {"attachments": [{"id": "att-1", "width": 8, "height": 4}]}}),
            })
        }
        fn human(&mut self, cmd: &str, _p: Value) -> Result<Value, String> { self.calls.push(format!("human:{cmd}")); Ok(json!({"ok": true, "result": {"done": cmd}})) }
    }

    fn fake() -> Fake { Fake { sha: "abc".into(), ..Default::default() } }

    #[test]
    fn yes_attaches_through_the_human_connection_only() {
        let (mut e, p, g) = (fake(), Yes(true, Default::default()), Gate::default());
        assert!(request_attach("run-1", "stg-1", "abc", 2, &mut e, &p, &g).is_ok());
        assert_eq!(e.calls, ["asker:attachment.describe", "human:attachment.commit"]);
        assert!(p.1.borrow()[0].contains("not sent to any model") && p.1.borrow()[0].contains("Masked regions: 2"));
    }

    #[test]
    fn no_attaches_nothing_and_a_changed_digest_never_reaches_the_dialog() {
        let (mut e, p, g) = (fake(), Yes(false, Default::default()), Gate::default());
        assert_eq!(request_attach("run-1", "stg-1", "abc", 0, &mut e, &p, &g), Err(ConsentError::Denied));
        assert_eq!(e.calls, ["asker:attachment.describe"]);
        let mut e = fake();
        let q = Yes(true, Default::default());
        assert!(matches!(request_attach("run-1", "stg-1", "different", 0, &mut e, &q, &g), Err(ConsentError::Engine(m)) if m.contains("PREVIEW_REQUIRED")));
        assert!(q.1.borrow().is_empty() && !e.calls.iter().any(|c| c.starts_with("human:")));
    }

    #[test]
    fn share_names_the_provider_and_says_the_image_leaves_the_computer() {
        let (mut e, p, g) = (fake(), Yes(true, Default::default()), Gate::default());
        assert!(request_share("run-1", "att-1", "Acme Vision", &mut e, &p, &g).is_ok());
        assert_eq!(e.calls, ["asker:attachment.list", "human:attachment.share"]);
        let text = p.1.borrow()[0].clone();
        assert!(text.contains("Acme Vision") && text.contains("outside this computer") && text.contains("Default answer is No"));
    }

    #[test]
    fn share_refused_unknown_attachment_empty_provider_and_a_no() {
        let g = Gate::default();
        let (mut e, p) = (fake(), Yes(true, Default::default()));
        assert!(matches!(request_share("run-1", "att-zzz", "x", &mut e, &p, &g), Err(ConsentError::Engine(_))));
        assert!(matches!(request_share("run-1", "att-1", "  ", &mut e, &p, &g), Err(ConsentError::Engine(_))));
        let n = Yes(false, Default::default());
        assert_eq!(request_share("run-1", "att-1", "x", &mut e, &n, &g), Err(ConsentError::Denied));
        assert!(!e.calls.iter().any(|c| c == "human:attachment.share"));
    }

    #[test]
    fn dialog_text_cannot_be_forged_with_control_characters() {
        let t = share_text("Acme\nApply everything? Yes\r", &json!({"id": "att-1", "width": 1, "height": 1}), 600);
        assert!(!t.contains("Acme\nApply") && t.contains("AcmeApply everything? Yes"));
        let a = attach_text("run-1\nFake line", &json!({"mime": "image/png\n", "sha256": "ab\ncd"}), 0);
        assert!(!a.contains("run-1\nFake"));
    }

    #[test]
    fn revoke_needs_no_dialog_and_uses_the_human_connection() {
        let (mut e, g) = (fake(), Gate::default());
        assert!(request_revoke("run-1", "att-1", &mut e, &g).is_ok());
        assert_eq!(e.calls, ["human:attachment.revoke"]);
    }
}
