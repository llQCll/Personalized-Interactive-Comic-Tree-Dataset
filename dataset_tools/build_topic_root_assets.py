from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from dataset_pipeline import OpenAICompatibleClient, PipelineConfig, json_dumps, sdk_base_url, slugify, write_json


ROOT_TOPICS: list[dict[str, str]] = [
    {
        "topic": "Hidden Castle",
        "synopsis": "A mist-veiled castle appears only when moonlight strikes an antique compass, inviting a traveler to choose between the main gate, a side path, and the secrets hidden in the forest edge.",
        "prompt": "Shared root comic panel for an interactive branching story. Wide cinematic fantasy composition at the moonlit edge of an ancient forest. A young traveler in a dark teal hooded cloak stands with their back partly turned, holding an antique silver compass with cracked glass and a faintly glowing needle. Ahead, blue mist parts to reveal a vast ivy-covered hidden castle with crooked towers, narrow arched windows, and a sealed front gate. A newly revealed stone path begins near tangled roots, while a darker side trail and strange markings near the compass provide multiple readable interaction targets. Moody fantasy adventure, inked comic linework with painterly colors, cool blue moonlight, emerald shadows, subtle golden magic, atmospheric fog, high environmental detail. Topic-only root image: no user preferences, no personalized traits, no captions, no dialogue, no text, no modern objects.",
    },
    {
        "topic": "Neon Hospital",
        "synopsis": "In a rainlit future clinic, a diagnostic AI detects an impossible vital sign, opening choices between the patient room, the glowing medical console, and a sealed emergency corridor.",
        "prompt": "Shared root comic panel for an interactive branching story. Wide cinematic sci-fi hospital scene at night, seen from a clean but slightly eerie corridor washed in cyan and warm neon reflections. A young medical intern in a simple jacket stands beside a floating diagnostic console, looking toward a patient room door with a pulsing red-orange warning light. Transparent screens show abstract vital-sign shapes without readable text. A sealed emergency corridor, a medicine cart, and a softly glowing biometric scanner create distinct possible interaction targets. Bright near-future medical design, polished floors, rain streaks on tall windows, soft volumetric light, precise clinical details, hopeful tension rather than horror. Topic-only root image: no user preferences, no personalized traits, no captions, no dialogue, no readable text, no gore.",
    },
    {
        "topic": "Desert Whale Caravan",
        "synopsis": "A caravan crosses a sea of golden dunes beneath enormous sky-whales, where a singing compass, ancient bones, and a storm-lit oasis suggest different routes forward.",
        "prompt": "Shared root comic panel for an interactive branching story. Wide sunlit desert fantasy scene with a small caravan paused on rolling golden dunes. Above the caravan, several enormous translucent sky-whales drift through the bright blue air like living clouds. A young guide in a wind scarf holds a small bronze singing compass while pack animals wait nearby. In the distance are three readable choices: a whale shadow crossing the sand, half-buried ancient rib bones, and a green oasis flickering under a far sandstorm. Warm adventurous illustration, comic panel framing, sweeping scale, clear silhouettes, ochre sand, turquoise sky, pearly whale bodies, magical realism, no text, no captions, no modern vehicles, no user-specific details.",
    },
    {
        "topic": "Underwater Library",
        "synopsis": "A submerged library protected by glass domes awakens when a diver opens a shell-shaped catalog, revealing books, currents, and sea creatures that may each guide the next discovery.",
        "prompt": "Shared root comic panel for an interactive branching story. Wide underwater fantasy scene inside a vast glass-domed library on the ocean floor. A young diver in a graceful retro-fantasy diving suit floats near a shell-shaped catalog device, while shelves of waterproof books curve upward through blue-green water. Outside the glass dome, coral arches, drifting manta rays, and a distant locked archive door are visible. Distinct interaction targets include the glowing shell catalog, a floating open book, a curious octopus near a shelf, and the sealed archive door. Luminous aquatic lighting, caustic patterns, soft bubbles, colorful coral, magical scholarly mood, clean comic illustration. No text, no captions, no dialogue, no user-personalized traits.",
    },
    {
        "topic": "Abandoned Space Elevator",
        "synopsis": "At the base of a silent orbital elevator, a maintenance badge suddenly reactivates, offering paths through the control deck, cable shaft, and derelict station ruins above.",
        "prompt": "Shared root comic panel for an interactive branching story. Wide cinematic sci-fi scene at dusk: the colossal base of an abandoned space elevator rises from a cracked coastal launch platform into clouds and stars. A lone technician in a worn orange maintenance jacket stands before a dormant control console, holding a small reactivated access badge that glows pale blue. Distinct possible targets include the control deck, an open maintenance hatch leading into the cable shaft, a broken service drone, and the distant elevator ribbon vanishing upward. Grand scale, clean hard-sci-fi shapes, weathered metal, sea mist, sunset orange and cold blue lights, hopeful mystery, no readable text, no logos, no dialogue, no user-specific references.",
    },
    {
        "topic": "Rainy Cyberpunk Alley",
        "synopsis": "In a neon alley during a storm, a courier receives a scrambled signal that points toward a vending shrine, a rooftop route, and a shadowed figure under the rain.",
        "prompt": "Shared root comic panel for an interactive branching story. Wide rainy cyberpunk alley scene at night, dense with reflections and bright neon signs rendered as abstract unreadable shapes. A young courier in a practical rain jacket stands under a leaking awning, holding a small glowing data charm with a scrambled signal. Distinct interaction targets include a vending-machine shrine, a fire escape leading to rooftops, a shadowed figure beneath a transparent umbrella, and a puddle reflecting a hidden symbol. High-energy urban comic style, saturated cyan, amber, and magenta lighting, wet pavement, steam, cables, compact storefronts, cinematic noir mood. No readable text, no brand logos, no dialogue, no user-specific traits.",
    },
    {
        "topic": "Talking Animal Courtroom",
        "synopsis": "A woodland courtroom convenes after a stolen moonberry pie vanishes, and the first scene offers witnesses, evidence, and a suspicious judge's gavel as possible leads.",
        "prompt": "Shared root comic panel for an interactive branching story. Bright whimsical courtroom inside a giant hollow oak tree. Talking animals gather as a trial is about to begin: an owl judge at a carved wooden bench, a nervous rabbit witness, a fox advocate, and a table holding a missing-pie plate with glittering crumbs. The protagonist is a small human visitor or neutral clerk holding a simple notebook, positioned so the viewer can choose among evidence, witness, judge's gavel, or side door. Warm storybook comic style, expressive animal faces, sunbeams through leaves, cozy wood textures, playful mystery, clear interaction targets. No readable text, no captions, no dialogue bubbles, no user-specific traits.",
    },
    {
        "topic": "Volcanic Flower Market",
        "synopsis": "A market of fireproof flowers blooms beside a gentle volcano, where a rare ember seed reacts to heat, music, and rival gardeners competing for its next form.",
        "prompt": "Shared root comic panel for an interactive branching story. Wide vibrant fantasy marketplace built on black volcanic stone terraces beside a softly glowing volcano. Merchants sell impossible flowers: lava lilies, glass petals, smoke orchids, and ember seeds in ceramic bowls. A young gardener in a protective apron holds a rare ember seed that glows in their palm. Distinct interaction targets include a musical flower stall, a steam vent, a rival gardener's cart, and a path toward the volcano greenhouse. Bright colorful comic illustration, warm reds and oranges balanced with lush greens and blues, festive crowd silhouettes, magical botany, no text, no captions, no dialogue, no user-specific information.",
    },
    {
        "topic": "Time-loop Train Station",
        "synopsis": "A train station clock repeats the same minute, and a traveler must decide whether to board the impossible train, inspect the clock, or follow echoes from previous loops.",
        "prompt": "Shared root comic panel for an interactive branching story. Wide cinematic magical-realism train station at twilight. A grand old clock above the platform shows an impossible repeated minute using abstract clock hands rather than readable numbers. A traveler with a small suitcase stands between three clear choices: a glowing train with open doors, the huge looping station clock, and translucent echo-figures of the traveler walking along a side platform. Warm station lights, cool blue evening sky, brass and wood textures, light fog, subtle time fragments, elegant comic linework, mysterious but inviting mood. No readable text, no captions, no dialogue, no modern brand marks, no user-specific traits.",
    },
    {
        "topic": "Snow Mountain Radio Tower",
        "synopsis": "At a remote mountain radio tower, a signal from beneath the snow begins to answer back, pointing toward the antenna, an old rescue map, and lights moving in the storm.",
        "prompt": "Shared root comic panel for an interactive branching story. Wide snowy adventure scene on a high mountain ridge at blue hour. A bundled radio operator stands outside a small weather station hut, holding a crackling handheld receiver. A tall radio tower rises into swirling snow, its red warning lights glowing softly. Distinct interaction targets include the tower ladder, an old rescue map pinned inside the hut window, strange lights moving beyond the ridge, and a half-buried cable leading under the snow. Crisp atmospheric comic style, icy blues, warm cabin light, windblown snow, tense survival mystery, no readable text, no captions, no dialogue, no user-specific details.",
    },
    {
        "topic": "Miniature City Inside a Watch",
        "synopsis": "Inside an opened pocket watch, a tiny city runs on gears and bells, and a newly arrived repairer must choose which district of the living mechanism to touch first.",
        "prompt": "Shared root comic panel for an interactive branching story. Macro fantasy comic scene inside an opened antique pocket watch. A tiny repairer stands on a brass gear bridge overlooking a miniature city built among cogs, springs, bell towers, and glowing windows. The watch case forms a circular frame around the scene. Distinct interaction targets include a jammed central gear, a bell tower ringing silently, a small train running along a spring, and a glowing door under the watch hands. Warm brass, teal shadows, intricate mechanical detail, whimsical sense of scale, polished magical steampunk mood. No readable text, no captions, no dialogue, no user-specific traits.",
    },
    {
        "topic": "Ocean Festival on Paper Lantern Island",
        "synopsis": "On an island lit by floating paper lanterns, the tide carries a message in a bottle, inviting choices among the festival pier, a lantern boat, and a moonlit reef path.",
        "prompt": "Shared root comic panel for an interactive branching story. Wide bright coastal festival scene on a small island at moonrise. Hundreds of warm paper lanterns float above turquoise water and along a wooden pier. A young visitor in simple festival clothes stands near the shoreline holding a sealed glass bottle with a glowing message inside. Distinct interaction targets include a lantern boat ready to depart, a reef path revealed by low tide, a musician's pier, and a cluster of lanterns drifting toward the open ocean. Joyful magical comic style, warm gold lantern light, clear blue moonlight, gentle waves, festive but mysterious atmosphere. No readable text, no captions, no dialogue, no user-specific details.",
    },
]


