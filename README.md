# Personalized Interactive Comic Tree Dataset

This repository contains a dataset-construction pipeline for personalized interactive comic generation. It builds branching story trees where each user-topic pair becomes a structured interactive visual narrative.

The dataset is designed for three connected research tasks:

- multimodal click intent recognition
- personalized next-image generation
- generation-assisted user modeling

## Core Idea

Instead of generating isolated image samples, the pipeline constructs complete interactive comic trees:

```text
user profile + topic
        |
        v
shared root image
        |
        v
personalized branching story tree
        |
        v
grounded clicks + intents + slots + prompts + profile updates
        |
        v
generated images + visual calibration
```

Users with the same topic share the same root scene. After the root, branches are planned according to each user's dynamic state, so different users can produce increasingly different story structures and image prompts.

## What Each Tree Contains

Each `user + topic` tree contains:

- story nodes with image paths and story states
- directed branch edges
- grounded click regions
- closed-domain intent labels
- semi-open intent rankings
- fixed intent slots
- natural-language intent descriptions
- image-generation prompts
- expected affective deltas
- expected profile deltas
- optional post-generation visual calibration

The default tree is irregular, not a complete binary tree. It uses depth up to `5` and `18` nodes by default.

## User State Design

The pipeline separates long-term motivations from short-term affect.

### Long-Term Interactive Motivation Profile

The stable user profile is adapted from Yee's motivation framework for online play and operationalized for interactive visual storytelling:

- `goal_progress`
- `mastery_logic`
- `challenge_seeking`
- `social_attachment`
- `cooperative_orientation`
- `world_discovery`
- `role_immersion`
- `aesthetic_customization`

### Short-Term Affective State

The affective state is based on the Self-Assessment Manikin structure and extended for visual-story interaction:

- `pleasure`
- `arousal`
- `dominance`
- `tension`
- `curiosity`
- `empathy`
- `cognitive_load`

Generated images can shift the short-term affective state. The stable profile and current affect are combined into a composite state for branch planning and later profile estimation.

## Repository Layout

```text
dataset_tools/
  dataset_pipeline.py          staged text/image/calibration pipeline
  run_end_to_end_dataset.py    end-to-end runner with timing records
  select_and_normalize_profiles.py
                               select raw profiles and map them to dimensions
  build_topic_root_assets.py   helper for shared topic root assets
  prepare_user_topic_assets.py helper for user-topic asset folders
  build_contrast_web.py        local HTML visualization builder
  verify_dataset_format.py     format verifier for public assets and tree JSON
assets/topic_roots/            curated shared root nodes for 12 topics
data/user_profiles.jsonl       initial raw user profile file
docs/
  DATASET_CONSTRUCTION.md      detailed data schema and workflow
```

Generated runs, local configs, non-curated raw user files, and image batches are intentionally ignored by git.

## Quick Dry Run

Dry run mode creates the full folder structure and JSON annotations without calling external model services:

```powershell
cd dataset_tools
python run_end_to_end_dataset.py --dry-run --profile-limit 1 --topics "Hidden Castle" --topics-per-user 1 --tree-nodes 18 --branch-depth 5
```

## Staged Usage

Text planning:

```powershell
cd dataset_tools
python dataset_pipeline.py --stage text --profile-limit 1 --topics "Hidden Castle" --topics-per-user 1 --tree-nodes 18 --branch-depth 5
```

Image generation for an existing run:

```powershell
python dataset_pipeline.py --stage images --run-dir "dataset_runs\run_YYYYMMDD_HHMMSS"
```

Post-generation calibration:

```powershell
python dataset_pipeline.py --stage calibrate --run-dir "dataset_runs\run_YYYYMMDD_HHMMSS"
```

End-to-end execution:

```powershell
python run_end_to_end_dataset.py --profile-limit 1 --topics "Hidden Castle" --topics-per-user 1 --tree-nodes 18 --branch-depth 5
```

For non-dry runs, keep model service settings and credentials outside the repository.

## Selecting And Mapping User Profiles

The initial raw user profile file is included at `data/user_profiles.jsonl`. To select informative profiles:

```powershell
cd dataset_tools
python select_and_normalize_profiles.py --profiles ../data/user_profiles.jsonl --limit 5
```

To select and map profiles into the long-term motivation and short-term affective dimensions:

```powershell
python select_and_normalize_profiles.py --profiles ../data/user_profiles.jsonl --limit 5 --normalize
```

For a no-service test:

```powershell
python select_and_normalize_profiles.py --profiles ../data/user_profiles.jsonl --limit 5 --normalize --dry-run
```

## Curated Root Assets

The repository includes 12 public topic root nodes in `assets/topic_roots/`. Each topic folder contains:

- `root.png`
- `synopsis.txt`
- `root_prompt.txt`
- `root_asset.json`
- `generation_metadata.json`

These files are sanitized for release: paths are relative, and local run paths or private service settings are not included.

Verify the asset format with:

```powershell
python dataset_tools/verify_dataset_format.py --root-assets assets/topic_roots
```

## Outputs

Each run writes:

- `profiles_normalized.jsonl`
- `topics.json`
- `manifest.jsonl`
- `users/user_x/topic_y/tree.json`
- node images or mock image metadata
- `stage_timings.json`
- `end_to_end_summary.json`

The end-to-end runner records time spent in text planning, image generation, and calibration.

## Safety

Do not commit:

- raw user profile files
- generated run directories
- local model service settings
- credentials
- non-curated generated image batches

The pipeline excludes sensitive connection settings from public run summaries.
