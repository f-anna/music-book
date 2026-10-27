use std::sync::{Arc, Mutex};

use tauri::{
    Manager, Runtime,
    plugin::{Builder, TauriPlugin},
};

mod commands;
mod epub;
mod models;

pub use models::*;

/// The state shared by the commands.
#[derive(Default)]
pub(crate) struct Session {
    book: Option<Arc<epub::Book>>,
    /// The last location reported before its book was loaded; handled once `open_book` finishes.
    pending_location: Option<LocationEvent>,
    /// Incremented by `close_book`, so that an `open_book` still in progress does not reopen the book.
    generation: u64,
}

/// Initializes the plugin, loads the commands and returns a `TauriPlugin` instance.
pub fn init<R: Runtime>() -> TauriPlugin<R> {
    Builder::new("soundtrack")
        .invoke_handler(tauri::generate_handler![
            commands::open_book,
            commands::close_book,
            commands::report_location
        ])
        .setup(|app, _api| {
            app.manage(Mutex::new(Session::default()));
            Ok(())
        })
        .build()
}
