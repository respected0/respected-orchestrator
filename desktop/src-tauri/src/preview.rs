//! Local preview policy (B3-06.03). Off by default. Everything here is a decision; the window is created by `lib.rs`.
//!
//! What is allowed: one `http://127.0.0.1:<port>` or `http://[::1]:<port>` page whose port the user listed in the engine settings,
//! in its own window that has no capability file (so it has no IPC at all), no cookies or storage shared with the app (incognito),
//! and navigation that may only stay on the same origin. Test output and project pages are untrusted content: nothing in here
//! trusts what the page says or does. Anything unclear is a refusal.
use serde_json::Value;
use std::net::{Ipv4Addr, Ipv6Addr};
use tauri::Url;

pub const MAX_URL: usize = 2048;
pub const MAX_PORTS: usize = 8;
pub const OPEN_SECONDS: u64 = 600;

#[derive(Debug, PartialEq, Eq)]
pub enum Denied {
    Disabled,
    NoPorts,
    BadUrl,
    Scheme,
    Credentials,
    Host,
    NoPort,
    PortNotAllowed(u16),
}

impl Denied {
    pub fn message(&self) -> String {
        match self {
            Denied::Disabled => "Yerel önizleme kapalı. Ayarlardan açılmadıkça hiçbir sayfa gösterilmez.".into(),
            Denied::NoPorts => "Önizleme açık ama izin verilen port yok.".into(),
            Denied::BadUrl => "Adres geçersiz.".into(),
            Denied::Scheme => "Yalnızca http:// yerel adresleri açılabilir.".into(),
            Denied::Credentials => "Adreste kullanıcı adı veya parola olamaz.".into(),
            Denied::Host => "Yalnızca 127.0.0.1 ve [::1] açılabilir.".into(),
            Denied::NoPort => "Adreste açık bir port yazılmalı.".into(),
            Denied::PortNotAllowed(p) => format!("{p} portu izin listesinde yok."),
        }
    }
}

/// Same rule as the engine's settings validation: empty, or at most 8 distinct whole ports in 1024..=65535.
pub fn parse_ports(text: &str) -> Result<Vec<u16>, &'static str> {
    if text.trim().is_empty() {
        return Ok(vec![]);
    }
    let parts: Vec<&str> = text.split(',').map(str::trim).collect();
    if parts.len() > MAX_PORTS {
        return Err("too many ports");
    }
    let mut ports = Vec::new();
    for part in parts {
        if part.is_empty() || !part.bytes().all(|b| b.is_ascii_digit()) {
            return Err("not a port");
        }
        let n: u32 = part.parse().map_err(|_| "not a port")?;
        if !(1024..=65535).contains(&n) {
            return Err("port out of range");
        }
        if ports.contains(&(n as u16)) {
            return Err("duplicate port");
        }
        ports.push(n as u16);
    }
    Ok(ports)
}

#[derive(Debug, PartialEq, Eq)]
pub struct Settings {
    pub enabled: bool,
    pub ports: Vec<u16>,
}

/// From the engine's `settings.readback` reply. Fails closed: any unexpected shape means disabled with no ports.
pub fn settings_from_reply(reply: &Value) -> Settings {
    let closed = Settings { enabled: false, ports: vec![] };
    if reply["ok"] != true {
        return closed;
    }
    let s = &reply["result"]["settings"];
    let enabled = s["preview_enabled"] == true;
    if !(s["preview_ports"].is_null() || s["preview_ports"].is_string()) {
        return closed; // a wrong type is never "empty": the whole feature stays closed
    }
    match parse_ports(s["preview_ports"].as_str().unwrap_or("")) {
        Ok(ports) if enabled => Settings { enabled, ports },
        _ => closed,
    }
}

pub fn check_url(raw: &str, settings: &Settings) -> Result<Url, Denied> {
    if !settings.enabled {
        return Err(Denied::Disabled);
    }
    if settings.ports.is_empty() {
        return Err(Denied::NoPorts);
    }
    if raw.len() > MAX_URL || raw.chars().any(|c| c.is_control() || c.is_whitespace() || c == '\\' || !c.is_ascii()) {
        return Err(Denied::BadUrl);
    }
    let url = Url::parse(raw).map_err(|_| Denied::BadUrl)?;
    if url.scheme() != "http" {
        return Err(Denied::Scheme);
    }
    if !url.username().is_empty() || url.password().is_some() {
        return Err(Denied::Credentials);
    }
    let loopback = match url.host() {
        Some(url::Host::Ipv4(a)) => a == Ipv4Addr::LOCALHOST,
        Some(url::Host::Ipv6(a)) => a == Ipv6Addr::LOCALHOST,
        _ => false, // names (including "localhost") can be redirected by hosts files or DNS; only the literal loopback is trusted
    };
    if !loopback {
        return Err(Denied::Host);
    }
    let port = url.port().ok_or(Denied::NoPort)?;
    if !settings.ports.contains(&port) {
        return Err(Denied::PortNotAllowed(port));
    }
    Ok(url)
}

