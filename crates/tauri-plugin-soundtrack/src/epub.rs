// Opening the EPUB, text extraction, segmentation and Locator → segment mapping.
// Pure Rust module

use std::io::Cursor;
use std::ops::Range;

use ego_tree::NodeRef;
use rbook::Epub;
use scraper::{Html, Node, Selector};
use sha2::{Digest, Sha256};

/// Segment size in words. Segments are cut only at paragraph boundaries, so these are soft limits.
const MIN_WORDS: usize = 300;
const MAX_WORDS: usize = 800;
/// A heading starts a new segment only if the current one has at least this many words.
const MIN_WORDS_BEFORE_HEADING: usize = 100;

const HEADING_ELEMENTS: &[&str] = &["h1", "h2", "h3", "h4", "h5", "h6"];
const BLOCK_ELEMENTS: &[&str] = &[
    "p", "div", "li", "blockquote", "pre", "dt", "dd", "td", "th", "tr", "table",
    "figcaption", "section", "article", "header", "footer", "aside", "br", "hr",
];

pub struct Book {
    /// SHA-256 of the file content (hex), the same as the adapter's `bookId`.
    pub id: String,
    /// One per spine item, indexed the same way as the Foliate `book.sections`.
    pub sections: Vec<Section>,
    pub segments: Vec<Segment>,
}

pub struct Section {
    /// Path within the EPUB, like the Foliate `book.sections[i].id` (decoded, no leading `/`).
    pub href: String,
    /// The paragraphs with collapsed whitespace, joined by a single space.
    pub text: String,
    /// The segments of this section, as a range of `Book::segments`.
    pub segments: Range<usize>,
}

pub struct Segment {
    pub index: usize,
    pub section_index: usize,
    /// Byte offsets into `Section::text`.
    pub start: usize,
    pub end: usize,
    pub words: usize,
}

/// How the position within the section was found.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Method {
    Exact,
    IgnoringWhitespace,
    Progression,
}

#[derive(Debug, Clone, Copy)]
pub struct Position {
    pub segment: usize,
    /// Byte offset into the section text.
    pub offset: usize,
    pub method: Method,
}

struct Paragraph {
    text: String,
    words: usize,
    heading: bool,
}

pub fn content_id(bytes: &[u8]) -> String {
    Sha256::digest(bytes).iter().map(|b| format!("{b:02x}")).collect()
}

impl Book {
    pub fn open(id: String, bytes: Vec<u8>) -> Result<Self, String> {
        let epub = Epub::read(Cursor::new(bytes)).map_err(|e| format!("cannot read EPUB: {e}"))?;
        let mut sections = Vec::new();
        let mut segments = Vec::new();

        // Every spine item gets an index, `linear="no"` ones too; like Foliate, only the ones
        // missing from the manifest are skipped. Otherwise `Locator.sectionIndex` would shift.
        for entry in epub.spine().iter() {
            let Some(item) = entry.manifest_entry() else { continue };
            let section_index = sections.len();
            // An unreadable or non-HTML item (e.g. an SVG cover) is an empty section, not an error.
            let paragraphs = if item.kind().subtype().contains("html") {
                epub.read_resource_str(item.href())
                    .map(|html| extract_paragraphs(&html))
                    .unwrap_or_default()
            } else {
                Vec::new()
            };

            let (text, ranges) = segment_paragraphs(&paragraphs);
            let first = segments.len();
            segments.extend(ranges.into_iter().enumerate().map(|(i, (start, end, words))| Segment {
                index: first + i,
                section_index,
                start,
                end,
                words,
            }));
            sections.push(Section {
                href: item.href().decode().trim_start_matches('/').to_string(),
                text,
                segments: first..segments.len(),
            });
        }
        Ok(Book { id, sections, segments })
    }

    pub fn segment_text(&self, segment: &Segment) -> &str {
        &self.sections[segment.section_index].text[segment.start..segment.end]
    }

    /// Finds the segment for a reader position. The visible text (`highlight`) gives the exact
    /// offset; `progression` comes from page numbers, so it is only the fallback and the tiebreaker.
    pub fn locate(&self, section_index: usize, highlight: Option<&str>, progression: f64) -> Option<Position> {
        let section = self.sections.get(section_index)?;
        let segments = &self.segments[section.segments.clone()];
        if segments.is_empty() {
            return None;
        }
        let text = &section.text;
        let estimate = floor_char_boundary(text, (progression.clamp(0.0, 1.0) * text.len() as f64) as usize);
        let needle = highlight.map(collapse_whitespace).filter(|h| !h.is_empty());

        let (offset, method) = needle
            .as_deref()
            .and_then(|n| closest(text.match_indices(n).map(|(i, _)| i), estimate))
            .map(|o| (o, Method::Exact))
            .or_else(|| {
                needle
                    .as_deref()
                    .and_then(|n| find_ignoring_whitespace(text, n, estimate))
                    .map(|o| (o, Method::IgnoringWhitespace))
            })
            .unwrap_or((estimate, Method::Progression));

        let i = segments.partition_point(|s| s.start <= offset).saturating_sub(1);
        Some(Position { segment: segments[i].index, offset, method })
    }
}

