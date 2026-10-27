const COMMANDS: &[&str] = &["open_book", "close_book", "report_location"];

fn main() {
    tauri_plugin::Builder::new(COMMANDS).build();
}
