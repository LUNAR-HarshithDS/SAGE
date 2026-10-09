"""Minimal request-router policy notes for the new SAGE model layer.

No changes to deterministic handlers are required just to use the trained
models. The model router reads these existing Request fields:

- kind
- complexity
- requires_web
- requires_local_knowledge
- use_thinking

Recommended classifications:

knowledge / local-first          -> 1.7B, thinking off
ordinary conversation            -> 4B, thinking off
complex / explicit research      -> 8B, thinking on
arithmetic / deterministic tool  -> no AI model
"""
