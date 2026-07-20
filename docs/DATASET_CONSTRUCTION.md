# Dataset Construction Details

This document describes how to construct personalized interactive comic tree data with the scripts in `dataset_tools/`.

## Task Formulation

The dataset is built around complete branching visual narratives. A sample can be used at different granularities:

- full tree: for studying personalized branching story generation
- single edge: for intent recognition and next-image generation
- trajectory: for generation-assisted user modeling

Each edge represents a possible user interaction:

```text
parent image + click target + user state -> intent label + next story state + target image prompt
```

After images are generated, the visual calibration stage checks whether the target image actually supports the planned branch and updates the final affect/profile deltas.

## Stage 1: Text Planning

The text stage creates all symbolic annotations and prompts before image generation.

Inputs:

- raw user profile notes
- topic names or curated topic root assets
- tree size settings

Outputs:

- normalized user profile
- shared topic world bible
- root image prompt
- personalized tree topology
- branch story states
- visual grounding targets
- intent labels
- fixed slots
- expected affect/profile deltas
- image-generation prompts

The root prompt is topic-only. It should not use user preferences, because all users under the same topic should share the same root image.

## Profile Selection And Dimension Mapping

The repository includes the initial raw profile file at `data/user_profiles.jsonl`.

Use `dataset_tools/select_and_normalize_profiles.py` to select profiles before running full tree construction. By default, profiles are ranked by a simple evidence-richness score using profile text length plus positive and negative preference counts.

Select the top profiles:

```powershell
cd dataset_tools
python select_and_normalize_profiles.py --profiles ../data/user_profiles.jsonl --limit 5
```

Select a specific user:

```powershell
python select_and_normalize_profiles.py --profiles ../data/user_profiles.jsonl --user-id 2071 --limit 1
```

Select and map profiles to the dataset dimensions:

```powershell
python select_and_normalize_profiles.py --profiles ../data/user_profiles.jsonl --limit 5 --normalize
```

The actual mapping logic is implemented in `DatasetPipeline.normalize_profile()`. It converts raw profile text into:

- `stable_profile`: 8 long-term interactive motivation dimensions
- `affective_state_0`: 7 short-term affect dimensions, usually initialized near neutral
- `profile_summary`
- `dimension_rationales`

## Stage 2: Image Generation

The image stage reads saved prompts from the text stage and generates node images.

For branch nodes, the parent image can be passed as a continuity reference. Prompts include constraints for:

- protagonist identity
- key objects
- visual style
- location continuity
- branch-specific diversity
- no visible metadata or labels

## Stage 3: Visual Calibration

The calibration stage compares:

- source node image
- target node image
- branch plan
- expected deltas

It writes:

- `observed_affective_delta`
- `observed_profile_delta`
- `final_affective_delta`
- `final_profile_delta`
- `delta_alignment`
- `calibration.visual_notes`

This allows the dataset to distinguish intended labels from what the generated image actually expresses.

## Tree Design

Default tree settings:

- `branch_depth = 5`
- `tree_nodes = 18`
- `valid_edges_per_tree = 17`

The topology is intentionally irregular. Some paths are short, while others continue deeper. This makes the tree more realistic than a complete binary tree and reduces wasted branches.

## Intent Schema

Closed-domain labels:

- `zoom_in`: look closer at a specific target
- `reveal`: reveal hidden information
- `branch_out`: enter a new place or story branch
- `reframe`: change perspective while continuing the current event
- `follow`: follow a character or clue
- `interact`: interact with a character or object

Each branch also stores:

- `grounding.target_box`
- `grounding.target_label`
- `grounding.target_caption`
- `intent_ranking`
- `slots.action`
- `slots.target`
- `slots.narrative_goal`
- `slots.mood`
- `slots.continuity_constraint`
- `slots.scope`
- `decision.confidence`
- `decision.requires_confirmation`
- `decision.is_oos`

