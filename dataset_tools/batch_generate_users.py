from __future__ import annotations

import argparse
import concurrent.futures
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from dataset_pipeline import read_profiles, slugify, write_json, write_jsonl


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_path(base_dir: Path, path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else (base_dir / path).resolve()


def available_topics(root_assets_dir: Path) -> list[str]:
    topics = []
    for topic_dir in sorted(path for path in root_assets_dir.iterdir() if path.is_dir()):
        asset_path = topic_dir / "root_asset.json"
        if asset_path.exists():
            asset = read_json(asset_path)
            topics.append(str(asset.get("topic") or topic_dir.name.replace("_", " ").title()))
        else:
            topics.append(topic_dir.name.replace("_", " ").title())
    if not topics:
        raise RuntimeError(f"No topics found under {root_assets_dir}")
    return topics


def stable_topic_sample(*, user_id: str, topics: list[str], count: int, seed: int) -> list[str]:
    if count > len(topics):
        raise ValueError(f"topics_per_user={count} exceeds available topics={len(topics)}")
    rng = random.Random(f"{seed}:{user_id}")
    return rng.sample(topics, count)


def latest_child_run(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    runs = sorted([path for path in output_dir.iterdir() if path.is_dir() and path.name.startswith("run_")])
    return runs[-1] if runs else None


def run_command(command: list[str], *, cwd: Path, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        log.write("$ " + " ".join(command) + "\n\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
        return process.wait()


def build_user_job(
    *,
    python_exe: str,
    base_dir: Path,
    job: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    user_id = str(job["user_id"])
    job_dir = Path(job["job_dir"])
    log_dir = job_dir / "logs"
    status_path = job_dir / "job_status.json"
    started = time.perf_counter()

    if status_path.exists() and not args.overwrite:
        existing = read_json(status_path)
        if existing.get("status") == "done":
            return existing | {"skipped": True}

    output_dir = job_dir / "runs"
    command = [
        python_exe,
        "run_end_to_end_dataset.py",
        "--config-json",
        str(resolve_path(base_dir, args.config_json)),
        "--profiles",
        str(resolve_path(base_dir, args.profiles)),
        "--profile-user-id",
        user_id,
        "--profile-limit",
        "1",
        "--topics",
        *job["topics"],
        "--topics-per-user",
        str(len(job["topics"])),
        "--root-assets-dir",
        str(resolve_path(base_dir, args.root_assets_dir)),
        "--output-dir",
        str(output_dir),
        "--branch-depth",
        str(args.branch_depth),
        "--tree-nodes",
        str(args.tree_nodes),
        "--image-size",
        args.image_size,
        "--image-quality",
        args.image_quality,
    ]
    if args.dry_run:
        command.append("--dry-run")
    if args.skip_images:
        command.append("--skip-images")
    if args.skip_calibration:
        command.append("--skip-calibration")

    text_image_code = run_command(command, cwd=base_dir, log_path=log_dir / "pipeline.log")
    run_dir = latest_child_run(output_dir)
    if text_image_code != 0 or run_dir is None:
        result = {
            "user_id": user_id,
            "topics": job["topics"],
            "status": "failed",
            "stage": "pipeline",
            "exit_code": text_image_code,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "job_dir": str(job_dir),
        }
        write_json(status_path, result)
        return result

    web_code = 0
    if args.build_web:
        web_command = [
            python_exe,
            "build_contrast_web.py",
            "--run-dir",
            str(run_dir),
            "--root-assets-dir",
            str(resolve_path(base_dir, args.root_assets_dir)),
            "--web-dir",
            str(run_dir / "web"),
        ]
        web_code = run_command(web_command, cwd=base_dir, log_path=log_dir / "web.log")

    result = {
        "user_id": user_id,
        "topics": job["topics"],
        "status": "done" if web_code == 0 else "failed",
        "stage": "web" if web_code != 0 else "complete",
        "exit_code": web_code,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "job_dir": str(job_dir),
        "run_dir": str(run_dir),
        "web_index": str(run_dir / "web" / "index.html") if args.build_web and web_code == 0 else None,
    }
    write_json(status_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-generate user-topic comic tree runs with bounded concurrency.")
    parser.add_argument("--profiles", default="../data/user_profiles.jsonl", help="Raw user profile JSONL.")
    parser.add_argument("--root-assets-dir", default="../assets/topic_roots", help="Curated topic root assets.")
    parser.add_argument("--config-json", required=True, help="Local config.json with private model service settings. Do not commit it.")
    parser.add_argument("--output-dir", default="dataset_runs_batch", help="Batch output directory.")
    parser.add_argument("--batch-dir", default="", help="Existing or explicit batch directory. Enables resume with the same plan.")
    parser.add_argument("--last-users", type=int, default=36, help="Use the last N users from the profile file.")
    parser.add_argument("--topics-per-user", type=int, default=4, help="Random unique topics assigned to each user.")
    parser.add_argument("--seed", type=int, default=20260721, help="Stable topic sampling seed.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent user jobs.")
    parser.add_argument("--branch-depth", type=int, default=5)
    parser.add_argument("--tree-nodes", type=int, default=18, help="Number of nodes generated for each user-topic tree.")
    parser.add_argument("--image-size", default="1024x1024")
    parser.add_argument("--image-quality", default="high")
    parser.add_argument("--skip-images", action="store_true")
    parser.add_argument("--skip-calibration", action="store_true", default=True)
    parser.add_argument("--with-calibration", dest="skip_calibration", action="store_false", help="Also run VL calibration.")
    parser.add_argument("--build-web", action="store_true", default=True)
    parser.add_argument("--no-web", dest="build_web", action="store_false")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Re-run jobs even if job_status.json says done.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = Path(__file__).resolve().parent
    profiles_path = resolve_path(base_dir, args.profiles)
    root_assets_dir = resolve_path(base_dir, args.root_assets_dir)
    batch_root = resolve_path(base_dir, args.batch_dir) if args.batch_dir else resolve_path(base_dir, args.output_dir) / time.strftime("batch_%Y%m%d_%H%M%S")
    batch_root.mkdir(parents=True, exist_ok=True)

    plan_path = batch_root / "batch_plan.json"
    if args.batch_dir and plan_path.exists():
        plan = read_json(plan_path)
        jobs = list(plan["jobs"])
    else:
        rows = read_profiles(profiles_path)
        selected = rows[-args.last_users :]
        topics = available_topics(root_assets_dir)
        jobs = []
        for row in selected:
            user_id = str(row["user_id"])
            user_topics = stable_topic_sample(
                user_id=user_id,
                topics=topics,
                count=args.topics_per_user,
                seed=args.seed,
            )
            jobs.append(
                {
                    "user_id": user_id,
                    "topics": user_topics,
                    "topic_ids": [slugify(topic) for topic in user_topics],
                    "job_dir": str(batch_root / f"user_{user_id}"),
                }
            )

        plan = {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "profiles": str(profiles_path),
            "root_assets_dir": str(root_assets_dir),
            "last_users": args.last_users,
            "topics_per_user": args.topics_per_user,
            "workers": args.workers,
            "branch_depth": args.branch_depth,
            "tree_nodes": args.tree_nodes,
            "skip_images": args.skip_images,
            "skip_calibration": args.skip_calibration,
            "build_web": args.build_web,
            "dry_run": args.dry_run,
            "job_count": len(jobs),
            "tree_count": len(jobs) * args.topics_per_user,
            "estimated_branch_images": 0 if args.skip_images else len(jobs) * args.topics_per_user * max(0, args.tree_nodes - 1),
            "jobs": jobs,
        }
        write_json(batch_root / "batch_plan.json", plan)
        write_jsonl(batch_root / "batch_plan.jsonl", jobs)
    print(json.dumps({"batch_root": str(batch_root), "job_count": len(jobs), "tree_count": plan["tree_count"]}, ensure_ascii=False, indent=2))

    started = time.perf_counter()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                build_user_job,
                python_exe=sys.executable,
                base_dir=base_dir,
                job=job,
                args=args,
            )
            for job in jobs
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            write_jsonl(batch_root / "batch_status.jsonl", results)
            print(json.dumps({"user_id": result["user_id"], "status": result["status"], "elapsed_seconds": result["elapsed_seconds"]}, ensure_ascii=False))

    summary = {
        "batch_root": str(batch_root),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "done": sum(1 for result in results if result.get("status") == "done"),
        "failed": sum(1 for result in results if result.get("status") != "done"),
        "results": sorted(results, key=lambda item: str(item["user_id"])),
    }
    write_json(batch_root / "batch_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
