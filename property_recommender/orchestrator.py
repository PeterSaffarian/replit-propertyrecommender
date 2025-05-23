#!/usr/bin/env python3
"""
property_recommender/orchestrator.py

End-to-end Property Recommendation Pipeline:
  1. Run the interactive profile collection (writes user_profile.json)
  2. Run data gathering (raw_properties.json → clean_properties.json)
  3. Run match reasoning (clean_properties.json → property_matches.json)
"""

import argparse
import sys
from pathlib import Path
import json

# Step 1: Profile collection
from .user_interaction.main import main as collect_profile

# Step 2: Data gathering
from .data_gathering.orchestrator import main as gather_data

# Step 3: Match reasoning
from .match_reasoning.orchestrator import run_matching as match_properties

def main():
    parser = argparse.ArgumentParser(
        description="Run full property recommendation pipeline end-to-end."
    )
    parser.add_argument(
        "--profile", type=Path, default=Path("user_profile.json"),
        help="Path where the user profile will be written/read."
    )
    parser.add_argument(
        "--raw-out", type=Path, default=Path("raw_properties.json"),
        help="Path to write raw Trade Me API output."
    )
    parser.add_argument(
        "--clean-out", type=Path, default=Path("clean_properties.json"),
        help="Path to write normalized property records."
    )
    parser.add_argument(
        "--matches-out", type=Path, default=Path("property_matches.json"),
        help="Path to write final ranked matches."
    )
    parser.add_argument(
        "--model", type=str, default="gpt-4o",
        help="OpenAI model for LLM calls."
    )
    parser.add_argument(
        "--temperature", type=float, default=0.7,
        help="Sampling temperature for LLM calls."
    )
    parser.add_argument(
        "--retries", type=int, default=2,
        help="Retry limit for normalization and matching."
    )
    parser.add_argument(
        "--sandbox", action="store_true",
        help="Use Trade Me sandbox endpoints for data gathering."
    )
    parser.add_argument(
        "--match-mode", choices=["batch", "individual"], default="batch",
        help="Matching mode: batch ranking vs per-record scoring."
    )
    args = parser.parse_args()

    # 1. Profile collection
    print("📝  Phase 1: Collecting user profile…")
    try:
        collect_profile()  # writes user_profile.json by default
    except SystemExit:
        # allow early exit from collect_profile
        pass
    if not args.profile.exists():
        sys.exit(f"❌ Profile file not found: {args.profile}")

    # 2. Data gathering
    print("\n🌐  Phase 2: Gathering property data…")
    sys.argv = [
        sys.argv[0],
        "--profile", str(args.profile),
        "--output", str(args.raw_out),
        "--model", args.model,
        "--temperature", str(args.temperature)
    ]
    gather_data()

    # 3. Match reasoning
    print("\n🏷️  Phase 3: Scoring and ranking properties…")
    match_properties(
        profile_path=args.profile,
        listings_path=args.raw_out,
        output_path=args.matches_out,
        schema_path=Path(__file__).parent / "match_reasoning" / "schemas" / "property_match.json",
        model=args.model,
        temperature=args.temperature,
        retries=args.retries,
        mode=args.match_mode
    )

    print(f"\n🎉  Pipeline complete! Final matches written to {args.matches_out}")

if __name__ == "__main__":
    main()
