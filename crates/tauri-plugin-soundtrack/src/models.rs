// Reader-independent types, the counterparts of `packages/adapter-foliate/src/types.ts`.
// Pure Rust module

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TextContext {
    /// begining of the visible text: the backend uses this to find the exact position.
    pub highlight: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Locator {
    /// SHA-256 hash of the book content (hex).
    pub book_id: String,
    /// identifies the spine element (the file path within the book).
    pub href: String,
    /// Spine index.
    pub section_index: u32,
    /// 0..1 within the spine element (approximate).
    pub progression: f64,
    /// 0..1 within the whole book (approximate).
    pub total_progression: Option<f64>,
    pub text: Option<TextContext>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LocationEvent {
    pub locator: Locator,
    pub chapter_title: Option<String>,
    /// True if the location change was a jump (TOC, link, search), not a simple page turn.
    pub is_jump: bool,
    /// The whole visible text; only for checking / debugging.
    pub visible_text: Option<String>,
}
