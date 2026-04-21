"""CLI entrypoint for new package layout."""

from __future__ import annotations

from arknights_toolbox.core.pipeline import run_character_pipeline
from arknights_toolbox.core.legacy_api import run_legacy_cli

def main() -> None:
    run_legacy_cli()


__all__ = ["run_character_pipeline", "main"]


if __name__ == "__main__":
    main()

