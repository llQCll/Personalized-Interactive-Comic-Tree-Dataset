from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT_REQUIRED_KEYS = {
    "topic_id",
    "topic",
    "synopsis",
    "world_bible",
    "root_state",
    "root_prompt",
    "root_image",
}

TREE_REQUIRED_KEYS = {
    "tree_id",
    "topic_id",
    "user_id",
    "world_bible",
    "root_image",
    "nodes",
    "edges",
}

NODE_REQUIRED_KEYS = {
    "node_id",
    "depth",
    "image",
    "story_state",
    "stable_profile",
    "affective_state",
    "current_state",
}

EDGE_REQUIRED_KEYS = {
    "edge_id",
    "source_node",
    "target_node",
    "closed_intent",
    "grounding",
    "intent_ranking",
    "slots",
    "decision",
    "expected_affective_delta",
    "expected_profile_delta",
    "story_state_after",
    "generation_prompt",
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fail(errors: list[str], path: Path, message: str) -> None:
    errors.append(f"{path}: {message}")


def has_absolute_or_private_path(value: Any) -> bool:
    if isinstance(value, dict):
        return any(has_absolute_or_private_path(item) for item in value.values())
    if isinstance(value, list):
        return any(has_absolute_or_private_path(item) for item in value)
    if not isinstance(value, str):
        return False
    normalized = value.replace("\\", "/").lower()
    return (
        ":/users/" in normalized
        or normalized.startswith("c:/")
        or "/desktop/" in normalized
        or "dataset_runs/" in normalized
        or "dataset_runs\\" in value.lower()
    )


def verify_root_assets(root_dir: Path) -> list[str]:
    errors: list[str] = []
    if not root_dir.exists():
        fail(errors, root_dir, "root asset directory does not exist")
        return errors

    topic_dirs = sorted(path for path in root_dir.iterdir() if path.is_dir())
    if not topic_dirs:
        fail(errors, root_dir, "no topic root directories found")
        return errors

    for topic_dir in topic_dirs:
        root_png = topic_dir / "root.png"
        root_asset = topic_dir / "root_asset.json"
        synopsis = topic_dir / "synopsis.txt"
        prompt = topic_dir / "root_prompt.txt"
        generation_meta = topic_dir / "generation_metadata.json"

        for required in [root_png, root_asset, synopsis, prompt, generation_meta]:
            if not required.exists():
                fail(errors, required, "missing required root asset file")

        if root_png.exists() and root_png.read_bytes()[:8] != PNG_SIGNATURE:
            fail(errors, root_png, "file is not a valid PNG")

        if synopsis.exists() and not synopsis.read_text(encoding="utf-8").strip():
            fail(errors, synopsis, "synopsis is empty")

        if prompt.exists() and not prompt.read_text(encoding="utf-8").strip():
            fail(errors, prompt, "root prompt is empty")

        if root_asset.exists():
            data = read_json(root_asset)
            missing = sorted(ROOT_REQUIRED_KEYS - set(data))
            if missing:
                fail(errors, root_asset, f"missing keys: {', '.join(missing)}")
            if data.get("topic_id") != topic_dir.name:
                fail(errors, root_asset, "topic_id must match directory name")
            if data.get("root_image") != "root.png":
                fail(errors, root_asset, "root_image must be the relative path root.png")
            if has_absolute_or_private_path(data):
                fail(errors, root_asset, "contains absolute/private local paths")

        if generation_meta.exists():
            data = read_json(generation_meta)
            if data.get("path") != "root.png":
                fail(errors, generation_meta, "path must be the relative path root.png")
            if has_absolute_or_private_path(data):
                fail(errors, generation_meta, "contains absolute/private local paths")

    return errors


def verify_tree(tree_path: Path) -> list[str]:
    errors: list[str] = []
    tree = read_json(tree_path)
    missing = sorted(TREE_REQUIRED_KEYS - set(tree))
    if missing:
        fail(errors, tree_path, f"missing tree keys: {', '.join(missing)}")
        return errors

    nodes = tree.get("nodes", [])
    edges = tree.get("edges", [])
    node_ids = {node.get("node_id") for node in nodes}
    if "n0" not in node_ids:
        fail(errors, tree_path, "missing root node n0")

    for node in nodes:
        node_path = tree_path.with_name(f"node:{node.get('node_id', '<missing>')}")
        missing = sorted(NODE_REQUIRED_KEYS - set(node))
        if missing:
            fail(errors, node_path, f"missing node keys: {', '.join(missing)}")

    for edge in edges:
        edge_path = tree_path.with_name(f"edge:{edge.get('edge_id', '<missing>')}")
        missing = sorted(EDGE_REQUIRED_KEYS - set(edge))
        if missing:
            fail(errors, edge_path, f"missing edge keys: {', '.join(missing)}")
        if edge.get("source_node") not in node_ids:
            fail(errors, edge_path, "source_node does not exist")
        if edge.get("target_node") not in node_ids:
            fail(errors, edge_path, "target_node does not exist")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify public root assets or generated tree JSON format.")
    parser.add_argument("--root-assets", default="", help="Path to public topic root assets.")
    parser.add_argument("--tree", default="", help="Optional tree.json to validate.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    errors: list[str] = []
    if args.root_assets:
        errors.extend(verify_root_assets(Path(args.root_assets)))
    if args.tree:
        errors.extend(verify_tree(Path(args.tree)))
    if not args.root_assets and not args.tree:
        raise SystemExit("Provide --root-assets and/or --tree.")

    if errors:
        print("Format verification failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("Format verification passed.")


if __name__ == "__main__":
    main()
