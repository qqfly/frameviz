fn main() {
    // Ensure the web viewer dist directory exists so that include_dir!() in
    // main.rs does not panic.  In dev mode the directory may be empty because
    // assets are served via the HTTP dev server; the full dist is populated by
    // prepare_web_viewer_dist.mjs during release builds.
    let dist = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../packages/frameviz-web-viewer/dist");
    if !dist.exists() {
        std::fs::create_dir_all(&dist).expect("failed to create web-viewer dist dir");
    }

    tauri_build::build()
}
