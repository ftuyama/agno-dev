"""Pytest configuration for agno-game-dev-crew."""

import os

# Tests may import agno before game_dev_crew; set before tokenizers (FastEmbed) load.
if "TOKENIZERS_PARALLELISM" not in os.environ:
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
