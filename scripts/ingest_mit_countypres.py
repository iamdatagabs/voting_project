"""Version-pinned MIT Election Lab county-presidential ingestion.

The versioned delivery API is used as a transport mirror; dataset attribution
and DOI are checked before downloading. Raw bytes are hashed locally, schema
and denominator integrity are validated, and Parquet plus static series are built.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PUBLIC = ROOT / "apps" / "web" / "data"
SOURCE_ID = "mit_election_lab.county_president"
DOI = "10.7910/DVN/VOQCHQ"
METADATA_URL = "https://api.electiondata.dev/v1/county-president"
DOWNLOAD_URL = (
    "https://api.electiondata.dev/v1/county-president@{version}"
    "/download/county-president.csv"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_fips(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    digits = re.sub(r"\D", "", text)
    return digits.zfill(5) if 1 <= len(digits) <= 5 else None


def main() -> None:
    extracted_at = datetime.now(timezone.utc).isoformat()
    raw_dir = DATA / "raw" / SOURCE_ID
    bronze_dir = DATA / "bronze"
    silver_dir = DATA / "silver"
    raw_dir.mkdir(parents=True, exist_ok=True)
    bronze_dir.mkdir(parents=True, exist_ok=True)
    silver_dir.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=180, follow_redirects=True) as client:
        metadata_response = client.get(METADATA_URL)
        metadata_response.raise_for_status()
        source_metadata = metadata_response.json()
        if source_metadata.get("validation", {}).get("status") != "pass":
            raise RuntimeError("Source mirror validation is not passing")
        attribution = source_metadata.get("source", {}).get("attribution", "")
        if DOI not in attribution:
            raise RuntimeError("Dataset metadata does not identify the expected MIT/Dataverse DOI")
        version = source_metadata["version"]
        download_url = DOWNLOAD_URL.format(version=version)
        download_response = client.get(download_url)
        download_response.raise_for_status()
        raw_path = raw_dir / f"county-president-{version}.csv"
        raw_path.write_bytes(download_response.content)

    source_sha256 = sha256(raw_path)
    publisher_raw = source_metadata.get("source", {}).get("raw", [])
    publisher_sha256 = publisher_raw[0].get("sha256") if publisher_raw else None

    frame = pd.read_csv(raw_path, dtype="string", low_memory=False)
    rows_downloaded = int(len(frame))
    frame.columns = [str(column).strip() for column in frame.columns]
    aliases = {
        "FIPS": "county_fips",
        "fips": "county_fips",
        "candidatevotes": "votes",
        "totalvotes": "total_votes",
    }
    frame = frame.rename(columns={key: value for key, value in aliases.items() if key in frame.columns})
    required = {
        "year", "state", "state_po", "county_name", "unit_id",
        "office", "candidate", "party", "votes", "total_votes",
    }
    missing = required - set(frame.columns)
    if missing:
        raise RuntimeError(f"Unexpected MIT source schema; missing columns: {sorted(missing)}")

    frame["votes"] = pd.to_numeric(frame["votes"].str.replace(",", "", regex=False), errors="coerce")
    frame["total_votes"] = pd.to_numeric(
        frame["total_votes"].str.replace(",", "", regex=False), errors="coerce"
    )
    frame["election_year"] = pd.to_numeric(frame["year"], errors="raise").astype(int)
    frame["state_po"] = frame["state_po"].str.upper().str.strip()
    frame["county_name"] = frame["county_name"].str.strip()
    frame["county_fips"] = frame.get(
        "county_fips", pd.Series(pd.NA, index=frame.index)
    ).map(clean_fips)
    if "county_id" in frame.columns:
        county_ids = frame["county_id"]
    else:
        county_ids = pd.Series(pd.NA, index=frame.index)
    frame["geography_id"] = [
        str(county_id) if pd.notna(county_id) and str(county_id).strip()
        else "us-unit-" + str(state_po) + "-" + re.sub(
            r"[^A-Z0-9]+", "-", str(unit_id).upper()
        ).strip("-")
        for county_id, state_po, unit_id in zip(
            county_ids, frame["state_po"], frame["unit_id"], strict=True
        )
    ]

    denominator_counts = frame.groupby(
        ["election_year", "geography_id"]
    )["total_votes"].nunique(dropna=True)
    if (denominator_counts > 1).any():
        raise RuntimeError("Inconsistent total_votes within a county-election group")

    bronze_path = bronze_dir / "mit_county_president_2000_2024.parquet"
    frame.to_parquet(bronze_path, index=False, compression="zstd")
    omitted_missing_votes = int(frame["votes"].isna().sum())
    omitted_missing_totals = int(frame["total_votes"].isna().sum())
    frame = frame.loc[frame["votes"].notna() & frame["total_votes"].notna()].copy()
    frame["votes"] = frame["votes"].astype("int64")
    frame["total_votes"] = frame["total_votes"].astype("int64")
    if (frame["votes"] < 0).any() or (frame["total_votes"] < frame["votes"]).any():
        raise RuntimeError("Vote-count integrity check failed")
    source_key = ["election_year", "state_po", "unit_id", "candidate", "party"]
    if frame.duplicated(source_key).any():
        raise RuntimeError("Duplicate candidate-geography-year observations in source")

    frame["election_type"] = "general"
    frame["office"] = "president"
    frame["geography_type"] = frame["county_fips"].map(
        lambda value: "county" if pd.notna(value) and str(value).strip() else "other_reporting_unit"
    )
    frame["geography_name"] = frame["county_name"]
    frame["state_fips"] = pd.NA
    frame["district"] = pd.NA
    frame["result_status"] = "historical_final"
    frame["source_id"] = SOURCE_ID
    frame["source_url"] = "https://doi.org/" + DOI
    frame["source_published_at"] = frame["version"].astype("string")
    frame["extracted_at"] = extracted_at

    canonical_columns = [
        "election_year", "election_type", "office", "geography_type", "geography_id",
        "geography_name", "state_fips", "district", "candidate", "party", "votes",
        "total_votes", "result_status", "source_id", "source_url",
        "source_published_at", "extracted_at",
    ]
    canonical = frame[canonical_columns].copy()
    parquet_path = silver_dir / "mit_county_president_2000_2024.parquet"
    canonical.to_parquet(parquet_path, index=False, compression="zstd")

    # total_votes repeats on each candidate row; deduplicate before aggregation.
    totals = frame.groupby(
        ["election_year", "state_po", "geography_id"], as_index=False
    ).agg(total_votes=("total_votes", "first"))
    party_votes = frame.groupby(
        ["election_year", "state_po", "party"], as_index=False
    ).agg(votes=("votes", "sum"))
    state_totals = totals.groupby(
        ["election_year", "state_po"], as_index=False
    ).agg(total_votes=("total_votes", "sum"))
    state_series = party_votes.merge(
        state_totals, on=["election_year", "state_po"], how="left", validate="many_to_one"
    )
    state_series["vote_share"] = state_series["votes"] / state_series["total_votes"]

    national_votes = frame.groupby(
        ["election_year", "party"], as_index=False
    ).agg(votes=("votes", "sum"))
    national_totals = totals.groupby(
        "election_year", as_index=False
    ).agg(total_votes=("total_votes", "sum"))
    national_series = national_votes.merge(
        national_totals, on="election_year", how="left", validate="many_to_one"
    )
    national_series["vote_share"] = national_series["votes"] / national_series["total_votes"]

    payload = {
        "metadata": {
            "source": "MIT Election Data and Science Lab",
            "citation": (
                'MIT Election Data and Science Lab, 2018, "County Presidential Election Returns '
                '2000-2024", https://doi.org/10.7910/DVN/VOQCHQ, Harvard Dataverse, V20.'
            ),
            "doi": DOI,
            "dataset_version": version,
            "mirror_validation": source_metadata.get("validation", {}).get("status"),
            "mirror_published_at": source_metadata.get("published_at"),
            "mirror_url": download_url,
            "upstream_source_sha256": publisher_sha256,
            "download_sha256": source_sha256,
            "extracted_at": extracted_at,
            "rows_downloaded": rows_downloaded,
            "rows_silver": int(len(frame)),
            "rows_missing_candidate_votes_excluded": omitted_missing_votes,
            "rows_missing_total_votes_excluded": omitted_missing_totals,
            "years": sorted(int(year) for year in frame["election_year"].unique()),
            "geography": "county-level, aggregated to state and national series",
            "status": "historical_final_source_returns",
            "license": source_metadata.get("source", {}).get("license", "CC0-1.0"),
        },
        "national": national_series.sort_values(
            ["election_year", "party"]
        ).to_dict("records"),
        "states": state_series.sort_values(
            ["state_po", "election_year", "party"]
        ).to_dict("records"),
    }
    output = PUBLIC / "presidential-timeseries.json"
    output.write_text(json.dumps(payload, separators=(",", ":"), default=str), encoding="utf-8")
    manifest = {
        **payload["metadata"],
        "raw_file": str(raw_path.relative_to(ROOT)),
        "bronze_file": str(bronze_path.relative_to(ROOT)),
        "silver_file": str(parquet_path.relative_to(ROOT)),
        "dashboard_file": str(output.relative_to(ROOT)),
        "rows_silver": int(len(canonical)),
    }
    manifest_path = silver_dir / "mit_county_president_2000_2024.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
