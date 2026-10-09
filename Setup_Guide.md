# SAGE Setup Guide

This guide explains how to install, configure, and run SAGE on macOS, Windows, and Linux.

SAGE is a modular local AI assistant that uses request routing, deterministic tools, language models, and a dedicated response-phrasing model.

> **Compatibility notice:** The Python backend and the model inference runtime have different platform requirements. The MLX runtime is intended for Apple silicon. Windows and Linux users must verify that their configured inference backend supports their operating system and hardware before attempting to run the full model pipeline.

## Table of Contents

1. Requirements
2. Download SAGE
3. Create a Python Environment
4. Install Dependencies
5. Configure Models
6. Validate the Installation
7. Run SAGE
8. Troubleshooting
9. Security and Data Management

## 1. Requirements

### All platforms

* Git
* Python 3
* Internet access for downloading dependencies and model files
* Sufficient disk space and memory for the selected models
* The model weights and configuration required by your installation

Use a Python version supported by the project's dependencies. If installation fails because of Python compatibility, check the package requirements before changing versions.

### Platform-specific requirements

| Platform | Requirements                                                                                                                                       |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| macOS    | Apple silicon is recommended for the MLX-based runtime.                                                                                            |
| Windows  | A compatible model runtime is required; the MLX-based macOS setup should not be assumed to work unchanged.                                         |
| Linux    | A compatible CPU or GPU runtime is required. MLX provides separate Linux CPU and CUDA installation options, but SAGE integration must be verified. |

## 2. Download SAGE

Open a terminal or command-line application.

Clone the repository:

```bash
git clone https://github.com/LUNAR-HarshithDS/SAGE.git
cd SAGE
```

If you already have a local copy, navigate to its project directory instead.

Confirm that the main project files are present:

```text
sage.py
input_interpreter.py
function_router.py
model_router.py
request_router.py
sage_model_runtime.py
```

The repository may contain additional modules, configuration files, and data directories.

## 3. Create a Python Environment

A virtual environment keeps SAGE's dependencies separate from other Python projects.

### macOS

Open Terminal and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### Windows — PowerShell

Open PowerShell in the SAGE directory and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks activation, you can use Command Prompt instead.

### Windows — Command Prompt

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
```

### Linux

Open a terminal and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

If creating the virtual environment fails, install your distribution's Python virtual-environment package and retry.

For example, on Ubuntu or Debian:

```bash
sudo apt update
sudo apt install python3-venv python3-pip git
```

Keep the virtual environment activated while installing dependencies and running SAGE.

## 4. Install Dependencies

From the project root, install the base dependencies:

```bash
python -m pip install -r requirements.txt
```

Inspect the model-related dependencies:

```bash
python -c "print(open('requirements-models.txt').read())"
```

If your selected model backend requires those packages, install them:

```bash
python -m pip install -r requirements-models.txt
```

Do not assume that every dependency works on every operating system. If a package fails to install, check its platform requirements and the Python version supported by that package.

### MLX runtime

MLX is designed for Apple silicon. On a compatible Mac, install the project's required MLX packages through the appropriate requirements file or environment configuration.

Linux users should consult the official MLX installation documentation if they intend to use its CPU or CUDA backend. Windows users should select a supported inference backend rather than assuming that the MLX setup works unchanged.

## 5. Configure Models

SAGE is designed around multiple model roles.

| Model                            | Intended role                       |
| -------------------------------- | ----------------------------------- |
| Qwen3-4B                         | General-purpose reasoning           |
| Qwen3-8B                         | More demanding reasoning and coding |
| Qwen3-1.7B with the SAGE adapter | Response phrasing                   |

The actual models, model identifiers, quantization formats, and adapter paths depend on the runtime configuration.

Before launching SAGE:

1. Confirm which model identifiers the model router expects.
2. Download or locate the required model files.
3. Set the paths expected by the runtime.
4. Configure the 1.7B adapter if the phrasing pipeline uses it.
5. Ensure the 4B and 8B models are configured without adapters if that is the intended setup.
6. Confirm that your selected inference backend supports the models and hardware.

Review these files when troubleshooting:

```text
settings.json
model_router.py
sage_model_runtime.py
sage_model_api.py
sage_runtime_prompt.py
```

Do not publish private conversation data, local credentials, or machine-specific secrets.

## 6. Validate the Installation

Run a Python syntax check from the repository root:

```bash
python -m compileall -q .
```

If the command completes without errors, the Python files passed this syntax check. This does not verify that the model runtime, dependencies, or complete application work correctly.

If the project has a test suite, run its documented tests as well.

## 7. Run SAGE

The expected main entry point is `sage.py`.

With the virtual environment activated, try:

```bash
python sage.py
```

If SAGE does not start, inspect the error output and the entry-point logic in `sage.py`. Follow the launch procedure implemented by the current version of the project.

### Basic verification

Once the application starts, test:

* A basic conversational request
* A mathematical question
* A request requiring multi-step reasoning
* A coding question
* A request that uses the response-phrasing pipeline

Verify that the expected model or tool is selected and that the request completes successfully.

## 8. Troubleshooting

### Python or dependency errors

Check the active Python version:

```bash
python --version
python -m pip --version
```

Confirm that the virtual environment is active and install the required dependencies again.

### Model not found

Check the model identifier, directory, file permissions, and configured path. Make sure the model files are actually available on the machine.

### Adapter loading errors

Confirm that the adapter path exists and matches the intended model. Models configured without adapters should not be given unnecessary adapter paths.

### Insufficient memory

Large models can consume substantial memory. Close unnecessary applications, avoid loading multiple models simultaneously where possible, and confirm that the runtime releases models when they are no longer needed.

### MLX import or runtime errors

MLX is intended for Apple silicon, with separate supported installation paths for Linux. A Windows installation or an unsupported hardware configuration may require a different inference backend and corresponding changes to SAGE's runtime.

### Python syntax or import errors

Run:

```bash
python -m compileall -q .
```

Then inspect the traceback, dependency versions, and module imports.

### Application exits immediately

Read the complete terminal error. Check the model paths, configuration files, environment activation, and launch command.

## 9. Security and Data Management

Before committing changes or publishing your repository:

* Never commit passwords, API keys, or access tokens.
* Exclude private conversation histories and personal data.
* Keep large model weights and training artifacts out of Git unless you intentionally distribute them.
* Review local settings and data files before committing.
* Maintain an appropriate `.gitignore`.
* Inspect staged changes before pushing them to GitHub.

## 10. Development

When modifying SAGE, keep request interpretation, function routing, model selection, runtime execution, and response generation separate.

Test changes to the relevant modules before relying on them in the main assistant workflow.

For model-routing changes, test both a basic request and a more demanding request to identify regressions.

## Additional Resources

* Python virtual environments: https://docs.python.org/3/library/venv.html
* MLX framework: https://github.com/ml-explore/mlx
* SAGE repository: https://github.com/LUNAR-HarshithDS/SAGE
