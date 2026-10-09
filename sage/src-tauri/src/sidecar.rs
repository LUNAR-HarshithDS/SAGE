use std::sync::Mutex;
use tauri::AppHandle;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

pub struct SidecarState {
    pub child: Mutex<Option<CommandChild>>,
    pub port: Mutex<u16>,
    pub loaded_size: Mutex<Option<String>>,
}

impl Default for SidecarState {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
            port: Mutex::new(8721),
            loaded_size: Mutex::new(None),
        }
    }
}

/// Where to look for extracted model / adapter files. Adjust to taste, or
/// make this configurable from the UI later — see extract_from_ollama.py
/// for pulling these out of Ollama's storage.
pub fn model_path_for(size: &str) -> String {
    format!("models/sage-{size}.gguf")
}

pub fn adapter_path_for(size: &str) -> String {
    format!("models/sage-{size}-adapter.gguf")
}

pub async fn spawn_for_size(
    app: &AppHandle,
    state: &SidecarState,
    size: &str,
    n_gpu_layers: u32,
) -> Result<(), String> {
    // Only one model is ever loaded at a time by design — no router, no
    // simultaneous sizes. Switching sizes kills the old instance first.
    stop(state);

    let port = *state.port.lock().unwrap();
    let model = model_path_for(size);
    let adapter = adapter_path_for(size);

    if !std::path::Path::new(&model).exists() {
        return Err(format!(
            "Model file not found: {model}. Run extract_from_ollama.py first."
        ));
    }

    let mut args = vec![
        "-m".to_string(),
        model,
        "--port".to_string(),
        port.to_string(),
        "-c".to_string(),
        "4096".to_string(),
        "-ngl".to_string(),
        n_gpu_layers.to_string(),
    ];

    if std::path::Path::new(&adapter).exists() {
        args.push("--lora".to_string());
        args.push(adapter);
    }

    let sidecar = app
        .shell()
        .sidecar("llama-server")
        .map_err(|e| e.to_string())?
        .args(args);

    let (mut rx, child) = sidecar.spawn().map_err(|e| e.to_string())?;

    *state.child.lock().unwrap() = Some(child);
    *state.loaded_size.lock().unwrap() = Some(size.to_string());

    // Drain stdout/stderr so the child never blocks on a full pipe. Wire
    // this to a Tauri event or log file if you want llama.cpp's own logs
    // visible during development.
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(_) | CommandEvent::Stderr(_) => {}
                CommandEvent::Terminated(_) => break,
                _ => {}
            }
        }
    });

    wait_until_healthy(port).await
}

pub fn stop(state: &SidecarState) {
    if let Some(child) = state.child.lock().unwrap().take() {
        let _ = child.kill();
    }
    *state.loaded_size.lock().unwrap() = None;
}

async fn wait_until_healthy(port: u16) -> Result<(), String> {
    let url = format!("http://127.0.0.1:{port}/health");
    for _ in 0..150 {
        if let Ok(resp) = reqwest::get(&url).await {
            if resp.status().is_success() {
                return Ok(());
            }
        }
        tokio::time::sleep(std::time::Duration::from_millis(200)).await;
    }
    Err("llama-server did not become healthy in time".to_string())
}
