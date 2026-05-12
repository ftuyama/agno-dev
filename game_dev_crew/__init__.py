"""Agno Game Dev Crew — multi-agent helpers for the game repo (REPO_ROOT)."""

import os

# FastEmbed pulls in huggingface/tokenizers; set before any tokenizer use so forks
# (e.g. multiprocessing after embeddings) do not trigger TOKENIZERS_PARALLELISM warnings.
if "TOKENIZERS_PARALLELISM" not in os.environ:
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

__all__ = ["__version__"]

__version__ = "0.1.0"
