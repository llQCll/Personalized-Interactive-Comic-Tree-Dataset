from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import error, request


PERSONALITY_DIMS = [
    "goal_progress",
    "mastery_logic",
    "challenge_seeking",
    "social_attachment",
    "cooperative_orientation",
    "world_discovery",
    "role_immersion",
    "aesthetic_customization",
]

AFFECT_DIMS = [
    "pleasure",
    "arousal",
    "dominance",
    "tension",
    "curiosity",
    "empathy",
    "cognitive_load",
]

CLOSED_INTENTS = {
    "zoom_in": "look closer at a specific target",
    "reveal": "reveal hidden information",
    "branch_out": "enter a new place or story branch",
    "reframe": "change perspective while continuing the current event",
    "follow": "follow a character or clue",
    "interact": "interact with a character or object",
}

DEFAULT_TOPICS = [
    "hidden castle",
    "floating market",
    "solar garden",
    "dream archive",
    "mechanical forest",
    "glass observatory",
    "memory railway",
    "moonlit museum",
    "rain city arcade",
    "paper lantern island",
    "clockwork harbor",
    "crystal greenhouse",
]

AFFECT_TO_PERSONALITY = {
    "goal_progress": {"dominance": 0.24, "arousal": 0.08, "cognitive_load": -0.12},
    "mastery_logic": {"curiosity": 0.22, "dominance": 0.12, "cognitive_load": 0.08},
    "challenge_seeking": {"arousal": 0.20, "tension": 0.16, "pleasure": 0.06},
    "social_attachment": {"empathy": 0.26, "pleasure": 0.12},
    "cooperative_orientation": {"empathy": 0.22, "dominance": 0.10, "tension": -0.08},
    "world_discovery": {"curiosity": 0.24, "arousal": 0.08, "cognitive_load": -0.06},
    "role_immersion": {"empathy": 0.14, "pleasure": 0.10, "curiosity": 0.08},
    "aesthetic_customization": {"pleasure": 0.16, "curiosity": 0.10, "dominance": 0.06},
}

STABLE_PROFILE_RUBRIC = {
    "goal_progress": {
        "definition": "Preference for clear objectives, visible progress, unlocked outcomes, and decisive story advancement.",
        "low_anchor": "wanders, observes, or lingers without caring about completion",
        "high_anchor": "chooses routes that solve tasks, unlock results, or push the plot forward",
        "source": "Adapted from Yee's Achievement motivation component.",
    },
    "mastery_logic": {
        "definition": "Preference for rules, mechanisms, causal explanations, puzzles, clues, and system understanding.",
        "low_anchor": "chooses by mood or aesthetics without needing explanation",
        "high_anchor": "inspects symbols, tools, maps, mechanisms, and evidence chains",
        "source": "Adapted from Yee's Mechanics and Advancement subcomponents.",
    },
    "challenge_seeking": {
        "definition": "Preference for risk, pressure, conflict, difficulty, danger, or high-stakes choices.",
        "low_anchor": "avoids pressure and selects safer or gentler continuations",
        "high_anchor": "moves toward danger, conflict, time pressure, or difficult branches",
        "source": "Adapted from Yee's Competition and Achievement-related motivation.",
    },
    "social_attachment": {
        "definition": "Preference for characters, relationships, emotional bonds, facial expressions, and interpersonal stakes.",
        "low_anchor": "treats characters as background and focuses on places, tools, or plot mechanics",
        "high_anchor": "clicks people, expressions, relationships, or emotionally meaningful objects",
        "source": "Adapted from Yee's Social and Relationship components.",
    },
    "cooperative_orientation": {
        "definition": "Preference for helping, repairing, negotiating, protecting, or solving problems with others.",
        "low_anchor": "prefers solo exploration, control, or object-centered action",
        "high_anchor": "chooses rescue, conversation, teamwork, caregiving, or reconciliation",
        "source": "Adapted from Yee's Social teamwork orientation.",
    },
    "world_discovery": {
        "definition": "Preference for entering new places, discovering hidden regions, and expanding the fictional world.",
        "low_anchor": "stays near the current event and avoids expanding the setting",
        "high_anchor": "clicks doors, paths, maps, horizons, portals, or unexplored spaces",
        "source": "Adapted from Yee's Discovery and Immersion components.",
    },
    "role_immersion": {
        "definition": "Preference for acting from inside the protagonist's role and preserving narrative atmosphere and continuity.",
        "low_anchor": "chooses experimentally or as an outside observer",
        "high_anchor": "selects actions that feel in-character and sustain the story mood",
        "source": "Adapted from Yee's Role-Playing and Immersion components.",
    },
    "aesthetic_customization": {
        "definition": "Preference for visual style, beauty, concrete design details, personalization, and creative variation.",
        "low_anchor": "cares mainly about functional outcomes and ignores visual style",
        "high_anchor": "clicks clothing, lighting, decoration, props, composition, or style-defining details",
        "source": "Adapted from Yee's Customization component.",
    },
}

AFFECT_RUBRIC = {
    "pleasure": {
        "definition": "How positive, satisfying, warm, or appealing the current image/story experience feels.",
        "low_anchor": "unpleasant, disappointing, cold, aversive",
        "high_anchor": "pleasant, warm, satisfying, attractive",
        "source": "SAM Pleasure.",
    },
    "arousal": {
        "definition": "How emotionally activated, alert, excited, or energized the user is right now.",
        "low_anchor": "calm, slow, sleepy, emotionally flat",
        "high_anchor": "excited, alert, tense, highly activated",
        "source": "SAM Arousal.",
    },
    "dominance": {
        "definition": "How much the user feels able to understand, control, and influence the situation.",
        "low_anchor": "lost, passive, confused, powerless",
        "high_anchor": "clear, active, confident, in control",
        "source": "SAM Dominance.",
    },
    "tension": {
        "definition": "Pressure, suspense, threat, urgency, or danger perceived in the current moment.",
        "low_anchor": "safe, relaxed, soft, low pressure",
        "high_anchor": "dangerous, suspenseful, urgent, pressured",
        "source": "Task-specific refinement of SAM Arousal.",
    },
    "curiosity": {
        "definition": "Immediate desire to reveal, inspect, understand, or continue exploring unresolved information.",
        "low_anchor": "bored, indifferent, no need to know more",
        "high_anchor": "strongly wants to uncover clues or see what happens next",
        "source": "Task-specific refinement of arousal and dominance for interactive exploration.",
    },
    "empathy": {
        "definition": "Momentary care, identification, or emotional resonance with characters and relationships.",
        "low_anchor": "detached, spectating, emotionally distant",
        "high_anchor": "concerned, connected, protective, emotionally involved",
        "source": "Task-specific social-affective extension of SAM Pleasure.",
    },
    "cognitive_load": {
        "definition": "How complex, overloaded, ambiguous, or difficult to process the current scene feels.",
        "low_anchor": "simple, clear, easy to parse",
        "high_anchor": "dense, confusing, overloaded, hard to decide",
        "source": "Task-specific inverse refinement of SAM Dominance.",
    },
}

