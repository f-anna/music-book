// MoodAnalyzer over llama.cpp's llama-server (OpenAI-compatible chat API, JSON schema).
// Pure Rust module

use std::env;
use std::time::Duration;

use reqwest::StatusCode;
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};

use super::prompt::{ResponseSchema, response_schema, system_prompt};
use super::{AnalysisError, MoodAnalyzer};
use crate::models::MoodAnalysis;

const DEFAULT_URL: &str = "http://127.0.0.1:8080";
const DEFAULT_MODEL: &str = "qwen3-4b-instruct-2507-q4_k_m";
/// One analysis takes 1-3 minutes on the development machine; a cold start even more.
const TIMEOUT: Duration = Duration::from_secs(600);
const SEED: u32 = 42;
/// With temperature 0 a retry only helps with a different seed.
const RETRIES: u32 = 2;

pub struct LlamaCppAnalyzer {
    client: Client,
    url: String,
    model_id: String,
    system_prompt: String,
}

impl LlamaCppAnalyzer {
    /// `SOUNDTRACK_LLM_URL` (default `http://127.0.0.1:8080`) and `SOUNDTRACK_LLM_MODEL`
    /// (only names the model in the cache key; the server decides which model runs).
    pub fn from_env() -> Result<Self, AnalysisError> {
        let base = env::var("SOUNDTRACK_LLM_URL").unwrap_or_else(|_| DEFAULT_URL.into());
        let model_id = env::var("SOUNDTRACK_LLM_MODEL").unwrap_or_else(|_| DEFAULT_MODEL.into());
        let client = Client::builder().timeout(TIMEOUT).build().map_err(|e| AnalysisError::Http(e.to_string()))?;
        Ok(LlamaCppAnalyzer {
            client,
            url: format!("{}/v1/chat/completions", base.trim_end_matches('/')),
            model_id,
            system_prompt: system_prompt(),
        })
    }

    fn request(&self, text: &str, seed: u32) -> Result<MoodAnalysis, AnalysisError> {
        let body = ChatRequest {
            messages: [
                Message { role: "system", content: &self.system_prompt },
                Message { role: "user", content: text },
            ],
            temperature: 0.0,
            seed,
            max_tokens: 300,
            response_format: ResponseFormat {
                r#type: "json_schema",
                json_schema: JsonSchema { name: "mood", schema: response_schema() },
            },
        };
        let response = self.client.post(&self.url).json(&body).send().map_err(|e| {
            if e.is_connect() {
                AnalysisError::Unavailable(e.to_string())
            } else {
                AnalysisError::Http(e.to_string())
            }
        })?;
        match response.status() {
            // llama-server answers 503 while it is loading the model.
            StatusCode::SERVICE_UNAVAILABLE => return Err(AnalysisError::Unavailable("model is loading".into())),
            status if !status.is_success() => return Err(AnalysisError::Http(status.to_string())),
            _ => {}
        }
        let chat: ChatResponse = response.json().map_err(|e| AnalysisError::Invalid(e.to_string()))?;
        let content = chat
            .choices
            .into_iter()
            .next()
            .ok_or_else(|| AnalysisError::Invalid("no choices in the answer".into()))?
            .message
            .content;
        let analysis: MoodAnalysis =
            serde_json::from_str(&content).map_err(|e| AnalysisError::Invalid(format!("{e}: {content}")))?;
        analysis.validate().map_err(AnalysisError::Invalid)?;
        Ok(analysis)
    }
}

impl MoodAnalyzer for LlamaCppAnalyzer {
    fn model_id(&self) -> &str {
        &self.model_id
    }

    fn analyze(&self, text: &str) -> Result<MoodAnalysis, AnalysisError> {
        let mut attempt = 0;
        loop {
            match self.request(text, SEED + attempt) {
                Err(AnalysisError::Invalid(_)) if attempt < RETRIES => attempt += 1,
                result => return result,
            }
        }
    }
}

#[derive(Serialize)]
struct ChatRequest<'a> {
    messages: [Message<'a>; 2],
    temperature: f32,
    seed: u32,
    max_tokens: u32,
    response_format: ResponseFormat,
}

#[derive(Serialize)]
struct Message<'a> {
    role: &'static str,
    content: &'a str,
}

#[derive(Serialize)]
struct ResponseFormat {
    r#type: &'static str,
    json_schema: JsonSchema,
}

#[derive(Serialize)]
struct JsonSchema {
    name: &'static str,
    schema: ResponseSchema,
}

#[derive(Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
}

#[derive(Deserialize)]
struct Choice {
    message: ChoiceMessage,
}

#[derive(Deserialize)]
struct ChoiceMessage {
    content: String,
}
