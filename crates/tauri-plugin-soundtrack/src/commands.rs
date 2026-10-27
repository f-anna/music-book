// Slim forwarding to the inner modules (besides `lib.rs`, only here can be `tauri`).

use std::sync::{Arc, Mutex};

use tauri::{
    AppHandle, Manager, Runtime, State, command,
    ipc::{InvokeBody, Request},
};

use crate::Session;
use crate::epub::{self, Book};
use crate::models::LocationEvent;

/// Receives the EPUB as a raw body, and returns its id (the same as the adapter's `bookId`).
#[command]
pub(crate) async fn open_book<R: Runtime>(
    app: AppHandle<R>,
    session: State<'_, Mutex<Session>>,
    request: Request<'_>,
) -> Result<String, String> {
    let InvokeBody::Raw(bytes) = request.body() else {
        return Err("open_book expects the EPUB bytes as a raw body".into());
    };
    let bytes = bytes.clone();
    let cache_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| e.to_string())?
        .join("soundtrack")
        .join("books");
    let generation = session.lock().unwrap().generation;

    let book = tauri::async_runtime::spawn_blocking(move || {
        let id = epub::content_id(&bytes);
        let path = cache_dir.join(format!("{id}.epub"));
        if !path.exists() {
            if let Err(e) = std::fs::create_dir_all(&cache_dir).and_then(|_| std::fs::write(&path, &bytes)) {
                eprintln!("[soundtrack] could not cache {}: {e}", path.display());
            }
        }
        Book::open(id, bytes)
    })
    .await
    .map_err(|e| e.to_string())??;

    let words: usize = book.segments.iter().map(|s| s.words).sum();
    eprintln!(
        "[soundtrack] book opened book={} sections={} segments={} words={}",
        short_id(&book.id),
        book.sections.len(),
        book.segments.len(),
        words,
    );

    let book = Arc::new(book);
    let pending = {
        let mut session = session.lock().unwrap();
        if session.generation != generation {
            return Err("book closed while opening".into());
        }
        session.book = Some(book.clone());
        session.pending_location.take().filter(|l| l.locator.book_id == book.id)
    };
    if let Some(location) = pending {
        print_segment(&book, &location);
    }
    Ok(book.id.clone())
}

#[command]
pub(crate) fn close_book(session: State<'_, Mutex<Session>>) {
    let mut session = session.lock().unwrap();
    *session = Session {
        generation: session.generation + 1,
        ..Session::default()
    };
}

#[command]
pub(crate) fn report_location(session: State<'_, Mutex<Session>>, location: LocationEvent) {
    print_location(&location);
    let book = {
        let mut session = session.lock().unwrap();
        let book = session.book.clone().filter(|b| b.id == location.locator.book_id);
        if book.is_none() {
            session.pending_location = Some(location.clone());
        }
        book
    };
    if let Some(book) = book {
        print_segment(&book, &location);
    }
}

fn print_location(location: &LocationEvent) {
    let LocationEvent {
        locator,
        chapter_title,
        is_jump,
        ..
    } = location;
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
        short_id(&locator.book_id),
        locator.section_index,
        locator.href,
        locator.progression,
        locator.total_progression,
        is_jump,
        chapter_title,
        highlight,
    );
}

fn print_segment(book: &Book, location: &LocationEvent) {
    let locator = &location.locator;
    let section_index = locator.section_index as usize;
    if let Some(section) = book.sections.get(section_index).filter(|s| s.href != locator.href) {
        eprintln!(
            "[soundtrack] WARNING section {section_index} is {} here, but {} in the reader",
            section.href, locator.href
        );
    }
    let highlight = locator.text.as_ref().and_then(|t| t.highlight.as_deref());
    let Some(position) = book.locate(section_index, highlight, locator.progression) else {
        eprintln!("[soundtrack] segment none (section {section_index} has no text)");
        return;
    };
    let segment = &book.segments[position.segment];
    let preview: String = book.segment_text(segment).chars().take(80).collect();
    eprintln!(
        "[soundtrack] segment #{} section={} offset={} words={} via={:?} text={:?}",
        segment.index, segment.section_index, position.offset, segment.words, position.method, preview,
    );
}

fn short_id(id: &str) -> &str {
    &id[..id.len().min(12)]
}
