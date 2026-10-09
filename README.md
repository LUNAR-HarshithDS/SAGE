# SAGE

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

Follow **[SETUP.md](SETUP.md)** for model installation, configuration, validation, and launch instructions.

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

See [SETUP.md](SETUP.md) for the setup procedure.

## Project Status

SAGE is an actively developed personal AI assistant. Features, model configurations, and internal interfaces may change as development continues.

## License

A license has not been specified here. Check the repository for an existing `LICENSE` file before redistributing or reusing the project.

## Author

Developed as an independent AI assistant project.
