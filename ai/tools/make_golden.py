"""
Generates golden simulation outcomes from deterministic fixtures.
Outputs ai/tools/golden_outcomes.json for Person 3 to diff their simulator against.
Usage: python -m ai.tools.make_golden
"""

import json
from pathlib import Path
from ai.tools.reference_simulator import run_all, compare_outcomes


def make_golden_outcomes() -> Path:
    current_dir = Path(__file__).resolve().parent
    fixtures_path = current_dir.parent / "fixtures" / "ai_fixtures.json"
    output_path = current_dir / "golden_outcomes.json"

    if not fixtures_path.exists():
        raise FileNotFoundError(f"Fixtures file not found at {fixtures_path}")

    with open(fixtures_path, "r", encoding="utf-8") as f:
        fixtures_data = json.load(f)

    golden: dict = {}

    for instruction, fixture in fixtures_data.items():
        if fixture.get("status") != "ok":
            continue
        world = fixture.get("world")
        branches = fixture.get("branches")
        if not world or not branches:
            continue

        outcomes = run_all(world, branches)
        comparison = compare_outcomes(outcomes)

        golden[instruction] = {
            "entity": world.get("entity", ""),
            "today": world.get("today", ""),
            "record_count": len(world.get("records", [])),
            "branches": {
                o["branch_id"]: {
                    "affected_ids": o["affected_ids"],
                    "affected_count": o["affected_count"]
                }
                for o in outcomes
            },
            "comparison": comparison
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(golden, f, indent=2)

    print(f"Successfully generated golden outcomes at {output_path}")
    print(f"Scenarios covered: {list(golden.keys())}")
    for scn, data in golden.items():
        print(f"\nScenario: '{scn}' (today: {data['today']})")
        for bid, bdata in data["branches"].items():
            print(f"  Branch {bid}: {bdata['affected_count']} affected -> {bdata['affected_ids']}")
        print(f"  Diverges: {data['comparison']['diverges']}, Common IDs: {data['comparison']['common_ids']}")
        print(f"  Exclusive ('only_in'): {data['comparison']['only_in']}")

    return output_path


if __name__ == "__main__":
    make_golden_outcomes()