fn extract_paragraphs(html: &str) -> Vec<Paragraph> {
    let document = Html::parse_document(html);
    let body = Selector::parse("body").expect("valid selector");
    let mut paragraphs = Vec::new();
    if let Some(body) = document.select(&body).next() {
        let mut buf = String::new();
        collect_blocks(*body, false, &mut buf, &mut paragraphs);
        flush(&mut buf, false, &mut paragraphs);
    }
    paragraphs
}

/// Collects the text into `buf`, and closes a paragraph at every block element boundary.
fn collect_blocks(node: NodeRef<Node>, in_heading: bool, buf: &mut String, out: &mut Vec<Paragraph>) {
    for child in node.children() {
        match child.value() {
            Node::Text(text) => buf.push_str(text),
            Node::Element(e) if matches!(e.name(), "script" | "style") => {}
            Node::Element(e) => {
                // A `<br>` inside a heading still belongs to the heading.
                let heading = in_heading || HEADING_ELEMENTS.contains(&e.name());
                let block = heading || BLOCK_ELEMENTS.contains(&e.name());
                if block {
                    flush(buf, in_heading, out);
                }
                collect_blocks(child, heading, buf, out);
                if block {
                    flush(buf, heading, out);
                }
            }
            _ => {}
        }
    }
}

fn flush(buf: &mut String, heading: bool, out: &mut Vec<Paragraph>) {
    let text = collapse_whitespace(buf);
    buf.clear();
    if !text.is_empty() {
        let words = text.split(' ').count();
        out.push(Paragraph { text, words, heading });
    }
}

/// Joins the paragraphs into the section text, and groups them into segments:
/// `(start, end, words)` with byte offsets into the returned text.
fn segment_paragraphs(paragraphs: &[Paragraph]) -> (String, Vec<(usize, usize, usize)>) {
    let mut text = String::new();
    let mut bounds = Vec::with_capacity(paragraphs.len());
    for p in paragraphs {
        if !text.is_empty() {
            text.push(' ');
        }
        bounds.push((text.len(), text.len() + p.text.len()));
        text.push_str(&p.text);
    }

    // (first paragraph, end paragraph exclusive, words)
    let mut groups: Vec<(usize, usize, usize)> = Vec::new();
    let mut start = 0;
    let mut words = 0;
    for (i, p) in paragraphs.iter().enumerate() {
        let cut = i > start
            && ((p.heading && words >= MIN_WORDS_BEFORE_HEADING)
                || (words >= MIN_WORDS && words + p.words > MAX_WORDS));
        if cut {
            groups.push((start, i, words));
            start = i;
            words = 0;
        }
        words += p.words;
    }
    if start < paragraphs.len() {
        match groups.last_mut() {
            // A short tail is merged into the previous segment, unless it starts a new chapter.
            Some(last) if words < MIN_WORDS && !paragraphs[start].heading => {
                last.1 = paragraphs.len();
                last.2 += words;
            }
            _ => groups.push((start, paragraphs.len(), words)),
        }
    }

    let ranges = groups
        .into_iter()
        .map(|(first, end, words)| (bounds[first].0, bounds[end - 1].1, words))
        .collect();
    (text, ranges)
}

fn collapse_whitespace(s: &str) -> String {
    s.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// Fallback for when the reader's text has no space where ours has one (e.g. `</h2><p>`).
fn find_ignoring_whitespace(text: &str, needle: &str, estimate: usize) -> Option<usize> {
    let needle: String = needle.chars().filter(|c| !c.is_whitespace()).collect();
    if needle.is_empty() {
        return None;
    }
    let mut compact = String::with_capacity(text.len());
    // For every byte of `compact`, the offset of its character in `text`.
    let mut origin = Vec::with_capacity(text.len());
    for (i, c) in text.char_indices().filter(|(_, c)| !c.is_whitespace()) {
        compact.push(c);
        origin.extend(std::iter::repeat_n(i, c.len_utf8()));
    }
    closest(compact.match_indices(&needle).map(|(i, _)| origin[i]), estimate)
}

/// Of several matches, the one nearest to the estimated position.
fn closest(offsets: impl Iterator<Item = usize>, estimate: usize) -> Option<usize> {
    offsets.min_by_key(|&o| o.abs_diff(estimate))
}

fn floor_char_boundary(s: &str, mut i: usize) -> usize {
    i = i.min(s.len());
    while !s.is_char_boundary(i) {
        i -= 1;
    }
    i
}