/// Navigation inside the preview may only stay on the origin that was opened: no redirect or link can leave it.
pub fn same_origin(opened: &Url, next: &Url) -> bool {
    opened.scheme() == next.scheme() && opened.host() == next.host() && opened.port() == next.port()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn on(ports: &[u16]) -> Settings { Settings { enabled: true, ports: ports.to_vec() } }
    fn ok(raw: &str) -> bool { check_url(raw, &on(&[5173, 3000])).is_ok() }

    #[test]
    fn off_by_default_and_every_closed_shape_refuses() {
        let off = Settings { enabled: false, ports: vec![5173] };
        assert_eq!(check_url("http://127.0.0.1:5173/", &off), Err(Denied::Disabled));
        assert_eq!(check_url("http://127.0.0.1:5173/", &on(&[])), Err(Denied::NoPorts));
        for reply in [json!(null), json!({}), json!({"ok": false}), json!({"ok": true}), json!({"ok": true, "result": {}}),
                      json!({"ok": true, "result": {"settings": {"preview_enabled": "true", "preview_ports": "5173"}}}),
                      json!({"ok": true, "result": {"settings": {"preview_enabled": true, "preview_ports": 5173}}}),
                      json!({"ok": true, "result": {"settings": {"preview_enabled": true, "preview_ports": "80"}}}),
                      json!({"ok": true, "result": {"settings": {"preview_enabled": false, "preview_ports": "5173"}}})] {
            assert_eq!(settings_from_reply(&reply), Settings { enabled: false, ports: vec![] }, "{reply}");
        }
        let good = settings_from_reply(&json!({"ok": true, "result": {"settings": {"preview_enabled": true, "preview_ports": "5173, 3000"}}}));
        assert_eq!(good, Settings { enabled: true, ports: vec![5173, 3000] });
    }

    #[test]
    fn only_listed_loopback_http_ports_open() {
        for good in ["http://127.0.0.1:5173/", "http://127.0.0.1:3000/a/b?x=1#f", "http://[::1]:5173/", "http://127.1:5173/", "http://2130706433:3000/"] {
            assert!(ok(good), "{good}");
        }
        assert_eq!(check_url("http://127.0.0.1:9999/", &on(&[5173])), Err(Denied::PortNotAllowed(9999)));
    }

    #[test]
    fn hostile_addresses_are_all_refused() {
        let cases = [
            "https://127.0.0.1:5173/", "file:///C:/Windows/win.ini", "javascript:alert(1)", "data:text/html,<script>1</script>", "ftp://127.0.0.1:5173/",
            "http://localhost:5173/", "http://LOCALHOST:5173/", "http://example.com:5173/", "http://127.0.0.1.evil.com:5173/", "http://evil.com:5173@127.0.0.1:5173/",
            "http://127.0.0.1:5173@evil.com:5173/", "http://user:pw@127.0.0.1:5173/", "http://127.0.0.1/", "http://127.0.0.1:80/", "http://127.0.0.1:5174/",
            "http://0.0.0.0:5173/", "http://192.168.1.5:5173/", "http://10.0.0.1:5173/", "http://[::ffff:127.0.0.1]:5173/", "http://127.0.0.2:5173/",
            "http://127.0.0.1:5173\\@evil.com/", "http://127.0.0.1:5173/\n", "http://127.0.0.1:5173/ x", "http://127.0.0.1:5173/\u{0}", "http://127.0.0.1:５１７３/",
            "http://１２７.0.0.1:5173/", "", "   ", "not a url", "//127.0.0.1:5173/", "http://", "http://:5173/",
        ];
        for bad in cases {
            assert!(!ok(bad), "{bad:?} must be refused");
        }
        assert!(!ok(&format!("http://127.0.0.1:5173/{}", "a".repeat(MAX_URL))));
    }

    #[test]
    fn denial_reasons_are_specific_and_readable() {
        let s = on(&[5173]);
        assert_eq!(check_url("https://127.0.0.1:5173/", &s), Err(Denied::Scheme));
        assert_eq!(check_url("http://u:p@127.0.0.1:5173/", &s), Err(Denied::Credentials));
        assert_eq!(check_url("http://localhost:5173/", &s), Err(Denied::Host));
        assert_eq!(check_url("http://127.0.0.1/", &s), Err(Denied::NoPort));
        for d in [Denied::Disabled, Denied::NoPorts, Denied::BadUrl, Denied::Scheme, Denied::Credentials, Denied::Host, Denied::NoPort, Denied::PortNotAllowed(1)] {
            assert!(d.message().len() > 8);
        }
    }

    #[test]
    fn port_lists_follow_the_engine_rule() {
        for good in ["", "  ", "3000", "3000, 5173", "1024", "65535"] { assert!(parse_ports(good).is_ok(), "{good}"); }
        for bad in ["80", "1023", "65536", "abc", "3000,", ",3000", "3000,3000", "-3000", "3000.5", "0x1f90", "3000 5173", "１２３４", "3000,3001,3002,3003,3004,3005,3006,3007,3008"] {
            assert!(parse_ports(bad).is_err(), "{bad}");
        }
    }

    #[test]
    fn navigation_cannot_leave_the_opened_origin() {
        let opened: Url = "http://127.0.0.1:5173/app".parse().unwrap();
        for good in ["http://127.0.0.1:5173/other?x=1", "http://127.0.0.1:5173/#frag"] { assert!(same_origin(&opened, &good.parse().unwrap()), "{good}"); }
        for bad in ["http://127.0.0.1:3000/", "http://[::1]:5173/", "https://127.0.0.1:5173/", "http://evil.com:5173/", "http://localhost:5173/",
                    "tauri://localhost/", "about:blank", "javascript:alert(1)", "file:///C:/x"] {
            assert!(!same_origin(&opened, &bad.parse().unwrap()), "{bad}");
        }
    }
}