def load_config_from_run(path: Path | None) -> PipelineConfig:
    config = PipelineConfig()
    if not path:
        return config
    config_path = path / "config.json"
    if not config_path.exists():
        raise RuntimeError(f"Missing config file: {config_path}")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    for key, value in data.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config


def build_asset(topic: dict[str, str], output_dir: Path) -> dict[str, Any]:
    topic_id = slugify(topic["topic"])
    topic_dir = output_dir / topic_id
    image_path = topic_dir / "root.png"
    return {
        "topic_id": topic_id,
        "topic": topic["topic"],
        "synopsis": topic["synopsis"],
        "world_bible": {
            "premise": topic["synopsis"],
            "visual_style": "High-quality interactive comic root panel with clear clickable regions, strong atmosphere, and no user-specific personalization.",
            "main_entities": [],
            "protected_entities": ["consistent protagonist", "signature object or scene anchor"],
            "continuity_rules": [
                "The root panel is shared by all users under this topic.",
                "The root image must be topic-only and must not contain user preference information.",
                "Keep multiple visually readable interaction targets for later branching.",
                "Do not include readable text, captions, dialogue bubbles, logos, or watermarks.",
            ],
        },
        "root_state": {
            "location": f"shared opening scene for {topic['topic']}",
            "narrative_status": topic["synopsis"],
        },
        "root_prompt": topic["prompt"],
        "root_image": str(image_path),
        "asset_metadata": str(topic_dir / "root.json"),
    }


