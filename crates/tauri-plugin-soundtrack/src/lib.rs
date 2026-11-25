use std::sync::{Arc, Mutex};

use tauri::{
    Manager, Runtime,
    plugin::{Builder, TauriPlugin},
};

mod analysis;
mod commands;
mod epub;
mod models;
mod store;
mod worker;

pub use models::*;

use analysis::LlamaCppAnalyzer;
use store::Store;
use worker::Worker;

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

            let db_path = app.path().app_data_dir()?.join("soundtrack").join("soundtrack.db");
            let store = match Store::open(&db_path) {
                Ok(store) => {
                    eprintln!("[soundtrack] analysis cache: {}", db_path.display());
                    store
                }
                Err(e) => {
                    eprintln!("[soundtrack] cannot open {}: {e}; analyses are not kept", db_path.display());
                    Store::in_memory()?
                }
            };
            let analyzer = LlamaCppAnalyzer::from_env()?;
            app.manage(Worker::spawn(store, Box::new(analyzer)));
            Ok(())
        })
        .build()
}
