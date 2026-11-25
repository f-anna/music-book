// SQLite cache of the segment analyses, in its own file (not the reader's database).
// Pure Rust module

use std::error::Error;
use std::path::Path;
use std::time::Duration;

use rusqlite::{Connection, OptionalExtension, params};

use crate::analysis::prompt::PROMPT_VERSION;
use crate::epub::{SEGMENTER_VERSION, Segment};
use crate::models::MoodAnalysis;

const SCHEMA: &str = "
CREATE TABLE IF NOT EXISTS segment_analysis (
    book_hash         TEXT    NOT NULL,
    seg_index         INTEGER NOT NULL,
    segmenter_version INTEGER NOT NULL,
    model_id          TEXT    NOT NULL,
    prompt_version    INTEGER NOT NULL,
    section_index     INTEGER NOT NULL,
    start_offset      INTEGER NOT NULL,  -- byte offsets in the section text (epub.rs)
    end_offset        INTEGER NOT NULL,
    analysis_json     TEXT    NOT NULL,
    elapsed_ms        INTEGER NOT NULL,
    created_at        TEXT    NOT NULL,
    PRIMARY KEY (book_hash, seg_index, segmenter_version, model_id, prompt_version)
);";

/// The segmenter and prompt versions are added by the store itself.
pub struct Key<'a> {
    pub book_hash: &'a str,
    pub seg_index: usize,
    pub model_id: &'a str,
}

pub struct Store {
    conn: Connection,
}

impl Store {
    pub fn open(path: &Path) -> Result<Self, Box<dyn Error + Send + Sync>> {
        if let Some(dir) = path.parent() {
            std::fs::create_dir_all(dir)?;
        }
        Ok(Self::init(Connection::open(path)?)?)
    }

    /// Fallback when the file cannot be opened: analyses still work, but are not kept.
    pub fn in_memory() -> rusqlite::Result<Self> {
        Self::init(Connection::open_in_memory()?)
    }

    fn init(conn: Connection) -> rusqlite::Result<Self> {
        conn.execute_batch(SCHEMA)?;
        Ok(Store { conn })
    }

    pub fn get(&self, key: &Key) -> rusqlite::Result<Option<MoodAnalysis>> {
        let json: Option<String> = self
            .conn
            .query_row(
                "SELECT analysis_json FROM segment_analysis
                 WHERE book_hash = ?1 AND seg_index = ?2 AND segmenter_version = ?3
                   AND model_id = ?4 AND prompt_version = ?5",
                params![key.book_hash, key.seg_index as i64, SEGMENTER_VERSION, key.model_id, PROMPT_VERSION],
                |row| row.get(0),
            )
            .optional()?;
        // A row that no longer parses (e.g. after a tag was removed) counts as a miss.
        Ok(json.and_then(|j| serde_json::from_str(&j).ok()))
    }

    pub fn put(&self, key: &Key, segment: &Segment, analysis: &MoodAnalysis, elapsed: Duration) -> rusqlite::Result<()> {
        let json = serde_json::to_string(analysis).expect("MoodAnalysis serializes");
        self.conn.execute(
            "INSERT OR REPLACE INTO segment_analysis VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, datetime('now'))",
            params![
                key.book_hash,
                key.seg_index as i64,
                SEGMENTER_VERSION,
                key.model_id,
                PROMPT_VERSION,
                segment.section_index as i64,
                segment.start as i64,
                segment.end as i64,
                json,
                elapsed.as_millis() as i64,
            ],
        )?;
        Ok(())
    }
}
