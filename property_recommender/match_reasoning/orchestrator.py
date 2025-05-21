#!/usr/bin/env python3
"""
property_recommender/match_reasoning/orchestrator.py

Pipeline runner for Match Reasoning:
  1. Read user profile JSON.
  2. Read cleaned property listings JSON.
  3. Score and rank listings via LLM (Matcher).
  4. Persist sorted match results to disk.
"""

import argparse
import json
import sys
from pathlib import Path

from property_recommender.match_reasoning.features.matcher import Matcher


def run_matching(
    profile_path: Path,
    listings_path: Path,
    output_path: Path,
    schema_path: Path,
    model: str,
    temperature: float,
    retries: int,
    mode: str
):
    # 1. Load user profile
    try:
        user_profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception as e:
        sys.exit(f"❌ Failed to load user profile '{profile_path}': {e}")

    # 2. Load cleaned listings
    try:
        listings = json.loads(listings_path.read_text(encoding="utf-8"))
    except Exception as e:
        sys.exit(f"❌ Failed to load property listings '{listings_path}': {e}")

    print(f"✅ Loaded profile and {len(listings)} listings")

    # 3. Initialize Matcher
    matcher = Matcher(
        schema_path=schema_path,
        model=model,
        temperature=temperature,
        retry_limit=retries
    )

    # 4. Run matching
    if mode == "batch":
        print("🔢 Running batch ranking…")
        matches = matcher.match_batch(user_profile, listings)
    else:
        print("🔍 Running individual scoring…")
        matches = matcher.match_individual(user_profile, listings)

    # 5. Persist output
    try:
        output_path.write_text(json.dumps(matches, indent=2), encoding="utf-8")
    except Exception as e:
        sys.exit(f"❌ Failed to write matches to '{output_path}': {e}")

    print(f"💾 Wrote {len(matches)} matches to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Property Match Orchestrator")
    parser.add_argument(
        "--profile", type=Path, default=Path("user_profile.json"),
        help="Path to the normalized user profile JSON"
    )
    parser.add_argument(
        "--listings", type=Path, default=Path("clean_properties.json"),
        help="Path to the cleaned property listings JSON"
    )
    parser.add_argument(
        "--out", type=Path, default=Path("property_matches.json"),
        help="Path where the match results will be written"
    )
    parser.add_argument(
        "--schema", type=Path,
        default=Path(__file__).parent / "schemas" / "property_match.json",
        help="Path to the property_match.json schema file"
    )
    parser.add_argument(
        "--model", type=str, default="gpt-4o",
        help="OpenAI model name to use for scoring"
    )
    parser.add_argument(
        "--temperature", type=float, default=0.7,
        help="Sampling temperature for the LLM (0.0–1.0)"
    )
    parser.add_argument(
        "--retries", type=int, default=2,
        help="Number of retry attempts for LLM calls"
    )
    parser.add_argument(
        "--mode", choices=["batch", "individual"], default="batch",
        help="Mode of matching: 'batch' for one-shot ranking, 'individual' for per-record scoring"
    )

    args = parser.parse_args()

    run_matching(
        profile_path=args.profile,
        listings_path=args.listings,
        output_path=args.out,
        schema_path=args.schema,
        model=args.model,
        temperature=args.temperature,
        retries=args.retries,
        mode=args.mode
    )


if __name__ == "__main__":
    main()
