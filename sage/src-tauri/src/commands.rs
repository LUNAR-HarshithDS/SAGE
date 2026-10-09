use crate::hardware::{self, HardwareReport};
use crate::sidecar::{self, SidecarState};
use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, State};

#[tauri::command]
pub fn check_environment() -> HardwareReport {
    hardware::detect()
}

#[tauri::command]
pub async fn prepare_model(
    app: AppHandle,
    state: State<'_, SidecarState>,
    size: String,
) -> Result<(), String> {
    let already_loaded = state.loaded_size.lock().unwrap().clone();
    if already_loaded.as_deref() == Some(size.as_str()) {
        return Ok(()); // already warm
    }

    let report = hardware::detect();
    let n_gpu_layers = if report.gpu_vram_gb.is_some() { 999 } else { 0 };

    sidecar::spawn_for_size(&app, &state, &size, n_gpu_layers).await
}

#[derive(Deserialize)]
pub struct ChatRequest {
    pub message: String,
    pub model_size: String,
}

#[derive(Serialize, Clone)]
#[serde(tag = "type")]
pub enum StreamEvent {
    #[serde(rename = "thinking_started")]
    ThinkingStarted,
    #[serde(rename = "thinking_finished")]
    ThinkingFinished,
    #[serde(rename = "token")]
    Token { text: String, thinking: bool },
    #[serde(rename = "complete")]
    Complete {
        reply: String,
        elapsed_secs: f64,
        tokens: u32,
        tokens_per_sec: f64,
    },
    #[serde(rename = "error")]
    Error { message: String },
}

/// Splits a Qwen3 completion stream into "thinking" vs "final answer"
/// segments based on <think>...</think> markers, emitting a `sage-stream`
/// event to the frontend for each meaningful chunk.
#[tauri::command]
pub async fn send_message(
    app: AppHandle,
    state: State<'_, SidecarState>,
    req: ChatRequest,
) -> Result<(), String> {
    if let Err(e) = prepare_model(app.clone(), state.clone(), req.model_size.clone()).await {
        let _ = app.emit("sage-stream", StreamEvent::Error { message: e.clone() });
        return Err(e);
    }

    let port = *state.port.lock().unwrap();
    let url = format!("http://127.0.0.1:{port}/v1/chat/completions");

    let body = serde_json::json!({
        "model": "sage",
        "messages": [{ "role": "user", "content": req.message }],
        "stream": true
    });

    let started = std::time::Instant::now();
    let client = reqwest::Client::new();

    let resp = match client.post(&url).json(&body).send().await {
        Ok(r) => r,
        Err(e) => {
            let msg = e.to_string();
            let _ = app.emit(
                "sage-stream",
                StreamEvent::Error {
                    message: msg.clone(),
                },
            );
            return Err(msg);
        }
    };

    let mut stream = resp.bytes_stream();
    let mut buffer = String::new();
    let mut full_reply = String::new();
    let mut in_thinking = false;
    let mut token_count: u32 = 0;

    while let Some(chunk) = stream.next().await {
        let chunk = match chunk {
            Ok(c) => c,
            Err(e) => {
                let msg = e.to_string();
                let _ = app.emit("sage-stream", StreamEvent::Error { message: msg.clone() });
                return Err(msg);
            }
        };
        buffer.push_str(&String::from_utf8_lossy(&chunk));

        while let Some(pos) = buffer.find("\n\n") {
            let line = buffer[..pos].trim().to_string();
            buffer.drain(..pos + 2);

            let Some(data) = line.strip_prefix("data: ") else {
                continue;
            };
            if data == "[DONE]" {
                continue;
            }

            let Ok(parsed) = serde_json::from_str::<serde_json::Value>(data) else {
                continue;
            };
            let Some(delta) = parsed["choices"][0]["delta"]["content"].as_str() else {
                continue;
            };
            if delta.is_empty() {
                continue;
            }

            token_count += 1;
            let mut remaining = delta;

            loop {
                if !in_thinking {
                    if let Some(idx) = remaining.find("<think>") {
                        let before = &remaining[..idx];
                        if !before.is_empty() {
                            full_reply.push_str(before);
                            let _ = app.emit(
                                "sage-stream",
                                StreamEvent::Token {
                                    text: before.to_string(),
                                    thinking: false,
                                },
                            );
                        }
                        in_thinking = true;
                        let _ = app.emit("sage-stream", StreamEvent::ThinkingStarted);
                        remaining = &remaining[idx + "<think>".len()..];
                        continue;
                    } else {
                        full_reply.push_str(remaining);
                        let _ = app.emit(
                            "sage-stream",
                            StreamEvent::Token {
                                text: remaining.to_string(),
                                thinking: false,
                            },
                        );
                        break;
                    }
                } else if let Some(idx) = remaining.find("</think>") {
                    let think_text = &remaining[..idx];
                    if !think_text.is_empty() {
                        let _ = app.emit(
                            "sage-stream",
                            StreamEvent::Token {
                                text: think_text.to_string(),
                                thinking: true,
                            },
                        );
                    }
                    in_thinking = false;
                    let _ = app.emit("sage-stream", StreamEvent::ThinkingFinished);
                    remaining = &remaining[idx + "</think>".len()..];
                    continue;
                } else {
                    let _ = app.emit(
                        "sage-stream",
                        StreamEvent::Token {
                            text: remaining.to_string(),
                            thinking: true,
                        },
                    );
                    break;
                }
            }
        }
    }

    let elapsed = started.elapsed().as_secs_f64();
    let tps = if elapsed > 0.0 {
        token_count as f64 / elapsed
    } else {
        0.0
    };

    let _ = app.emit(
        "sage-stream",
        StreamEvent::Complete {
            reply: full_reply,
            elapsed_secs: elapsed,
            tokens: token_count,
            tokens_per_sec: tps,
        },
    );

    Ok(())
}