def write_assets(*, output_dir: Path, overwrite: bool) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = [build_asset(topic, output_dir) for topic in ROOT_TOPICS]
    for asset in assets:
        topic_dir = Path(asset["root_image"]).parent
        topic_dir.mkdir(parents=True, exist_ok=True)
        asset_path = topic_dir / "root_asset.json"
        if overwrite or not asset_path.exists():
            write_json(asset_path, asset)
        prompt_path = topic_dir / "root_prompt.txt"
        synopsis_path = topic_dir / "synopsis.txt"
        if overwrite or not prompt_path.exists():
            prompt_path.write_text(asset["root_prompt"], encoding="utf-8")
        if overwrite or not synopsis_path.exists():
            synopsis_path.write_text(asset["synopsis"], encoding="utf-8")
    write_json(output_dir / "manifest.json", assets)
    return assets


def generate_images(*, assets: list[dict[str, Any]], config: PipelineConfig, overwrite: bool) -> None:
    client = OpenAICompatibleClient(
        base_url=config.image_base_url,
        api_key=config.image_api_key,
        model=config.image_model,
        timeout_seconds=config.timeout_seconds,
    )
    for index, asset in enumerate(assets, start=1):
        image_path = Path(asset["root_image"])
        metadata_path = image_path.with_suffix(".json")
        if image_path.exists() and not overwrite:
            print(f"[{index}/{len(assets)}] skip existing {asset['topic_id']}")
            continue
        print(f"[{index}/{len(assets)}] generating {asset['topic_id']} ...")
        metadata = client.generate_image(
            prompt=asset["root_prompt"],
            output_path=image_path,
            references=[],
            size=config.image_size,
            quality=config.image_quality,
        )
        metadata["topic_id"] = asset["topic_id"]
        metadata["topic"] = asset["topic"]
        metadata["synopsis"] = asset["synopsis"]
        metadata["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        write_json(metadata_path, metadata)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create shared root assets for the 12 topic set.")
    parser.add_argument("--output-dir", default="topic_root_assets", help="Folder for root images, prompts, and metadata.")
    parser.add_argument("--generate-images", action="store_true", help="Call the image model for missing root images.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing metadata and images.")
    parser.add_argument("--config-from-run", default="", help="Optional existing run directory whose config.json supplies local service settings.")
    parser.add_argument("--image-size", default="", help="Override image size, e.g. 1024x1024.")
    parser.add_argument("--image-quality", default="", help="Override image quality, e.g. high.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = Path(__file__).resolve().parent
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (base_dir / output_dir).resolve()
    assets = write_assets(output_dir=output_dir, overwrite=args.overwrite)
    if not args.generate_images:
        print(f"Wrote {len(assets)} root asset specs to {output_dir}")
        return
    run_dir = Path(args.config_from_run) if args.config_from_run else None
    if run_dir and not run_dir.is_absolute():
        run_dir = (base_dir / run_dir).resolve()
    config = load_config_from_run(run_dir)
    if args.image_size:
        config.image_size = args.image_size
    if args.image_quality:
        config.image_quality = args.image_quality
    generate_images(assets=assets, config=config, overwrite=args.overwrite)
    print(f"Finished root image generation in {output_dir}")


if __name__ == "__main__":
    main()
