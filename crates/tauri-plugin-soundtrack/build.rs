const COMMANDS: &[&str] = &["report_location"];

fn main() {
    tauri_plugin::Builder::new(COMMANDS).build();
}
