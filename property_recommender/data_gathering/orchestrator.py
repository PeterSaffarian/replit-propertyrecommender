#!/usr/bin/env python3
"""
property_recommender/data_gathering/orchestrator.py

Pipeline runner for Data Gathering:
  1. Read user profile JSON.
  2. Generate Trade Me API search parameters via LLM (QueryBuilder).
  3. Fetch raw listings from Trade Me (FetchExecutor).
  4. Normalize raw listings via LLM (DataNormalizer).
  5. Persist raw and cleaned JSON outputs.
"""

import argparse
import json
import sys
from pathlib import Path

from .features.query_builder.query_builder import QueryBuilder
from .features.fetch_executor.fetch_executor import FetchExecutor
from .features.data_normalizer.data_normalizer import DataNormalizer


def run_pipeline(
    profile_path: Path,
    raw_output_path: Path,
    clean_output_path: Path,
    schema_path: Path,
    model: str,
    temperature: float,
    retries: int,
    sandbox: bool
):
    # 1. Load the user profile
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception as e:
        sys.exit(f"❌ Failed to load profile {profile_path}: {e}")
    print(f"✅ Loaded user profile from {profile_path}")

    # 2. Build search parameters
    qb = QueryBuilder(model=model, temperature=temperature, sandbox=sandbox)
    params = qb.build_params(profile)
    print("🔍 Generated search parameters:")
    print(json.dumps(params, indent=2))

    # 3. Fetch raw data
    fetcher = FetchExecutor(sandbox=sandbox)
    raw = fetcher.fetch(search_params=params, section="Residential", save_path=raw_output_path)
    print(f"📥 Fetched raw data; saved to {raw_output_path}")

    # 4. Normalize data
    normalizer = DataNormalizer(
        schema_path=schema_path,
        model=model,
        temperature=temperature,
        retry_limit=retries
    )
    # Trade Me wraps listings in "List"
    records = raw.get("List") if isinstance(raw, dict) and "List" in raw else raw
    cleaned = normalizer.normalize(records)
    print(f"🧹 Normalized {len(cleaned)} records")

    # 5. Persist clean data
    clean_output_path.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
    print(f"💾 Clean data written to {clean_output_path}")


def main():
    parser = argparse.ArgumentParser(description="Property Data Gathering Pipeline")
    parser.add_argument(
        "--profile", type=Path, default=Path("user_profile.json"),
        help="Path to user_profile.json"
    )
    parser.add_argument(
        "--raw-out", type=Path, default=Path("raw_properties.json"),
        help="Where to write raw API output"
    )
    parser.add_argument(
        "--clean-out", type=Path, default=Path("clean_properties.json"),
        help="Where to write normalized listings"
    )
    parser.add_argument(
        "--schema", type=Path,
        default=Path(__file__).parent / "schemas" / "property_record.json",
        help="JSON Schema for normalized records"
    )
    parser.add_argument(
        "--model", type=str, default="gpt-4o",
        help="OpenAI model for QueryBuilder & DataNormalizer"
    )
    parser.add_argument(
        "--temperature", type=float, default=0.7,
        help="Sampling temperature for LLM calls"
    )
    parser.add_argument(
        "--retries", type=int, default=2,
        help="Retry limit for normalization"
    )
    parser.add_argument(
        "--sandbox", action="store_true",
        help="Use Trade Me sandbox endpoints"
    )
    args = parser.parse_args()

    run_pipeline(
        profile_path=args.profile,
        raw_output_path=args.raw_out,
        clean_output_path=args.clean_out,
        schema_path=args.schema,
        model=args.model,
        temperature=args.temperature,
        retries=args.retries,
        sandbox=args.sandbox
    )


if __name__ == "__main__":
    main()
