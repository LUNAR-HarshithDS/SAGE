use serde::Serialize;
use sysinfo::System;

#[derive(Serialize, Clone)]
pub struct HardwareReport {
    pub cpu_cores: usize,
    pub total_ram_gb: f64,
    pub gpu_name: Option<String>,
    pub gpu_vram_gb: Option<f64>,
    pub os: String,
    pub arch: String,
    pub fits: ModelFit,
}

#[derive(Serialize, Clone)]
pub struct ModelFit {
    pub can_run_1_7b: bool,
    pub can_run_4b: bool,
    pub can_run_8b: bool,
    pub recommended: String,
    pub notes: Vec<String>,
}

// Rough, deliberately conservative thresholds for Q4_K_M-quantized weights,
// leaving headroom for context + KV cache on top of raw weight size:
//   1.7B ≈ 1.4GB weights -> want ~4GB+ usable
//   4B   ≈ 2.6GB weights -> want ~6GB+ usable
//   8B   ≈ 5.0GB weights -> want ~10GB+ usable
// Tune these once you've benchmarked actual behavior on real hardware.

pub fn detect() -> HardwareReport {
    let mut sys = System::new_all();
    sys.refresh_all();

    let cpu_cores = sys.cpus().len();
    // NOTE: sysinfo's total_memory() has returned different units across
    // major versions (KB vs bytes). Verify this conversion against the
    // sysinfo version actually resolved in Cargo.lock — divide by 1024^2
    // instead of 1024^3 if the reported RAM looks 1000x too small.
    let total_ram_gb = sys.total_memory() as f64 / 1024.0 / 1024.0 / 1024.0;

    let (gpu_name, gpu_vram_gb) = detect_gpu();

    // If there's no clearly identified dedicated GPU, assume CPU-only and
    // budget a conservative fraction of system RAM (leaving room for the OS
    // and the app itself) rather than the full total.
    let usable_gb = gpu_vram_gb.unwrap_or(total_ram_gb * 0.6);

    let can_run_1_7b = usable_gb >= 4.0;
    let can_run_4b = usable_gb >= 6.0;
    let can_run_8b = usable_gb >= 10.0;

    let recommended = if can_run_8b {
        "8b"
    } else if can_run_4b {
        "4b"
    } else if can_run_1_7b {
        "1.7b"
    } else {
        "none"
    }
    .to_string();

    let mut notes = Vec::new();
    if gpu_vram_gb.is_none() {
        notes.push(
            "No dedicated GPU detected — running on CPU will be noticeably slower.".to_string(),
        );
    }
    if recommended == "none" {
        notes.push(
            "This machine may struggle even with the smallest Sage model. Expect slow responses."
                .to_string(),
        );
    }

    HardwareReport {
        cpu_cores,
        total_ram_gb,
        gpu_name,
        gpu_vram_gb,
        os: std::env::consts::OS.to_string(),
        arch: std::env::consts::ARCH.to_string(),
        fits: ModelFit {
            can_run_1_7b,
            can_run_4b,
            can_run_8b,
            recommended,
            notes,
        },
    }
}

#[cfg(target_os = "macos")]
fn detect_gpu() -> (Option<String>, Option<f64>) {
    // Apple Silicon shares system RAM as VRAM (no separate dedicated pool to
    // query cheaply from Rust without extra deps), so we report the chip
    // name for display and let the caller fall back to the RAM-based
    // estimate for capacity planning.
    let name = std::process::Command::new("sysctl")
        .args(["-n", "machdep.cpu.brand_string"])
        .output()
        .ok()
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.trim().to_string());
    (name, None)
}

#[cfg(target_os = "windows")]
fn detect_gpu() -> (Option<String>, Option<f64>) {
    let output = std::process::Command::new("wmic")
        .args(["path", "win32_VideoController", "get", "name,AdapterRAM"])
        .output();

    match output {
        Ok(o) => parse_wmic_gpu(&String::from_utf8_lossy(&o.stdout)),
        Err(_) => (None, None),
    }
}

#[cfg(target_os = "windows")]
fn parse_wmic_gpu(text: &str) -> (Option<String>, Option<f64>) {
    for line in text.lines().skip(1) {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        if let Some((ram, name)) = line.split_once(' ') {
            if let Ok(bytes) = ram.trim().parse::<f64>() {
                return (
                    Some(name.trim().to_string()),
                    Some(bytes / 1024.0 / 1024.0 / 1024.0),
                );
            }
        }
    }
    (None, None)
}

#[cfg(target_os = "linux")]
fn detect_gpu() -> (Option<String>, Option<f64>) {
    // Best-effort via nvidia-smi. Returns None (falls back to the RAM-based
    // estimate) on AMD/Intel GPUs or CPU-only boxes where it isn't installed.
    let output = std::process::Command::new("nvidia-smi")
        .args([
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ])
        .output();

    match output {
        Ok(o) if o.status.success() => {
            let text = String::from_utf8_lossy(&o.stdout);
            let line = text.lines().next().unwrap_or("");
            if let Some((name, mem)) = line.split_once(',') {
                let mb: f64 = mem.trim().parse().unwrap_or(0.0);
                (Some(name.trim().to_string()), Some(mb / 1024.0))
            } else {
                (None, None)
            }
        }
        _ => (None, None),
    }
}
