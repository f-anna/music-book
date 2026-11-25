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

/// Mood tags, a closed list so that they map deterministically to stems.
/// Provisional: the final list comes together with the music mapping (milestone 4).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Tag {
    Calm,
    Cheerful,
    Humorous,
    Tender,
    Melancholic,
    Grief,
    Solemn,
    Mysterious,
    Ominous,
    Fear,
    Suspense,
    Anger,
    Violence,
    Chaos,
    Triumph,
    Contemplative,
}

impl Tag {
    pub const ALL: [Tag; 16] = [
        Tag::Calm, Tag::Cheerful, Tag::Humorous, Tag::Tender, Tag::Melancholic, Tag::Grief,
        Tag::Solemn, Tag::Mysterious, Tag::Ominous, Tag::Fear, Tag::Suspense, Tag::Anger,
        Tag::Violence, Tag::Chaos, Tag::Triumph, Tag::Contemplative,
    ];

    pub fn name(self) -> &'static str {
        match self {
            Tag::Calm => "calm",
            Tag::Cheerful => "cheerful",
            Tag::Humorous => "humorous",
            Tag::Tender => "tender",
            Tag::Melancholic => "melancholic",
            Tag::Grief => "grief",
            Tag::Solemn => "solemn",
            Tag::Mysterious => "mysterious",
            Tag::Ominous => "ominous",
            Tag::Fear => "fear",
            Tag::Suspense => "suspense",
            Tag::Anger => "anger",
            Tag::Violence => "violence",
            Tag::Chaos => "chaos",
            Tag::Triumph => "triumph",
            Tag::Contemplative => "contemplative",
        }
    }

    /// The one-line definition shown to the model in the prompt.
    pub fn definition(self) -> &'static str {
        match self {
            Tag::Calm => "peaceful, nothing is happening",
            Tag::Cheerful => "light, happy, good spirits",
            Tag::Humorous => "comic, ironic, playful",
            Tag::Tender => "affection, friendship, intimacy",
            Tag::Melancholic => "wistful sadness, longing",
            Tag::Grief => "loss, mourning, death of someone close",
            Tag::Solemn => "grave, dignified, religious or ceremonial",
            Tag::Mysterious => "the unknown, enigma, the uncanny; not merely dark",
            Tag::Ominous => "foreboding, a sense that something bad will happen",
            Tag::Fear => "characters are afraid, terror",
            Tag::Suspense => "uncertain outcome, the reader holds their breath",
            Tag::Anger => "rage, defiance, hostility",
            Tag::Violence => "physical struggle, killing, injury",
            Tag::Chaos => "confusion, disorder, things falling apart",
            Tag::Triumph => "victory, exultation, pride",
            Tag::Contemplative => "reflection, philosophy, inner thought",
        }
    }
}

/// The analyzer's answer for one segment, on the 1..=5 scales of the prompt.
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct MoodAnalysis {
    /// Short reason, for debugging and the thesis; the model writes it before the scores.
    pub rationale: String,
    pub valence: u8,
    pub arousal: u8,
    pub tension: u8,
    pub tags: Vec<Tag>,
}

impl MoodAnalysis {
    /// llama.cpp enforces the schema's enums but not every bound, so the backend checks again.
    pub fn validate(&self) -> Result<(), String> {
        for (name, value) in [("valence", self.valence), ("arousal", self.arousal), ("tension", self.tension)] {
            if !(1..=5).contains(&value) {
                return Err(format!("{name} out of range: {value}"));
            }
        }
        if !(1..=3).contains(&self.tags.len()) {
            return Err(format!("expected 1-3 tags, got {}", self.tags.len()));
        }
        Ok(())
    }
}

/// The reader-independent mood, the input of the music side (principle 4).
#[derive(Debug, Clone, Serialize)]
pub struct MoodVector {
    /// -1..1
    pub valence: f32,
    /// 0..1
    pub arousal: f32,
    /// 0..1
    pub tension: f32,
    pub tags: Vec<Tag>,
    /// 1 for a valid analysis, 0 for the neutral fallback.
    pub confidence: f32,
}

impl MoodVector {
    /// Used when there is no valid analysis.
    pub fn neutral() -> Self {
        MoodVector { valence: 0.0, arousal: 0.5, tension: 0.5, tags: Vec::new(), confidence: 0.0 }
    }
}

impl From<&MoodAnalysis> for MoodVector {
    fn from(a: &MoodAnalysis) -> Self {
        MoodVector {
            valence: (f32::from(a.valence) - 3.0) / 2.0,
            arousal: (f32::from(a.arousal) - 1.0) / 4.0,
            tension: (f32::from(a.tension) - 1.0) / 4.0,
            tags: a.tags.clone(),
            confidence: 1.0,
        }
    }
}
