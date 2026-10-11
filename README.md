## Table of Contents

- [SAGE](#sage)
- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Model Strategy](#model-strategy)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Getting Started](#getting-started)
- [Development Principles](#development-principles)
- [Troubleshooting](#troubleshooting)
- [Project Satus](#project-status)
- [SAGE Setup Guide](#sage-setup-guide)







## SAGE

**A Local AI Assistant for Reasoning, Research, and Task Execution**

SAGE is a modular AI assistant designed to run locally, combining language models, request routing, deterministic tools, and a dedicated response-phrasing model. Its architecture aims to balance reasoning quality, response clarity, and resource usage on consumer hardware.

## Overview

SAGE separates request interpretation, task routing, model selection, execution, and response generation into distinct components. This makes the system easier to maintain and extend as new capabilities are added.

The project is designed around local inference, with an emphasis on configurable behavior and a modular Python backend.

## Key Features

* **Intelligent request routing:** Interprets incoming requests and selects an appropriate processing path.
* **Multi-model architecture:** Uses different model sizes according to task complexity.
* **Dedicated response phrasing:** Supports a fine-tuned 1.7B model for producing clear, natural responses.
* **Local inference:** Supports an MLX-based runtime for compatible Apple Silicon systems.
* **Deterministic tools:** Provides code-based handling for supported calculations and other structured tasks.
* **Modular architecture:** Separates request interpretation, function routing, model selection, and model execution.
* **Configurable reasoning:** Supports model-specific reasoning behavior through the runtime and routing configuration.

## Architecture

SAGE is organized into several cooperating components.

| Component           | Responsibility                                                                             |
| ------------------- | ------------------------------------------------------------------------------------------ |
| Input Interpreter   | Identifies the intent and complexity of a request.                                         |
| Function Router     | Determines whether a request should use a tool, local knowledge, research, or an AI model. |
| Model Router        | Selects an appropriate model for the task.                                                 |
| Model Runtime       | Loads models and generates responses using the configured inference backend.               |
| Deterministic Tools | Handles supported operations through regular code rather than language-model generation.   |
| Response Writer     | Uses the dedicated 1.7B phrasing model when the configured pipeline requires it.           |

### Model Strategy

The intended model configuration uses three model roles:

* **Qwen3-4B:** General-purpose reasoning and everyday requests.
* **Qwen3-8B:** More demanding reasoning and coding tasks.
* **Qwen3-1.7B with a SAGE fine-tuned adapter:** Response phrasing and presentation.

The model router determines which path is used. Not every request needs to run through every model.

The exact behavior depends on the installed models and the active runtime configuration.

## Project Structure

The repository contains the main assistant entry point and supporting modules, including:

```text
SAGE/
├── sage.py
├── input_interpreter.py
├── function_router.py
├── model_router.py
├── request_router.py
├── sage_model_runtime.py
├── sage_model_api.py
├── deterministic_tools.py
├── knowledge.py
├── math_engine.py
├── pdf_processor.py
├── sage_runtime_prompt.py
├── requirements.txt
├── requirements-models.txt
├── README.md
└── SETUP.md
```

Additional directories and files may be present for datasets, knowledge sources, training, configuration, and local development.

## Requirements

The requirements depend on the selected inference backend and installed models.

* macOS on Apple Silicon for the MLX-based setup described in this repository.
* A supported Python version.
* Git.
* Python dependencies listed in the project's requirements files.
* The model weights required by the configured model runtime.
* Sufficient memory and storage for the selected models.

The 4B, 8B, and 1.7B models have different memory requirements. Model selection should account for available RAM and the overhead of other running applications.

## Getting Started

Clone the repository:

```bash
git clone https://github.com/LUNAR-HarshithDS/SAGE.git
cd SAGE
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project's base dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Follow the Setup Guide for model installation, configuration, validation, and launch instructions.

## Development Principles

SAGE is built around the following principles:

1. **Modularity:** Keep routing, execution, and generation logic separate.
2. **Local-first operation:** Prefer local processing where supported and appropriate.
3. **Efficient model use:** Avoid loading larger models when a smaller or deterministic path is sufficient.
4. **Clear responses:** Separate reasoning and response presentation where the configured pipeline supports it.
5. **Maintainability:** Keep configuration, model selection, and runtime behavior understandable and testable.

## Troubleshooting

For setup and runtime problems:

1. Confirm that the virtual environment is active.
2. Verify that the required model directories and files exist.
3. Check that installed packages support your Python and macOS versions.
4. Review the terminal output for model-loading and dependency errors.
5. Confirm that the configured model paths match the actual files on your machine.

See the Setup Guide for the setup procedure.

## Project Status

SAGE is an actively developed personal AI assistant. Features, model configurations, and internal interfaces may change as development continues.

## License

A license has not been specified here. Check the repository for an existing `LICENSE` file before redistributing or reusing the project.

## Author

Developed as an independent AI assistant project.

## SAGE Setup Guide

This guide covers preparing, configuring, and running SAGE on macOS,
Windows, and Linux.

SAGE is a modular local AI assistant. Its repository includes request
routing, model selection, a native MLX model runtime, and an
experimental bridge/server path for llama.cpp-compatible models.

> **Compatibility status:** The native runtime in
> `sage_model_runtime.py` imports MLX and is designed for Apple silicon.
> Do not assume that this runtime works on Windows or Linux unchanged.
> The Windows/Linux llama.cpp route requires a compatible GGUF model, a
> working `llama-server`, and a runtime configuration that matches the
> checked-out version of SAGE. Treat those platforms as experimental
> until the full request pipeline has been tested.


## 1. Before You Begin

### General requirements

-   Git
-   Python 3
-   Internet access to install packages and download model files
-   Enough memory and disk space for the model you intend to run
-   A terminal or command-line application

Use a Python version supported by the dependencies in the current
repository. If a package fails to install, check that package's
supported Python versions rather than repeatedly retrying the same
command.

### Platform overview

  -----------------------------------------------------------------------
  Platform                Recommended starting    Important limitation
                          point                   
  ----------------------- ----------------------- -----------------------
  macOS on Apple silicon  Native MLX runtime      Best match for the
                                                  current native runtime.

  Windows                 Experimental llama.cpp  Requires a compatible
                          / `llama-server` route  GGUF model and matching
                                                  server/runtime
                                                  configuration.

  Linux                   Experimental llama.cpp  The native SAGE runtime
                          route, or a separately  and dependencies must
                          validated MLX setup     be checked for the
                                                  selected backend and
                                                  hardware.
  -----------------------------------------------------------------------

## 2. Get the Source Code

Open Terminal (macOS/Linux), PowerShell (Windows), or your preferred
shell.

Clone the repository:

``` bash
git clone https://github.com/LUNAR-HarshithDS/SAGE.git
cd SAGE
```

If you already have a local checkout, change into that directory
instead. Before changing files, confirm that you are in the repository
root and that `sage.py`, `model_router.py`, and `sage_model_runtime.py`
are present.

## 3. Create a Python Environment

A virtual environment isolates SAGE's Python packages from other
projects.

### macOS

``` bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### Windows --- PowerShell

Run these commands from the SAGE repository directory:

``` powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks activation, either allow it for the current
PowerShell process only:

``` powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

Or use Command Prompt:

``` bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
```

### Linux

``` bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

On Debian or Ubuntu, if virtual-environment creation fails because
`venv` is missing:

``` bash
sudo apt update
sudo apt install python3-venv python3-pip git
```

Keep the environment activated while installing dependencies and running
SAGE.

## 4. Install Dependencies

First inspect the dependency files in the repository:

``` text
requirements.txt
requirements-models.txt
```

The current `requirements.txt` is focused on MLX-LM training
dependencies. It is not a complete, cross-platform lockfile for every
possible SAGE runtime.

### macOS --- native MLX runtime

On Apple silicon, install the native model dependencies in the active
virtual environment:

``` bash
python -m pip install --upgrade pip
python -m pip install "mlx-lm[train]" huggingface_hub
```

MLX is designed primarily for Apple silicon. Use the project's MLX
runtime and its configured model/adapter paths only when the model files
and installed package versions match the code.

### Windows --- experimental server route

Do not install MLX as though it were a normal Windows dependency. For
Windows, use a compatible build of `llama.cpp` that provides
`llama-server`, and select a GGUF model compatible with that server.

The server installation is separate from Python dependencies. Follow the
official llama.cpp instructions for your Windows architecture and
GPU/CPU backend. Confirm that `llama-server --version` works before
attempting to connect SAGE to it.

The Python package list for the server route depends on the current SAGE
code and may differ from the MLX training dependencies. Do not blindly
install the macOS requirements file on Windows.

### Linux --- experimental server route

For a portable starting point, use a compatible `llama.cpp` build with
`llama-server` and a supported GGUF model. Follow the official
build/install instructions for your Linux distribution and hardware.

MLX also has Linux support paths for selected configurations, but that
does not automatically make the current SAGE MLX runtime or its full
model pipeline Linux-compatible. Validate the exact runtime,
dependencies, and model configuration before relying on it.

## 5. Configure the Model Runtime

SAGE's intended model roles are:

  Model role                         Intended purpose
  ---------------------------------- -------------------------------------
  Qwen3-4B                           General reasoning
  Qwen3-8B                           More demanding reasoning and coding
  Qwen3-1.7B with the SAGE adapter   Response phrasing

The model names above describe the intended design, not a guarantee that
every format or backend is configured automatically. Model identifiers,
quantization, adapter format, and paths must match the runtime selected
for your platform.

### macOS

1.  Check the model identifiers and paths used by `model_router.py` and
    `sage_model_runtime.py`.
2.  Ensure the required model files are available.
3.  Configure the 1.7B adapter path if the phrasing stage uses it.
4.  Keep the 4B and 8B models adapter-free if that is the configuration
    you intend to use.
5.  Confirm that the selected MLX model and adapter formats match the
    installed MLX-LM version.

### Windows and Linux

1.  Choose a GGUF model that your installed `llama-server` supports.
2.  Start the server using the model path and settings required by your
    setup.
3.  Check the server's listening address and port.
4.  Make sure SAGE's bridge/runtime configuration targets that exact
    address and port.
5.  Confirm whether the current code supports every stage you need,
    especially the separate 1.7B phrasing stage and its adapter. An MLX
    adapter is not automatically interchangeable with a
    llama.cpp-compatible adapter.
6.  Do not assume the full 4B/8B reasoning plus 1.7B phrasing workflow
    is working until you have tested it end to end.

Do not commit model weights, private prompts, credentials, or local-only
configuration containing secrets.

## 6. Run SAGE

With the virtual environment activated, first check the Python files for
syntax errors.

### macOS

``` bash
python -m compileall -q .
python sage.py
```

The launch command assumes `sage.py` is the intended entry point in your
current checkout. If it exits, use the traceback to identify missing
dependencies, model paths, or configuration.

### Windows

If your checkout includes the Windows launcher scripts, open PowerShell
in the repository root and follow `WINDOWS.md` for the server startup
and launch sequence. The launcher cannot supply a missing model or
automatically convert an MLX adapter.

You can run a syntax check independently:

``` powershell
python -m compileall -q .
```

### Linux

``` bash
python -m compileall -q .
python sage.py
```

These commands check syntax and attempt to launch the application; they
do not prove that the selected inference backend or all model stages
work. If your Linux setup uses `llama-server`, start and verify that
service according to your configuration before launching SAGE.

## 7. Validate the Installation

Test the application in stages:

1.  **Startup:** SAGE launches without import or configuration errors.
2.  **Basic response:** Send a simple conversational request.
3.  **Reasoning:** Try a multi-step question.
4.  **Coding:** Try a small programming task.
5.  **Model routing:** Confirm the expected model is selected for simple
    and demanding requests.
6.  **Phrasing stage:** If enabled, confirm that the 1.7B
    response-phrasing stage completes.
7.  **Resource cleanup:** Confirm that models are released when no
    longer needed, where the selected runtime supports that behavior.

A successful Python syntax check is not an end-to-end test. Record
platform, Python version, runtime/backend, model format, and any error
output when reporting a problem.

## 8. Troubleshooting

### `ModuleNotFoundError`

Activate the project's virtual environment, then install the
dependencies required by the selected runtime. Check whether the missing
package is platform-specific.

### MLX import or installation failure

MLX is not a universal cross-platform backend. On Windows, use the
configured supported alternative rather than trying to force the native
MLX runtime to load. On Linux, verify that the installed MLX package
supports your hardware and that SAGE's runtime is compatible with it.

### Model or adapter not found

Check the configured path, spelling, permissions, and model format. Make
sure the model actually exists locally and is supported by the selected
runtime.

### `llama-server` connection failure

Confirm that the server is installed, the model loaded successfully, and
the configured host/port match. Test the server directly before
troubleshooting SAGE's bridge.

### Out-of-memory errors or very slow generation

Use a smaller or more heavily quantized model, close unnecessary
applications, reduce the context length, and avoid loading several large
models at once. Memory requirements depend on model size, quantization,
context length, and runtime.

### SAGE exits immediately

Read the complete terminal traceback. Check Python version,
virtual-environment activation, configuration, model paths, and server
status. Do not suppress the error before identifying its cause.

## 9. Security and Git Hygiene

Before committing or publishing changes:

-   Never commit passwords, API keys, access tokens, or private
    credentials.
-   Exclude private conversation histories and personal data.
-   Keep large model weights and training artifacts out of Git unless
    you intentionally distribute them.
-   Review local settings and generated files before committing.
-   Maintain a suitable `.gitignore`.
-   Inspect staged changes before pushing:

``` bash
git status
git diff --cached
```

## Additional Resources

-   SAGE repository: https://github.com/LUNAR-HarshithDS/SAGE
-   Python virtual environments:
    https://docs.python.org/3/library/venv.html
-   MLX: https://github.com/ml-explore/mlx
-   llama.cpp: https://github.com/ggml-org/llama.cpp


