// The prompt and the answer schema, as tuned in eval/qwen3-llamacpp/RESULTS.md (4th version).
// Pure Rust module

use serde::Serialize;

use crate::models::Tag;

/// Part of the cache key: bump it whenever the prompt or the schema changes.
pub const PROMPT_VERSION: u32 = 4;

pub fn system_prompt() -> String {
    let mut prompt = String::from(concat!(
        "You rate the mood of a passage from a novel, to drive adaptive background music. ",
        "Judge the emotional atmosphere the reader experiences, not the plot. ",
        "Rate each scale with an integer from 1 to 5:\n",
        "valence: 1 = grief, despair, horror; 2 = sad, gloomy, unpleasant; 3 = neutral or mixed; ",
        "4 = pleasant, warm, affectionate, amusing; 5 = joyful, elated.\n",
        "arousal: 1 = still, sleepy; 2 = quiet, reflective; 3 = moderate activity; ",
        "4 = lively, agitated; 5 = frantic, violent action.\n",
        "tension: 1 = relaxed, safe; 2 = slight unease; 3 = noticeable suspense; ",
        "4 = strong suspense or threat; 5 = extreme danger, climax.\n",
        "Calibration: most passages of a novel sit in the middle of the scales (2-4). ",
        "Use 1 or 5 only when the passage clearly and strongly calls for it, ",
        "and rate each scale independently of the others.\n",
        "tags: the 1-3 tags that best describe the dominant feeling, from this list only:\n",
    ));
    for tag in Tag::ALL {
        prompt += &format!("- {}: {}\n", tag.name(), tag.definition());
    }
    prompt += "rationale: one sentence of at most 20 words. Answer with JSON only.";
    prompt
}

/// The JSON schema of the answer. Structs instead of a `serde_json::Value`, because the
/// grammar follows the property order, and `rationale` must come first.
#[derive(Serialize)]
pub struct ResponseSchema {
    r#type: &'static str,
    properties: Properties,
    required: [&'static str; 5],
    #[serde(rename = "additionalProperties")]
    additional_properties: bool,
}

#[derive(Serialize)]
struct Properties {
    rationale: Text,
    valence: Scale,
    arousal: Scale,
    tension: Scale,
    tags: Tags,
}

#[derive(Serialize)]
struct Text {
    r#type: &'static str,
    #[serde(rename = "maxLength")]
    max_length: u32,
}

#[derive(Serialize)]
struct Scale {
    r#enum: [u8; 5],
}

#[derive(Serialize)]
struct Tags {
    r#type: &'static str,
    items: TagItems,
    #[serde(rename = "minItems")]
    min_items: u8,
    #[serde(rename = "maxItems")]
    max_items: u8,
}

#[derive(Serialize)]
struct TagItems {
    r#enum: [Tag; 16],
}

pub fn response_schema() -> ResponseSchema {
    let scale = || Scale { r#enum: [1, 2, 3, 4, 5] };
    ResponseSchema {
        r#type: "object",
        properties: Properties {
            rationale: Text { r#type: "string", max_length: 400 },
            valence: scale(),
            arousal: scale(),
            tension: scale(),
            tags: Tags { r#type: "array", items: TagItems { r#enum: Tag::ALL }, min_items: 1, max_items: 3 },
        },
        required: ["rationale", "valence", "arousal", "tension", "tags"],
        additional_properties: false,
    }
}
