use tauri::Url;

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
