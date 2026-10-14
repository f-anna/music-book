# tauri-plugin-soundtrack

The backend of the Music Book as a Tauri v2 plugin. The JS API (`tauri-plugin-soundtrack-api`) loads directly from `guest-js/index.ts` without a build step.


Binding to the host app:

- `Cargo.toml`: `tauri-plugin-soundtrack = { path = ".../crates/tauri-plugin-soundtrack" }`
- `lib.rs`: `.plugin(tauri_plugin_soundtrack::init())`
- capabilities: `"soundtrack:default"`
- `package.json`: `"tauri-plugin-soundtrack-api": "file:.../crates/tauri-plugin-soundtrack"`, and in the Vite config `resolve.dedupe: ["@tauri-apps/api"]`
