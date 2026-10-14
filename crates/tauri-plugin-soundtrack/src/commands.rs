// Slim forwarding to the inner modules (besides `lib.rs`, only here can be `tauri`).

use tauri::command;

use crate::models::LocationEvent;

#[command]
pub(crate) fn report_location(location: LocationEvent) {
    let LocationEvent {
        locator,
        chapter_title,
        is_jump,
        ..
    } = &location;
    let highlight: String = locator
        .text
        .as_ref()
        .and_then(|t| t.highlight.as_deref())
        .unwrap_or_default()
        .chars()
        .take(60)
        .collect();
    eprintln!(
        "[soundtrack] location book={} section={} href={} progression={:.3} total={:?} jump={} chapter={:?} text={:?}",
        &locator.book_id[..locator.book_id.len().min(12)],
        locator.section_index,
        locator.href,
        locator.progression,
        locator.total_progression,
        is_jump,
        chapter_title,
        highlight,
    );
}
