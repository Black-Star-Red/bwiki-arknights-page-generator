# Project Structure

This package now follows a layered structure to reduce coupling with the legacy
monolithic script (`core/干员脚本2.0.py`).

## Layers

- `app/`
  - Entry points only (`cli_main.py`, `gui_main.py`).
  - No business logic.
- `core/use_cases/`
  - Public business use-cases (`run_character_pipeline`).
  - Stable API surface for callers.
- `core/legacy_api.py`
  - Adapter layer for calling functions exposed by the legacy script.
  - Centralizes reflection (`getattr`) and error handling.
- `shared/globals/`
  - Actual source of shared static constants.
  - Split by domain (`wiki_constants.py`, `gameplay_constants.py`).
  - Used by core modules directly.
- `shared/services/`
  - Actual source of external integration services (Bilibili/Wiki).
  - Includes wiki publish orchestration helpers (page creation + portrait upload).
  - Used by core modules directly.
- `shared/utils/`
  - Shared pure helper functions extracted from legacy script.
  - Keeps business flow code focused on orchestration.
- `shared/rendering/`
  - Shared rendering/parsing helpers for wiki text generation.
  - Isolates complex text parsing from orchestration flow.
  - Includes template helper builders (e.g. drawer/material rendering).
  - Includes progression rendering helpers (e.g. `Material`, `LevelUPEnhance`).
  - Includes split field renderers (e.g. talents/attributes/skills/summon/infrastructure/dossier/voice sections).
- `core/legacy_loader.py`
  - Dynamic module loading (`importlib`) for the legacy script.
- `data/`
  - DataMapper and data source implementations.
  - Includes temporary source switching for cross-source fallback logic.

## Dependency Direction

`app -> core/use_cases -> core/legacy_api -> core/legacy_loader -> legacy script`

`core/use_cases -> data` (through legacy script runtime flow)

The key rule is: outer layers can depend on inner layers, not the reverse.

## Incremental Refactor Plan

1. Keep legacy script behavior unchanged.
2. Move reusable logic from legacy script into `core/use_cases/` modules.
3. Keep adapters thin and typed.
4. Replace reflection in callers with direct use-case calls over time.
