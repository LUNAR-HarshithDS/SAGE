# SAGE on Windows

This guide covers the Windows Python sidecar. The current SAGE model runtime uses MLX, which is not a native Windows inference backend. Windows therefore uses the existing `llama_bridge.py` adapter to connect SAGE to a separate `llama-server` process.

## Current status

- Python request routing, local tools, and the HTTP sidecar are intended to run on Windows.
- Model inference requires a compatible `llama-server` build and a Qwen3 GGUF model.
- The Python setup script does **not** download models or install `llama-server`.
- End-to-end behavior must be tested with the exact model and server build you use.

## Requirements

- Windows 10 or 11, 64-bit
- Python 3.11 or newer
- Git, if cloning the repository
- A compatible `llama-server` executable
- A Qwen3 GGUF model that fits your available RAM/VRAM
- Internet access to install Python dependencies
- Optional: `TAVILY_API_KEY` for web research

## 1. Get the project

Clone the repository, or open PowerShell in the folder containing `sage.py`:

```powershell
git clone https://github.com/LUNAR-HarshithDS/SAGE.git
cd SAGE
```

## 2. Set up Python

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_windows.ps1
```

The execution-policy change applies only to the current PowerShell process. You can alternatively use the batch launcher after setup.

## 3. Start llama-server

Install or build `llama-server` from the official llama.cpp project and obtain a compatible Qwen3 GGUF model. Start it so its OpenAI-compatible API listens on `127.0.0.1:8721`.

The exact model argument depends on the GGUF file you downloaded. A typical llama.cpp command has this shape:

```powershell
.\llama-server.exe -m "C:\path\to\your-qwen3-model.gguf" --host 127.0.0.1 --port 8721
```

Use a model and quantization that fit your hardware. Do not assume MLX model folders or MLX LoRA adapters can be loaded directly by llama.cpp. If you want SAGE's trained 1.7B adapter, it must be converted/merged into a compatible format using a supported workflow.

Before continuing, verify the server API responds:

```powershell
Invoke-RestMethod http://127.0.0.1:8721/v1/models
```

Keep this terminal open.

## 4. Start the SAGE sidecar

Open a second PowerShell window in the SAGE folder:

```powershell
.\run_windows.ps1
```

Or double-click `run_windows.bat`. The default ports are:

- llama-server: `127.0.0.1:8721`
- SAGE sidecar: `127.0.0.1:8722`

Check the sidecar health endpoint in a browser or PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8722/health
```

Expected response:

```json
{"ok":true}
```

The sidecar exposes `/message` as newline-delimited JSON for a local client. It is not a full graphical chat application.

## 5. Optional web research

Set a Tavily API key for the current PowerShell session if you want web research:

```powershell
$env:TAVILY_API_KEY = "your-key-here"
```

Do not commit API keys to Git or put them in source files.

## Troubleshooting

### Python is not recognized

Install Python 3.11 or newer and enable the Python Launcher / PATH option, then open a new terminal.

### Setup fails while installing packages

Read the first pip error. Confirm Python version and internet access, then retry:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements-windows.txt
```

### `llama-server` connection failed

Confirm the server is running on port 8721 and that this succeeds:

```powershell
Invoke-RestMethod http://127.0.0.1:8721/v1/models
```

### The model loads but output is incorrect

SAGE's bridge relies on the server's chat template and the GGUF model format. Verify Qwen3 chat-template and thinking behavior with your chosen llama.cpp build. The bridge and full pipeline still need end-to-end testing on the target machine.

### MLX import errors

The Windows sidecar should import the shared runtime types without requiring MLX. Actual Windows inference is handled by `llama_bridge.py`. If you run `sage.py` directly, it still follows the native MLX path and is not the Windows launch method.

## Security

The sidecar binds to localhost by default. Do not expose it to a public network without adding authentication and appropriate request protections. Keep model files, API keys, private memory, and conversation data out of public commits.
