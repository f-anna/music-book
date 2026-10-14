use tauri::{
    Runtime,
    plugin::{Builder, TauriPlugin},
};

mod commands;
mod models;

pub use models::*;

/// Initializes the plugin, loads the commands and returns a `TauriPlugin` instance.
pub fn init<R: Runtime>() -> TauriPlugin<R> {
    Builder::new("soundtrack")
        .invoke_handler(tauri::generate_handler![commands::report_location])
        .build()
}