SCALE_METADATA = {
    "stable_profile": {
        "name": "Long-term Interactive Motivation Profile",
        "scale": "0.0 to 1.0; 0.0-0.2 very low, 0.2-0.4 low, 0.4-0.6 neutral/uncertain, 0.6-0.8 high, 0.8-1.0 very high",
        "primary_source": "Yee, Motivations for Play in Online Games: Achievement, Social, and Immersion are adapted to interactive visual storytelling.",
        "dimensions": STABLE_PROFILE_RUBRIC,
    },
    "affective_state": {
        "name": "Short-term Affective State",
        "scale": "0.0 to 1.0; internally normalized from SAM-like 1-9 ratings where 0.0 is the low anchor and 1.0 is the high anchor",
        "primary_source": "Bradley & Lang, Self-Assessment Manikin: Pleasure, Arousal, and Dominance are extended with task-specific affective refinements.",
        "dimensions": AFFECT_RUBRIC,
    },
}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def clamp_vector(values: dict[str, float], dims: list[str]) -> dict[str, float]:
    return {dim: round(clamp(float(values.get(dim, 0.5))), 4) for dim in dims}


def stable_hash(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    return int(digest[:12], 16)


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def read_profiles(path: Path, *, limit: int | None = None, user_id: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if user_id is not None and str(row.get("user_id")) != str(user_id):
                continue
            rows.append(row)
            if limit is not None and len(rows) >= limit:
                break
    if user_id is not None and not rows:
        raise RuntimeError(f"Could not find user_id={user_id!r} in {path}")
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(data), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


@dataclass
class PipelineConfig:
    llm_base_url: str = field(default_factory=lambda: os.getenv("DATASET_LLM_BASE_URL", ""))
    llm_api_key: str = field(default_factory=lambda: os.getenv("DATASET_LLM_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("DATASET_LLM_MODEL", "gpt-5.5"))
    image_base_url: str = field(default_factory=lambda: os.getenv("DATASET_IMAGE_BASE_URL", ""))
    image_api_key: str = field(default_factory=lambda: os.getenv("DATASET_IMAGE_API_KEY", ""))
    image_model: str = field(default_factory=lambda: os.getenv("DATASET_IMAGE_MODEL", "gpt-image-2"))
    image_size: str = "1024x1024"
    image_quality: str = "high"
    timeout_seconds: int = 600
    alpha_affect: float = 0.30
    affect_decay: float = 0.75
    calibration_expected_weight: float = 0.60
    branch_depth: int = 5
    tree_nodes: int = 18
    valid_edges_per_tree: int = 17
    root_assets_dir: str = ""


SENSITIVE_CONFIG_FIELDS = {
    "llm_base_url",
    "llm_api_key",
    "image_base_url",
    "image_api_key",
}


def public_config_snapshot(config: PipelineConfig) -> dict[str, Any]:
    return {key: value for key, value in config.__dict__.items() if key not in SENSITIVE_CONFIG_FIELDS}


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 600,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.api_prefix = "" if self.base_url.endswith("/v1") else "/v1"

    def chat_json(self, *, system_prompt: str, user_prompt: str, images: list[str] | None = None) -> dict[str, Any]:
        if not self.base_url:
            raise RuntimeError("LLM base URL is empty. Set DATASET_LLM_BASE_URL or use --dry-run.")
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        if images:
            content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
            for image_path in images:
                content.append({"type": "image_url", "image_url": {"url": image_to_data_url(Path(image_path))}})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        data = self._post_json("/chat/completions", payload)
        content = data["choices"][0]["message"]["content"]
        return parse_json_object(content)

    def generate_image(self, *, prompt: str, output_path: Path, references: list[Path] | None = None, size: str, quality: str) -> dict[str, Any]:
        if not self.base_url:
            raise RuntimeError("Image base URL is empty. Set DATASET_IMAGE_BASE_URL or use --plan-only/--dry-run.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if references and all(path.exists() for path in references):
            return self._generate_image_with_sdk(
                prompt=prompt,
                output_path=output_path,
                references=references,
                size=size,
                quality=quality,
            )
        if references:
            ref_notes = "\n".join(f"Reference image {i + 1}: {path.name}" for i, path in enumerate(references))
            prompt = f"{prompt}\n\nContinuity reference notes:\n{ref_notes}"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "response_format": "b64_json",
        }
        data = self._post_json("/images/generations", payload)
        b64_json = data["data"][0]["b64_json"]
        output_path.write_bytes(base64.b64decode(b64_json))
        return {
            "path": str(output_path),
            "model": self.model,
            "size": size,
            "quality": quality,
            "usage": data.get("usage"),
        }

    def _generate_image_with_sdk(
        self,
        *,
        prompt: str,
        output_path: Path,
        references: list[Path],
        size: str,
        quality: str,
    ) -> dict[str, Any]:
        try:
            from openai import OpenAI
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "Reference-image generation requires the openai Python package. "
                "Install it or run with --plan-only first."
            ) from exc

        client = OpenAI(
            api_key=self.api_key,
            base_url=sdk_base_url(self.base_url),
            timeout=httpx.Timeout(timeout=None, connect=30.0, read=self.timeout_seconds, write=self.timeout_seconds, pool=self.timeout_seconds),
            max_retries=2,
        )
        handles = [path.open("rb") for path in references]
        try:
            response = client.images.edit(
                model=self.model,
                image=handles,
                prompt=prompt,
                size=size,
                quality=quality,
                response_format="b64_json",
            )
        finally:
            for handle in handles:
                handle.close()
        image_data = response.data[0].b64_json
        output_path.write_bytes(base64.b64decode(image_data))
        return {
            "path": str(output_path),
            "model": self.model,
            "size": size,
            "quality": quality,
            "mode": "edit_with_references",
            "reference_images": [str(path) for path in references],
            "usage": serialize_usage(getattr(response, "usage", None)),
        }

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = self.base_url + self.api_prefix + path
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API request failed {exc.code} at {url}: {message}") from exc


def parse_json_object(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if isinstance(content, list):
        text = "\n".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content)
    else:
        text = str(content)
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def is_mock_image_path(path: Path) -> bool:
    return path.with_suffix(".mock.json").exists()


def image_exists_for_stage(path: Path) -> bool:
    return path.exists() or is_mock_image_path(path)


def image_to_data_url(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".") or "png"
    mime = "jpeg" if ext in {"jpg", "jpeg"} else ext
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{data}"


def serialize_usage(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {key: getattr(usage, key) for key in dir(usage) if not key.startswith("_") and isinstance(getattr(usage, key), (str, int, float, bool, type(None)))}


def sdk_base_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    return cleaned if cleaned.endswith("/v1") else cleaned + "/v1"


def load_root_asset(*, topic_id: str, root_assets_dir: str) -> dict[str, Any] | None:
    if not root_assets_dir:
        return None
    assets_dir = Path(root_assets_dir)
    if not assets_dir.is_absolute():
        assets_dir = (Path(__file__).resolve().parent / assets_dir).resolve()
    asset_path = assets_dir / topic_id / "root_asset.json"
    if not asset_path.exists():
        return None
    asset = json.loads(asset_path.read_text(encoding="utf-8-sig"))
    root_image = Path(str(asset.get("root_image", "")))
    if not root_image.is_absolute():
        asset["root_image"] = str((asset_path.parent / root_image).resolve())
    asset["root_asset_path"] = str(asset_path)
    return asset


class DatasetPipeline:
    def __init__(self, *, config: PipelineConfig, output_dir: Path, dry_run: bool = False) -> None:
        self.config = config
        self.output_dir = output_dir
        self.dry_run = dry_run
        self.llm = OpenAICompatibleClient(
            base_url=config.llm_base_url,
            api_key=config.llm_api_key,
            model=config.llm_model,
            timeout_seconds=config.timeout_seconds,
        )
        self.image_client = OpenAICompatibleClient(
            base_url=config.image_base_url,
            api_key=config.image_api_key,
            model=config.image_model,
            timeout_seconds=config.timeout_seconds,
        )

    def run(
        self,
        *,
        profiles_path: Path,
        profile_limit: int,
        profile_user_id: str | None,
        topics: list[str],
        topics_per_user: int,
        generate_images: bool,
    ) -> Path:
        run_dir = self.output_dir / time.strftime("run_%Y%m%d_%H%M%S")
        run_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            run_dir / "config.json",
            public_config_snapshot(self.config) | {"dry_run": self.dry_run, "stage": "all" if generate_images else "text"},
        )

        raw_profiles = read_profiles(profiles_path, limit=profile_limit, user_id=profile_user_id)
        normalized_profiles = [self.normalize_profile(row) for row in raw_profiles]
        write_jsonl(run_dir / "profiles_normalized.jsonl", normalized_profiles)

        topic_specs = [self.build_topic(topic, run_dir, generate_images=generate_images) for topic in topics]
        write_json(run_dir / "topics.json", topic_specs)

        manifest_rows: list[dict[str, Any]] = []
        for user_index, profile in enumerate(normalized_profiles):
            assigned_topics = [topic_specs[(user_index + offset) % len(topic_specs)] for offset in range(topics_per_user)]
            for topic_spec in assigned_topics:
                tree = self.build_tree(profile=profile, topic_spec=topic_spec, run_dir=run_dir, generate_images=generate_images)
                tree_path = run_dir / "users" / f"user_{profile['user_id']}" / topic_spec["topic_id"] / "tree.json"
                write_json(tree_path, tree)
                manifest_rows.append(
                    {
                        "tree_id": tree["tree_id"],
                        "user_id": profile["user_id"],
                        "topic_id": topic_spec["topic_id"],
                        "user_topic_dir": str(tree_path.parent),
                        "tree_path": str(tree_path),
                        "node_count": len(tree["nodes"]),
                        "edge_count": len(tree["edges"]),
                    }
                )
        write_jsonl(run_dir / "manifest.jsonl", manifest_rows)
        return run_dir

    def generate_images_for_run(self, *, run_dir: Path, limit: int | None = None, overwrite: bool = False) -> None:
        manifest_path = run_dir / "manifest.jsonl"
        if not manifest_path.exists():
            raise RuntimeError(f"Missing manifest file: {manifest_path}")
        manifest_rows = read_jsonl(manifest_path, limit=limit)
        topics = {topic["topic_id"]: topic for topic in json.loads((run_dir / "topics.json").read_text(encoding="utf-8"))}

        for topic in topics.values():
            root_path = Path(topic["root_image"])
            if overwrite or not image_exists_for_stage(root_path):
                self.maybe_generate_image(
                    prompt=topic["root_prompt"],
                    output_path=root_path,
                    references=[],
                )

        for row in manifest_rows:
            tree_path = Path(row["tree_path"])
            tree = json.loads(tree_path.read_text(encoding="utf-8"))
            node_by_id = {node["node_id"]: node for node in tree["nodes"]}
            for edge in tree["edges"]:
                target = node_by_id[edge["target_node"]]
                target_path = Path(target["image"])
                source_path = Path(node_by_id[edge["source_node"]]["image"])
                if not overwrite and image_exists_for_stage(target_path):
                    continue
                self.maybe_generate_image(
                    prompt=edge["generation_prompt"],
                    output_path=target_path,
                    references=[source_path],
                )

    def calibrate_run(self, *, run_dir: Path, limit: int | None = None, overwrite: bool = False) -> None:
        manifest_path = run_dir / "manifest.jsonl"
        if not manifest_path.exists():
            raise RuntimeError(f"Missing manifest file: {manifest_path}")
        manifest_rows = read_jsonl(manifest_path, limit=limit)
        for row in manifest_rows:
            tree_path = Path(row["tree_path"])
            tree = json.loads(tree_path.read_text(encoding="utf-8"))
            node_by_id = {node["node_id"]: node for node in tree["nodes"]}
            changed = False
            for edge in tree["edges"]:
                if edge.get("calibration") and not overwrite:
                    continue
                source = node_by_id[edge["source_node"]]
                target = node_by_id[edge["target_node"]]
                source_path = Path(source["image"])
                target_path = Path(target["image"])
                if not image_exists_for_stage(source_path) or not image_exists_for_stage(target_path):
                    edge["calibration"] = {
                        "status": "missing_images",
                        "message": "Calibration skipped because source or target image does not exist.",
                    }
                    changed = True
                    continue
                calibration = self.calibrate_edge(edge=edge, source_node=source, target_node=target)
                edge.update(calibration)
                changed = True
            if changed:
                tree["calibration_status"] = {
                    "calibrated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "expected_weight": self.config.calibration_expected_weight,
                }
                write_json(tree_path, tree)

    def normalize_profile(self, raw: dict[str, Any]) -> dict[str, Any]:
        raw_text = raw.get("profile", "")
        user_id = str(raw.get("user_id", stable_hash(json.dumps(raw, ensure_ascii=False))))
        if self.dry_run:
            return mock_normalized_profile(user_id=user_id, raw_text=raw_text)

        system_prompt = (
            "You convert raw user preference notes into task-specific dimensions for an "
            "interactive comic generation dataset. Return only valid JSON."
        )
        user_prompt = f"""
Raw profile text is auxiliary evidence, not the final label.
Map it into an 8D long-term interactive motivation profile in [0, 1],
a neutral 7D short-term affective state in [0, 1], and one concise English profile summary.

Stable motivation scale metadata:
{json_dumps(SCALE_METADATA["stable_profile"])}

Short-term affect scale metadata:
{json_dumps(SCALE_METADATA["affective_state"])}

Scoring rule:
- 0.0-0.2: very low evidence for the high anchor.
- 0.2-0.4: low.
- 0.4-0.6: neutral, mixed, or insufficient evidence.
- 0.6-0.8: high.
- 0.8-1.0: very high.
- The initial affective_state_0 should usually be neutral 0.5 for every dimension unless the raw profile strongly implies a persistent baseline.
- Do not diagnose clinical personality. These are task-specific creative-interactive motivations.

Return schema:
{{
  "stable_profile": {{"goal_progress": 0.5, "...": 0.5}},
  "affective_state_0": {{"pleasure": 0.5, "...": 0.5}},
  "profile_summary": "...",
  "dimension_rationales": {{"goal_progress": "..."}}
}}

Raw user id: {user_id}
Raw profile:
{raw_text[:6000]}
"""
        data = self.llm.chat_json(system_prompt=system_prompt, user_prompt=user_prompt)
        return {
            "user_id": user_id,
            "raw_profile": raw_text,
            "stable_profile": clamp_vector(data.get("stable_profile", {}), PERSONALITY_DIMS),
            "affective_state_0": clamp_vector(data.get("affective_state_0", {}), AFFECT_DIMS),
            "profile_summary": str(data.get("profile_summary", "")),
            "dimension_rationales": data.get("dimension_rationales", {}),
        }

    def build_topic(self, topic: str, run_dir: Path, *, generate_images: bool) -> dict[str, Any]:
        topic_id = slugify(topic)
        root_asset = load_root_asset(topic_id=topic_id, root_assets_dir=self.config.root_assets_dir)
        if root_asset:
            spec = root_asset
            spec["topic_id"] = topic_id
            spec["topic"] = spec.get("topic", topic)
            spec.setdefault("root_state", {"location": f"shared opening scene for {topic}", "narrative_status": spec.get("synopsis", "")})
            spec.setdefault("world_bible", {
                "premise": spec.get("synopsis", ""),
                "visual_style": "Shared topic root panel loaded from a curated root asset library.",
                "main_entities": [],
                "protected_entities": ["consistent protagonist", "signature object or scene anchor"],
                "continuity_rules": [
                    "The root panel is shared by all users under this topic.",
                    "The root image must be topic-only and must not contain user preference information.",
                ],
            })
            return spec
        if self.dry_run:
            spec = mock_topic(topic=topic, topic_id=topic_id)
        else:
            system_prompt = "Create compact world bibles for interactive branching comics. Return only valid JSON."
            user_prompt = f"""
Create a shared topic world bible and root panel prompt.
The root image must be identical for all users under this topic. Downstream branches will diverge by user profile.
The root_prompt must be topic-only: use only the premise, protected entities, continuity rules, and scene logic.
Do not use user profile, preference dimensions, affective state, personalized pacing, or personalized visual emphasis in the root image.

Topic: {topic}

Return schema:
{{
  "topic_id": "{topic_id}",
  "topic": "{topic}",
  "world_bible": {{
    "premise": "...",
    "visual_style": "...",
    "main_entities": ["..."],
    "protected_entities": ["consistent protagonist", "key object"],
    "continuity_rules": ["..."]
  }},
  "root_state": {{"location": "...", "narrative_status": "..."}},
  "root_prompt": "image generation prompt for the shared root panel"
}}
"""
            spec = self.llm.chat_json(system_prompt=system_prompt, user_prompt=user_prompt)
            spec["topic_id"] = topic_id
            spec["topic"] = topic

        root_path = run_dir / "images" / topic_id / "root.png"
        if generate_images:
            self.maybe_generate_image(
                prompt=spec["root_prompt"],
                output_path=root_path,
                references=[],
            )
        spec["root_image"] = str(root_path)
        return spec

    def build_tree(self, *, profile: dict[str, Any], topic_spec: dict[str, Any], run_dir: Path, generate_images: bool) -> dict[str, Any]:
        tree_id = f"{topic_spec['topic_id']}_user_{profile['user_id']}"
        user_topic_dir = run_dir / "users" / f"user_{profile['user_id']}" / topic_spec["topic_id"]
        user_images_dir = user_topic_dir / "images"
        user_images_dir.mkdir(parents=True, exist_ok=True)
        source_root_image = Path(topic_spec["root_image"])
        local_root_image = user_images_dir / "n0.png"
        if source_root_image.exists():
            shutil.copy2(source_root_image, local_root_image)
        else:
            local_root_image = source_root_image
        write_json(
            user_topic_dir / "root_asset.json",
            {
                "topic_id": topic_spec["topic_id"],
                "topic": topic_spec["topic"],
                "synopsis": topic_spec.get("synopsis", topic_spec.get("world_bible", {}).get("premise", "")),
                "root_prompt": topic_spec.get("root_prompt", ""),
                "source_root_image": str(source_root_image),
                "local_root_image": str(local_root_image),
            },
        )
        (user_topic_dir / "synopsis.txt").write_text(
            str(topic_spec.get("synopsis", topic_spec.get("world_bible", {}).get("premise", ""))),
            encoding="utf-8",
        )
        (user_topic_dir / "root_prompt.txt").write_text(str(topic_spec.get("root_prompt", "")), encoding="utf-8")
        root_node = {
            "node_id": "n0",
            "user_id": profile["user_id"],
            "depth": 0,
            "image": str(local_root_image),
            "story_state": topic_spec["root_state"],
            "stable_profile": profile["stable_profile"],
            "affective_state": profile["affective_state_0"],
            "current_state": compute_current_state(
                stable_profile=profile["stable_profile"],
                affective_state=profile["affective_state_0"],
                alpha=self.config.alpha_affect,
            ),
            "profile_summary": profile["profile_summary"],
        }

        tree = {
            "tree_id": tree_id,
            "topic_id": topic_spec["topic_id"],
            "user_id": profile["user_id"],
            "scale_metadata": SCALE_METADATA,
            "world_bible": topic_spec["world_bible"],
            "root_image": str(local_root_image),
            "nodes": [root_node],
            "edges": [],
            "oos_regions": [],
            "sampled_paths": [],
        }

        expansion_plan = build_irregular_expansion_plan(
            max_depth=self.config.branch_depth,
            max_nodes=self.config.tree_nodes,
        )
        node_by_id = {"n0": root_node}
        for source_id, target_ids in expansion_plan:
            source = node_by_id[source_id]
            branch_plan = self.plan_branches(
                tree_id=tree_id,
                topic_spec=topic_spec,
                profile=profile,
                source_node=source,
                target_ids=target_ids,
            )
            tree["oos_regions"].append(branch_plan["oos_region"])
            for index, target_id in enumerate(target_ids):
                edge = branch_plan["edges"][index]
                edge["edge_id"] = f"{source_id}_to_{target_id}"
                edge["source_node"] = source_id
                edge["target_node"] = target_id
                target_node = self.realize_target_node(
                    tree_id=tree_id,
                    topic_spec=topic_spec,
                    source_node=source,
                    target_id=target_id,
                    edge=edge,
                    run_dir=run_dir,
                    generate_images=generate_images,
                )
                node_by_id[target_id] = target_node
                tree["nodes"].append(target_node)
                edge["target_image"] = target_node["image"]
                tree["edges"].append(edge)

        tree["sampled_paths"] = sample_paths(tree["edges"])
        return tree

    def plan_branches(
        self,
        *,
        tree_id: str,
        topic_spec: dict[str, Any],
        profile: dict[str, Any],
        source_node: dict[str, Any],
        target_ids: list[str],
    ) -> dict[str, Any]:
        if self.dry_run:
            return mock_branch_plan(target_ids=target_ids, source_node=source_node)

        system_prompt = (
            "You design branch annotations for a personalized interactive comic dataset. "
            "Return valid JSON only. Branches must be diverse yet consistent with protected entities."
        )
        user_prompt = f"""
Plan branches before image generation. Use the current dynamic user state, not only the stable profile.
Make endings diverse while preserving protagonist, key objects, location logic, and visual continuity.
This dataset is used for contrastive personalization experiments. Make personalization visible in the branch design:
- If the user has high goal_progress, create branches with clear objectives, visible progress, unlocked results, and decisive story advancement.
- If the user has high mastery_logic, create branches with mechanisms, symbols, maps, tools, clue chains, and readable causal evidence.
- If the user has high challenge_seeking, create branches with risk, pressure, conflict, danger, or difficult tradeoffs while staying safe and non-graphic.
- If the user has high social_attachment or cooperative_orientation, create branches with interpersonal stakes, helping, conversation, rescue, repair, or emotionally legible character choices.
- If the user has high world_discovery, create branches that enter new locations, hidden regions, or broader world systems.
- If the user has high role_immersion, preserve in-character action, atmosphere, and narrative continuity.
- If the user has high aesthetic_customization, emphasize style-defining details, props, lighting, costume, composition, and creative visual variation.
- Do not merely change wording. The target image prompt should alter composition, focal objects, interaction target, emotional tone, and story consequence according to the user state.
- Keep the root image shared and topic-only; personalization starts from branch planning after the root.

Tree: {tree_id}
Topic world bible:
{json_dumps(topic_spec["world_bible"])}

Source node:
{json_dumps(source_node)}

User stable profile:
{json_dumps(profile["stable_profile"])}

Current affective state and current state:
{json_dumps({"affective_state": source_node["affective_state"], "current_state": source_node["current_state"]})}

Scale metadata and scoring anchors:
{json_dumps(SCALE_METADATA)}

Create {len(target_ids)} valid branches and 1 OOS/weak region.
Each valid branch needs closed_intent, grounding, semi-open intent ranking, slots, expected_affective_delta, expected_profile_delta,
story_state_after, and a detailed image prompt for gpt-image-2.
The detailed image prompt must be conditioned on the current dynamic user state:
adapt visual emphasis, pacing, detail density, emotional tone, and branch content to the user's stable profile,
current affective state, and current composite state. Do not write profile dimension names or user-model metadata
as visible text in the image.

Return schema:
{{
  "edges": [
    {{
      "branch_label": "...",
      "closed_intent": "zoom_in | reveal | branch_out | reframe | follow | interact",
      "grounding": {{"target_box": [0.1,0.1,0.3,0.3], "target_label": "...", "target_caption": "..."}},
      "intent_ranking": [{{"intent": "...", "score": 0.9}}],
      "slots": {{"action": "...", "target": "...", "narrative_goal": "...", "mood": "...", "continuity_constraint": "...", "scope": "next_panel"}},
      "decision": {{"type": "accept", "confidence": 0.8, "requires_confirmation": false, "is_oos": false}},
      "profile_signal": {{"mastery_logic": 0.2}},
      "expected_affective_delta": {{"curiosity": 0.1}},
      "expected_profile_delta": {{"mastery_logic": 0.02}},
      "story_state_after": {{"location": "...", "narrative_status": "..."}},
      "generation_prompt": "..."
    }}
  ],
  "oos_region": {{
    "grounding": {{"target_box": [0.0,0.0,0.1,0.1], "target_label": "low-salience background"}},
    "decision": {{"type": "oos", "confidence": 0.2, "requires_confirmation": false, "is_oos": true}}
  }}
}}
"""
        data = self.llm.chat_json(system_prompt=system_prompt, user_prompt=user_prompt, images=[source_node["image"]] if Path(source_node["image"]).exists() else None)
        data["edges"] = data.get("edges", [])[: len(target_ids)]
        while len(data["edges"]) < len(target_ids):
            data["edges"].append(mock_branch_plan(target_ids=["x"], source_node=source_node)["edges"][0])
        for edge in data["edges"]:
            normalize_expected_delta_fields(edge)
            edge["closed_intent"] = normalize_closed_intent(edge)
        return data

    def calibrate_edge(self, *, edge: dict[str, Any], source_node: dict[str, Any], target_node: dict[str, Any]) -> dict[str, Any]:
        expected_affective_delta = get_expected_affective_delta(edge)
        expected_profile_delta = get_expected_profile_delta(edge)
        if self.dry_run:
            observed_affective_delta = {key: round(value * 0.9, 4) for key, value in expected_affective_delta.items()}
            observed_profile_delta = {key: round(value * 0.9, 4) for key, value in expected_profile_delta.items()}
            profile_alignment = 0.9
            affect_alignment = 0.9
            needs_revision = False
            visual_notes = "Dry-run calibration mirrors expected deltas."
        else:
            system_prompt = (
                "You are a strict VL calibration annotator for an interactive comic dataset. "
                "Compare the source image, target image, branch plan, and expected deltas. "
                "Return only valid JSON."
            )
            user_prompt = f"""
Assess whether the generated target image visually supports the planned branch and expected user-state deltas.

Personality dimensions: {PERSONALITY_DIMS}
Affect dimensions: {AFFECT_DIMS}
Scale metadata:
{json_dumps(SCALE_METADATA)}

Source node:
{json_dumps(source_node)}

Target node:
{json_dumps(target_node)}

Branch edge:
{json_dumps(edge)}

Expected affective delta:
{json_dumps(expected_affective_delta)}

Expected profile delta:
{json_dumps(expected_profile_delta)}

Return schema:
{{
  "observed_affective_delta": {{"pleasure": 0.0, "...": 0.0}},
  "observed_profile_delta": {{"goal_progress": 0.0, "...": 0.0}},
  "delta_alignment": {{
    "profile_alignment": 0.0,
    "affect_alignment": 0.0,
    "image_intent_alignment": 0.0,
    "continuity_alignment": 0.0,
    "ending_diversity": 0.0,
    "needs_revision": false
  }},
  "visual_notes": "...",
  "revision_suggestion": "..."
}}
Scores are in [0,1]. Deltas should be small signed values, usually between -0.2 and 0.2.
"""
            data = self.llm.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                images=[source_node["image"], target_node["image"]],
            )
            observed_affective_delta = coerce_delta(data.get("observed_affective_delta", {}), AFFECT_DIMS)
            observed_profile_delta = coerce_delta(data.get("observed_profile_delta", {}), PERSONALITY_DIMS)
            alignment = data.get("delta_alignment", {})
            profile_alignment = clamp(float(alignment.get("profile_alignment", 0.0)))
            affect_alignment = clamp(float(alignment.get("affect_alignment", 0.0)))
            needs_revision = bool(alignment.get("needs_revision", profile_alignment < 0.6 or affect_alignment < 0.6))
            visual_notes = str(data.get("visual_notes", ""))

        final_affective_delta = blend_deltas(
            expected=expected_affective_delta,
            observed=observed_affective_delta,
            dims=AFFECT_DIMS,
            expected_weight=self.config.calibration_expected_weight,
        )
        final_profile_delta = blend_deltas(
            expected=expected_profile_delta,
            observed=observed_profile_delta,
            dims=PERSONALITY_DIMS,
            expected_weight=self.config.calibration_expected_weight,
        )
        return {
            "expected_affective_delta": expected_affective_delta,
            "expected_profile_delta": expected_profile_delta,
            "observed_affective_delta": observed_affective_delta,
            "observed_profile_delta": observed_profile_delta,
            "final_affective_delta": final_affective_delta,
            "final_profile_delta": final_profile_delta,
            "delta_alignment": {
                "profile_alignment": profile_alignment,
                "affect_alignment": affect_alignment,
                "needs_revision": needs_revision,
            },
            "calibration": {
                "status": "calibrated",
                "visual_notes": visual_notes,
                "expected_weight": self.config.calibration_expected_weight,
            },
        }

    def realize_target_node(
        self,
        *,
        tree_id: str,
        topic_spec: dict[str, Any],
        source_node: dict[str, Any],
        target_id: str,
        edge: dict[str, Any],
        run_dir: Path,
        generate_images: bool,
    ) -> dict[str, Any]:
        affective_state_after = update_affective_state(
            before=source_node["affective_state"],
            delta=get_expected_affective_delta(edge),
            decay=self.config.affect_decay,
        )
        stable_profile_after = update_stable_profile(
            before=source_node["stable_profile"],
            delta=get_expected_profile_delta(edge),
        )
        current_state_after = compute_current_state(
            stable_profile=stable_profile_after,
            affective_state=affective_state_after,
            alpha=self.config.alpha_affect,
        )
        image_path = run_dir / "users" / f"user_{source_node.get('user_id', '')}" / topic_spec["topic_id"] / "images" / f"{target_id}.png"
        if generate_images:
            self.maybe_generate_image(
                prompt=edge["generation_prompt"],
                output_path=image_path,
                references=[Path(source_node["image"])],
            )
        return {
            "node_id": target_id,
            "user_id": source_node.get("user_id", ""),
            "depth": int(source_node.get("depth", 0)) + 1,
            "image": str(image_path),
            "story_state": edge.get("story_state_after", {}),
            "stable_profile": stable_profile_after,
            "affective_state": affective_state_after,
            "current_state": current_state_after,
            "profile_summary": summarize_state(stable_profile_after, affective_state_after),
        }

    def maybe_generate_image(self, *, prompt: str, output_path: Path, references: list[Path]) -> None:
        if self.dry_run:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            write_json(output_path.with_suffix(".mock.json"), {"prompt": prompt, "references": [str(path) for path in references]})
            return
        metadata = self.image_client.generate_image(
            prompt=prompt,
            output_path=output_path,
            references=references,
            size=self.config.image_size,
            quality=self.config.image_quality,
        )
        write_json(output_path.with_suffix(".json"), metadata)


def compute_current_state(*, stable_profile: dict[str, float], affective_state: dict[str, float], alpha: float) -> dict[str, float]:
    current: dict[str, float] = {}
    for personality_dim in PERSONALITY_DIMS:
        affect_delta = 0.0
        for affect_dim, weight in AFFECT_TO_PERSONALITY.get(personality_dim, {}).items():
            affect_delta += weight * (float(affective_state.get(affect_dim, 0.5)) - 0.5)
        current[personality_dim] = round(clamp(float(stable_profile.get(personality_dim, 0.5)) + alpha * affect_delta), 4)
    return current


def update_affective_state(*, before: dict[str, float], delta: dict[str, Any], decay: float) -> dict[str, float]:
    updated: dict[str, float] = {}
    for dim in AFFECT_DIMS:
        centered = float(before.get(dim, 0.5)) - 0.5
        next_value = 0.5 + decay * centered + float(delta.get(dim, 0.0))
        updated[dim] = round(clamp(next_value), 4)
    return updated


def update_stable_profile(*, before: dict[str, float], delta: dict[str, Any], beta: float = 0.06) -> dict[str, float]:
    updated: dict[str, float] = {}
    for dim in PERSONALITY_DIMS:
        next_value = float(before.get(dim, 0.5)) + beta * float(delta.get(dim, 0.0))
        updated[dim] = round(clamp(next_value), 4)
    return updated


def coerce_delta(values: dict[str, Any], dims: list[str], low: float = -0.2, high: float = 0.2) -> dict[str, float]:
    return {dim: round(max(low, min(high, float(values.get(dim, 0.0)))), 4) for dim in dims if dim in values}


def normalize_expected_delta_fields(edge: dict[str, Any]) -> None:
    if "expected_affective_delta" not in edge:
        edge["expected_affective_delta"] = edge.get("affective_delta", {})
    if "expected_profile_delta" not in edge:
        edge["expected_profile_delta"] = edge.get("profile_update", {})


def normalize_closed_intent(edge: dict[str, Any]) -> str:
    value = str(edge.get("closed_intent", "")).strip().lower()
    branch = str(edge.get("branch_label", "")).lower()
    action = str(edge.get("slots", {}).get("action", "")).lower()
    goal = str(edge.get("slots", {}).get("narrative_goal", "")).lower()
    target = str(edge.get("grounding", {}).get("target_label", "")).lower()
    caption = str(edge.get("grounding", {}).get("target_caption", "")).lower()
    intents = " ".join(str(item.get("intent", "")) for item in edge.get("intent_ranking", [])).lower()
    text = " ".join([branch, action, goal, target, caption, intents])

    # Closed intent is a normalized task label, not a verbatim model suggestion.
    # Prioritize the user's observable operation: inspect, use, enter, reveal, or follow.
    explicit_reveal = any(
        word in text
        for word in [
            "hidden door",
            "concealed door",
            "moonwell door",
            "secret entrance",
            "hidden mechanism",
            "concealed mechanism",
            "hidden route",
            "concealed route",
        ]
    ) or ("map-fragment" in text and any(word in text for word in ["side trail", "alternate route", "side approach", "route"]))
    movement_into_new_space = any(
        word in action or word in branch
        for word in [
            "enter ",
            "step into",
            "step through",
            "step under",
            "move into",
            "go through",
            "through the side arch",
            "into the side arch",
            "under the side arch",
            "side passage",
            "corridor",
        ]
    )
    object_operation = any(
        word in action
        for word in ["raise", "hold", "bring", "test", "use", "align", "place", "touch", "trace", "kneel"]
    )
    close_inspection = any(word in action for word in ["inspect", "examine", "study", "look", "search", "assess"])

    if explicit_reveal:
        return "reveal"
    if close_inspection:
        return "zoom_in"
    if movement_into_new_space:
        return "branch_out"
    if object_operation:
        return "interact"
    if any(word in text for word in ["new place", "new branch", "new location"]):
        return "branch_out"
    if any(word in text for word in ["inspect", "examine", "look", "closer", "detail", "study"]):
        return "zoom_in"
    if any(word in text for word in ["follow character", "follow the character", "follow guide", "follow her", "follow him"]):
        return "follow"
    if any(word in text for word in ["follow", "pursue"]):
        return "follow"
    if any(word in text for word in ["interact", "speak", "open"]):
        return "interact"
    if any(word in text for word in ["view", "angle", "perspective", "continue", "watch"]):
        return "reframe"
    return value if value in CLOSED_INTENTS else "reframe"


def get_expected_affective_delta(edge: dict[str, Any]) -> dict[str, float]:
    return coerce_delta(edge.get("expected_affective_delta", edge.get("affective_delta", {})), AFFECT_DIMS)


def get_expected_profile_delta(edge: dict[str, Any]) -> dict[str, float]:
    return coerce_delta(edge.get("expected_profile_delta", edge.get("profile_update", {})), PERSONALITY_DIMS)


def blend_deltas(
    *,
    expected: dict[str, float],
    observed: dict[str, float],
    dims: list[str],
    expected_weight: float,
) -> dict[str, float]:
    blended: dict[str, float] = {}
    for dim in dims:
        if dim not in expected and dim not in observed:
            continue
        value = expected_weight * float(expected.get(dim, 0.0)) + (1.0 - expected_weight) * float(observed.get(dim, 0.0))
        blended[dim] = round(max(-0.2, min(0.2, value)), 4)
    return blended


def summarize_state(stable_profile: dict[str, float], affective_state: dict[str, float]) -> str:
    strongest_profile = sorted(stable_profile.items(), key=lambda item: item[1], reverse=True)[:2]
    strongest_affect = sorted(affective_state.items(), key=lambda item: item[1], reverse=True)[:2]
    profile_text = ", ".join(name.replace("_", " ") for name, _ in strongest_profile)
    affect_text = ", ".join(name.replace("_", " ") for name, _ in strongest_affect)
    return f"The user currently leans toward {profile_text}, with a short-term affective state marked by {affect_text}."


def build_irregular_expansion_plan(*, max_depth: int, max_nodes: int) -> list[tuple[str, list[str]]]:
    """Create a deterministic non-complete branching tree with the requested maximum depth."""
    if max_depth < 1:
        return []
    max_nodes = max(1, max_nodes)
    template_edges = [
        ("n0", "n1"), ("n0", "n2"), ("n0", "n3"),
        ("n1", "n4"), ("n1", "n5"),
        ("n2", "n6"),
        ("n3", "n7"), ("n3", "n8"),
        ("n4", "n9"),
        ("n5", "n10"), ("n5", "n11"),
        ("n6", "n12"),
        ("n9", "n13"),
        ("n13", "n14"),
        ("n10", "n15"),
        ("n15", "n16"),
        ("n8", "n17"),
    ]
    depths = {"n0": 0}
    plan_map: dict[str, list[str]] = {}
    for source, target in template_edges:
        target_index = int(target[1:])
        if target_index >= max_nodes:
            continue
        if source not in depths:
            continue
        target_depth = depths[source] + 1
        if target_depth > max_depth:
            continue
        depths[target] = target_depth
        plan_map.setdefault(source, []).append(target)

    next_index = max([int(node[1:]) for node in depths if node.startswith("n")] or [0]) + 1
    expandable = [node for node, depth in sorted(depths.items(), key=lambda item: (item[1], item[0])) if depth < max_depth]
    cursor = 0
    while next_index < max_nodes and expandable:
        source = expandable[cursor % len(expandable)]
        cursor += 1
        if depths[source] >= max_depth:
            continue
        child = f"n{next_index}"
        next_index += 1
        depths[child] = depths[source] + 1
        plan_map.setdefault(source, []).append(child)
        if depths[child] < max_depth:
            expandable.append(child)

    return [(source, children) for source, children in plan_map.items()]


def sample_paths(edges: list[dict[str, Any]]) -> list[list[str]]:
    children: dict[str, list[str]] = {}
    for edge in edges:
        children.setdefault(edge["source_node"], []).append(edge["target_node"])
    paths: list[list[str]] = []

    def walk(node: str, path: list[str]) -> None:
        if node not in children:
            paths.append(path)
            return
        for child in children[node]:
            walk(child, path + [child])

    walk("n0", ["n0"])
    return paths


def node_depth(node_id: str) -> int:
    if node_id == "n0":
        return 0
    digits = "".join(char for char in node_id if char.isdigit())
    return 1 if not digits else min(5, int(digits))


def slugify(text: str) -> str:
    safe = "".join(char.lower() if char.isalnum() else "_" for char in text).strip("_")
    return "_".join(part for part in safe.split("_") if part)[:64] or "topic"


def mock_normalized_profile(*, user_id: str, raw_text: str) -> dict[str, Any]:
    rng = random.Random(stable_hash(user_id + raw_text))
    stable = {dim: round(0.25 + rng.random() * 0.60, 4) for dim in PERSONALITY_DIMS}
    affect = {dim: 0.5 for dim in AFFECT_DIMS}
    return {
        "user_id": user_id,
        "raw_profile": raw_text,
        "stable_profile": stable,
        "affective_state_0": affect,
        "profile_summary": summarize_state(stable, affect),
        "dimension_rationales": {dim: "Dry-run deterministic profile value from auxiliary raw profile." for dim in PERSONALITY_DIMS},
    }


def mock_topic(*, topic: str, topic_id: str) -> dict[str, Any]:
    return {
        "topic_id": topic_id,
        "topic": topic,
        "world_bible": {
            "premise": f"A branching interactive comic about {topic}.",
            "visual_style": "bright cinematic fantasy with clear readable interactive regions",
            "main_entities": ["consistent protagonist", "signature object", "central location"],
            "protected_entities": ["consistent protagonist", "signature object"],
            "continuity_rules": [
                "Keep the protagonist recognizable across all panels.",
                "Preserve the signature object and topic-specific environment.",
                "Make branch endings visually diverse while sharing the same world logic.",
            ],
        },
        "root_state": {"location": f"opening scene of {topic}", "narrative_status": "the protagonist arrives at the shared starting point"},
        "root_prompt": f"Create a shared root comic panel for {topic}. Bright cinematic fantasy, clear protagonist, signature object, and multiple visually readable possible interaction targets.",
    }


def mock_branch_plan(*, target_ids: list[str], source_node: dict[str, Any]) -> dict[str, Any]:
    templates = [
        (
            "solve a symbolic mechanism",
            "inspect_mechanism",
            {"mastery_logic": 0.8, "goal_progress": 0.5},
            {"curiosity": 0.08, "dominance": 0.04, "cognitive_load": 0.03},
        ),
        (
            "enter a hidden new area",
            "explore_area",
            {"world_discovery": 0.8, "challenge_seeking": 0.4},
            {"curiosity": 0.07, "arousal": 0.05, "tension": 0.03},
        ),
        (
            "help the central character",
            "help_character",
            {"social_attachment": 0.8, "cooperative_orientation": 0.6},
            {"empathy": 0.08, "pleasure": 0.04, "tension": -0.02},
        ),
        (
            "shape the scene through a style-defining object",
            "customize_scene",
            {"aesthetic_customization": 0.8, "role_immersion": 0.5},
            {"pleasure": 0.07, "curiosity": 0.04, "dominance": 0.03},
        ),
    ]
    edges = []
    for index, _target_id in enumerate(target_ids):
        label, intent, profile_signal, affect_delta = templates[(node_depth(source_node["node_id"]) + index) % len(templates)]
        edges.append(
            {
                "branch_label": label,
                "closed_intent": normalize_closed_intent({"branch_label": label, "intent_ranking": [{"intent": intent}], "slots": {"action": intent}}),
                "grounding": {
                    "target_box": [0.15 + index * 0.35, 0.25, 0.38 + index * 0.35, 0.62],
                    "target_label": label,
                    "target_caption": f"A visible target that invites the user to {label}.",
                },
                "intent_ranking": [
                    {"intent": intent, "score": 0.88},
                    {"intent": "reveal_clue", "score": 0.68},
                    {"intent": "continue_story", "score": 0.46},
                ],
                "slots": {
                    "action": intent.split("_")[0],
                    "target": label,
                    "narrative_goal": label,
                    "mood": "curious and cinematic",
                    "continuity_constraint": "preserve protagonist, signature object, and previous location logic",
                    "scope": "next_panel",
                },
                "decision": {"type": "accept", "confidence": 0.82, "requires_confirmation": False, "is_oos": False},
                "profile_signal": profile_signal,
                "expected_affective_delta": affect_delta,
                "expected_profile_delta": {key: value * 0.1 for key, value in profile_signal.items()},
                "story_state_after": {
                    "location": f"personalized continuation after {label}",
                    "narrative_status": f"The protagonist chooses to {label}.",
                },
                "generation_prompt": (
                    f"Create the next comic panel after the user chose to {label}. "
                    "Keep the protagonist and signature object consistent. Make this branch visually distinct, readable, and coherent with the previous panel."
                ),
            }
        )
    return {
        "edges": edges,
        "oos_region": {
            "grounding": {"target_box": [0.02, 0.02, 0.12, 0.12], "target_label": "low-salience background"},
            "decision": {"type": "oos", "confidence": 0.2, "requires_confirmation": False, "is_oos": True},
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a personalized interactive comic tree dataset.")
    parser.add_argument("--stage", choices=["text", "images", "calibrate", "all"], default="text", help="Pipeline stage to run.")
    parser.add_argument("--profiles", default="user_profiles(1).jsonl", help="Input JSONL profile file.")
    parser.add_argument("--output-dir", default="dataset_runs", help="Output directory.")
    parser.add_argument("--run-dir", default="", help="Existing run directory for --stage images.")
    parser.add_argument("--profile-limit", type=int, default=2, help="Number of users to process.")
    parser.add_argument("--profile-user-id", default="", help="Only process this user_id from the profile JSONL.")
    parser.add_argument("--topics", nargs="*", default=DEFAULT_TOPICS[:2], help="Topic names.")
    parser.add_argument("--topics-per-user", type=int, default=1, help="How many topics each user receives.")
    parser.add_argument("--dry-run", action="store_true", help="Use deterministic mock planning and write mock image metadata.")
    parser.add_argument("--overwrite-images", action="store_true", help="Regenerate existing image files in --stage images.")
    parser.add_argument("--overwrite-calibration", action="store_true", help="Re-run calibration for already calibrated edges.")
    parser.add_argument("--image-size", default="1024x1024")
    parser.add_argument("--image-quality", default="high")
    parser.add_argument("--root-assets-dir", default="", help="Optional curated topic root assets folder.")
    parser.add_argument("--branch-depth", type=int, default=5, help="Maximum tree depth, with root at depth 0.")
    parser.add_argument("--tree-nodes", type=int, default=18, help="Maximum number of nodes per user-topic tree.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = Path(__file__).resolve().parent
    config = PipelineConfig(image_size=args.image_size, image_quality=args.image_quality)
    config.root_assets_dir = args.root_assets_dir
    config.branch_depth = args.branch_depth
    config.tree_nodes = args.tree_nodes
    config.valid_edges_per_tree = max(0, args.tree_nodes - 1)
    pipeline = DatasetPipeline(
        config=config,
        output_dir=(base_dir / args.output_dir).resolve(),
        dry_run=args.dry_run,
    )
    if args.stage in {"images", "calibrate"}:
        if not args.run_dir:
            raise SystemExit(f"--stage {args.stage} requires --run-dir")
        run_dir = Path(args.run_dir)
        if not run_dir.is_absolute():
            run_dir = (base_dir / run_dir).resolve()
    if args.stage == "images":
        pipeline.generate_images_for_run(
            run_dir=run_dir,
            limit=args.profile_limit if args.profile_limit > 0 else None,
            overwrite=args.overwrite_images,
        )
        return
    if args.stage == "calibrate":
        pipeline.calibrate_run(
            run_dir=run_dir,
            limit=args.profile_limit if args.profile_limit > 0 else None,
            overwrite=args.overwrite_calibration,
        )
        return
    pipeline.run(
        profiles_path=(base_dir / args.profiles).resolve(),
        profile_limit=args.profile_limit,
        profile_user_id=args.profile_user_id or None,
        topics=args.topics,
        topics_per_user=args.topics_per_user,
        generate_images=args.stage == "all",
    )


if __name__ == "__main__":
    main()