This supports visual grounding, closed-domain classification, semi-open intent ranking, slot prediction, and OOS/confirmation experiments.

## Long-Term User Profile

Scores are normalized to `[0, 1]`.

Scoring anchors:

- `0.0-0.2`: very low
- `0.2-0.4`: low
- `0.4-0.6`: neutral, mixed, or insufficient evidence
- `0.6-0.8`: high
- `0.8-1.0`: very high

Dimensions:

- `goal_progress`: preference for clear objectives, visible progress, unlocked outcomes, and decisive story advancement.
- `mastery_logic`: preference for rules, mechanisms, causal explanations, puzzles, clues, and system understanding.
- `challenge_seeking`: preference for risk, pressure, conflict, difficulty, danger, or high-stakes choices.
- `social_attachment`: preference for characters, relationships, emotional bonds, facial expressions, and interpersonal stakes.
- `cooperative_orientation`: preference for helping, repairing, negotiating, protecting, or solving problems with others.
- `world_discovery`: preference for entering new places, discovering hidden regions, and expanding the fictional world.
- `role_immersion`: preference for acting from inside the protagonist's role and preserving narrative atmosphere and continuity.
- `aesthetic_customization`: preference for visual style, beauty, concrete design details, personalization, and creative variation.

## Short-Term Affective State

Scores are normalized to `[0, 1]`.

Dimensions:

- `pleasure`: how positive, satisfying, warm, or appealing the current experience feels.
- `arousal`: how emotionally activated, alert, excited, or energized the user is.
- `dominance`: how much the user feels able to understand, control, and influence the situation.
- `tension`: pressure, suspense, threat, urgency, or danger perceived in the current moment.
- `curiosity`: immediate desire to reveal, inspect, understand, or continue exploring unresolved information.
- `empathy`: momentary care, identification, or emotional resonance with characters and relationships.
- `cognitive_load`: how complex, overloaded, ambiguous, or difficult to process the current scene feels.

## Dynamic State

The pipeline stores:

```text
stable_profile
affective_state_t
current_state_t
```

The affective state changes quickly after each branch. The stable profile changes slowly. The current state combines the two and is used for branch planning.

Conceptually:

```text
image stimulus -> affective delta
stable profile + affective state -> current hidden state
click/feedback -> observation for profile estimation
```

## Running

Dry run:

```powershell
cd dataset_tools
python run_end_to_end_dataset.py --dry-run --profile-limit 1 --topics "Hidden Castle"
```

Full staged run:

```powershell
python dataset_pipeline.py --stage text --profile-limit 1 --topics "Hidden Castle"
python dataset_pipeline.py --stage images --run-dir "dataset_runs\run_YYYYMMDD_HHMMSS"
python dataset_pipeline.py --stage calibrate --run-dir "dataset_runs\run_YYYYMMDD_HHMMSS"
```

End-to-end run:

```powershell
python run_end_to_end_dataset.py --profile-limit 1 --topics "Hidden Castle"
```

Keep all private service settings outside git.

## Curated Root Assets

The repository includes a public root-node asset library at `assets/topic_roots/`.

Each topic contains:

- `root.png`
- `synopsis.txt`
- `root_prompt.txt`
- `root_asset.json`
- `generation_metadata.json`

These root nodes are meant to be shared initial scenes. They should remain topic-only and should not encode any user-specific preference.

Verify the public assets with:

```powershell
python dataset_tools/verify_dataset_format.py --root-assets assets/topic_roots
```

## Generated Files

Typical run layout:

```text
dataset_runs/run_YYYYMMDD_HHMMSS/
  profiles_normalized.jsonl
  topics.json
  manifest.jsonl
  stage_timings.json
  end_to_end_summary.json
  users/
    user_x/
      topic_y/
        tree.json
        root_asset.json
        synopsis.txt
        root_prompt.txt
        images/
```

Generated run directories are ignored by git.
