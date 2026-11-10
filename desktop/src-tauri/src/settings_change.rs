//! Settings changes asked for from the settings screen (KALAN_ISLER 4.5).
//!
//! Several settings are consent switches the WebView must not be able to flip by itself (local preview, microphone, screen capture, the
//! speech program, the acceptance command list). So the renderer can only *ask*: the engine validates the change, and what the person sees
//! is built here from the engine's own schema and stored values, in an OS dialog the WebView cannot reach. Only a Yes applies it.
use crate::approval::{Gate, Presence};
use serde_json::{json, Value};

const MAX_KEYS: usize = 40;

fn clean(v: &Value) -> String {
    let text = match v { Value::String(s) => s.clone(), Value::Null => String::new(), other => other.to_string() };
    let short: String = text.chars().filter(|c| !c.is_control()).take(120).collect();
    if short.is_empty() { "(boş)".into() } else { short }
}

/// One line per setting that really changes: the engine's label, the stored value, the new one. A secret's value is never shown.
pub fn dialog_text(schema: &Value, stored: &Value, changes: &serde_json::Map<String, Value>) -> Option<String> {
    let mut lines = Vec::new();
    for (key, new) in changes {
        let field = schema["fields"].as_array().and_then(|a| a.iter().find(|f| f["key"] == key.as_str()));
        let label = field.and_then(|f| f["label"].as_str()).unwrap_or(key);
        if field.map(|f| f["secret"] == true).unwrap_or(false) {
            lines.push(format!("  {} ({key}): gizli değer değişecek", clean(&json!(label))));
        } else if &stored[key] != new {
            lines.push(format!("  {} ({key}): {} → {}", clean(&json!(label)), clean(&stored[key]), clean(new)));
        }
    }
    if lines.is_empty() { return None; }
    Some(format!("Bu ayarlar değiştirilsin mi?\n\n{}\n\nVarsayılan yanıt Hayır'dır.", lines.join("\n")))
}

/// `call` is one request on the shell's own engine connection. The answer is data for the screen: applied, declined, unchanged, or the
/// engine's field errors. `Err` is a transport failure or an engine refusal.
pub fn request(changes: &Value, call: &mut dyn FnMut(&str, Value) -> Result<Value, String>, presence: &dyn Presence, gate: &Gate) -> Result<Value, String> {
    let map = changes.as_object().filter(|m| !m.is_empty() && m.len() <= MAX_KEYS).ok_or("Değişiklik listesi boş ya da çok uzun.")?;
    let _guard = gate.enter().ok_or("Başka bir onay penceresi açık.")?;
    let mut ask = |cmd: &str, payload: Value| -> Result<Value, String> {
        let v = call(cmd, payload)?;
        if v["ok"] == true { Ok(v["result"].clone()) } else { Err(v["error"]["message"].as_str().unwrap_or("refused").to_string()) }
    };
    let checked = ask("settings.validate", json!({"settings": changes}))?;
    if checked["valid"] != true {
        return Ok(json!({"applied": false, "errors": checked["errors"]}));
    }
    let schema = ask("settings.schema", json!({}))?;
    let stored = ask("settings.readback", json!({}))?;
    let Some(text) = dialog_text(&schema, &stored["settings"], map) else { return Ok(json!({"applied": false, "unchanged": true})); };
    if !presence.ask("Respected Orchestrator: ayar değişikliği", &text) {
        return Ok(json!({"applied": false, "declined": true}));
    }
    ask("settings.apply", json!({"settings": changes}))?;
    Ok(json!({"applied": true}))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;

    struct Say(bool, RefCell<Vec<String>>);
    impl Presence for Say {
        fn ask(&self, _t: &str, text: &str) -> bool { self.1.borrow_mut().push(text.to_string()); self.0 }
    }

    fn engine(calls: &RefCell<Vec<String>>, valid: bool) -> impl FnMut(&str, Value) -> Result<Value, String> + '_ {
        move |cmd, _payload| {
            calls.borrow_mut().push(cmd.to_string());
            let result = match cmd {
                "settings.validate" => if valid { json!({"valid": true, "errors": []}) } else { json!({"valid": false, "errors": [{"key": "preview_ports", "message": "bad"}]}) },
                "settings.schema" => json!({"fields": [{"key": "preview_enabled", "label": "Yerel önizleme", "secret": false}, {"key": "memory_token", "label": "Belirteç", "secret": true}]}),
                "settings.readback" => json!({"settings": {"preview_enabled": false, "memory_token": "***set***", "preview_ports": ""}}),
                "settings.apply" => json!({"status": "applied"}),
                _ => return Err("unexpected".into()),
            };
            Ok(json!({"ok": true, "result": result}))
        }
    }

    #[test]
    fn only_a_yes_in_the_native_dialog_applies_and_the_dialog_shows_the_engines_values() {
        let (calls, gate) = (RefCell::new(vec![]), Gate::default());
        let no = Say(false, RefCell::new(vec![]));
        let changes = json!({"preview_enabled": true, "memory_token": "sk-SECRET\u{7}VALUE"});
        assert_eq!(request(&changes, &mut engine(&calls, true), &no, &gate).unwrap(), json!({"applied": false, "declined": true}));
        assert!(!calls.borrow().contains(&"settings.apply".to_string()));
        let text = no.1.borrow()[0].clone();
        assert!(text.contains("Yerel önizleme (preview_enabled): false → true") && text.contains("gizli değer değişecek"), "{text}");
        assert!(!text.contains("SECRET"), "a secret is never shown: {text}");
        let yes = Say(true, RefCell::new(vec![]));
        assert_eq!(request(&changes, &mut engine(&calls, true), &yes, &gate).unwrap(), json!({"applied": true}));
        assert_eq!(calls.borrow().last().unwrap(), "settings.apply");
    }

    #[test]
    fn invalid_unchanged_empty_and_concurrent_requests_never_reach_the_dialog_or_the_engine_write() {
        let (calls, gate) = (RefCell::new(vec![]), Gate::default());
        let yes = Say(true, RefCell::new(vec![]));
        let bad = request(&json!({"preview_ports": "x"}), &mut engine(&calls, false), &yes, &gate).unwrap();
        assert_eq!(bad["errors"][0]["key"], "preview_ports");
        assert_eq!(request(&json!({"preview_enabled": false}), &mut engine(&calls, true), &yes, &gate).unwrap(), json!({"applied": false, "unchanged": true}));
        for nothing in [json!({}), json!([1]), json!("x"), json!(null)] { assert!(request(&nothing, &mut engine(&calls, true), &yes, &gate).is_err()); }
        let _held = gate.enter().unwrap();
        assert!(request(&json!({"preview_enabled": true}), &mut engine(&calls, true), &yes, &gate).is_err(), "one dialog at a time");
        assert!(yes.1.borrow().is_empty() && !calls.borrow().contains(&"settings.apply".to_string()));
    }
}
