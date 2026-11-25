// Mood analysis of a segment's text.
// Pure Rust module

use std::fmt;

use crate::models::MoodAnalysis;

mod llama_cpp;
pub mod prompt;

pub use llama_cpp::LlamaCppAnalyzer;

/// Blocking: an analysis takes minutes on a CPU, so it runs on the worker thread.
pub trait MoodAnalyzer: Send {
    /// Part of the cache key: results of different models are kept apart.
    fn model_id(&self) -> &str;
    fn analyze(&self, text: &str) -> Result<MoodAnalysis, AnalysisError>;
}

#[derive(Debug)]
pub enum AnalysisError {
    /// The model server is not running or still loading.
    Unavailable(String),
    Http(String),
    /// The answer does not match the schema or the ranges.
    Invalid(String),
}

impl fmt::Display for AnalysisError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AnalysisError::Unavailable(e) => write!(f, "model server unavailable: {e}"),
            AnalysisError::Http(e) => write!(f, "model server error: {e}"),
            AnalysisError::Invalid(e) => write!(f, "invalid analysis: {e}"),
        }
    }
}

impl std::error::Error for AnalysisError {}
