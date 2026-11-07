fn main() {
    // Test executables (the mock runtime used by the ACL test) need the common-controls v6 manifest the real app gets from tauri-build.
    // Only test targets get it, so the app's own manifest is untouched.
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") && std::env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc") {
        let manifest = std::path::Path::new(&std::env::var("CARGO_MANIFEST_DIR").unwrap()).join("test-controls.manifest");
        println!("cargo::rustc-link-arg-tests=/MANIFEST:EMBED");
        println!("cargo::rustc-link-arg-tests=/MANIFESTINPUT:{}", manifest.display());
        println!("cargo::rerun-if-changed=test-controls.manifest");
    }
    // Every app command is listed here, so the ACL applies to them like it does to plugin commands: a window may call a command only when a
    // capability grants it. `capabilities/default.json` grants these to the window "main" and to nothing else.
    tauri_build::try_build(
        tauri_build::Attributes::new().app_manifest(
            tauri_build::AppManifest::new().commands(&["engine_status", "confirm_close", "request_apply", "capability_inventory", "session_call", "preview_open"]),
        ),
    )
    .expect("tauri build")
}
