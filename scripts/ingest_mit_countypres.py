"""Reproducible MIT Election Lab county-presidential ingestion.

Downloads the latest public Harvard Dataverse version by DOI, verifies the
publisher-provided MD5 and a locally computed SHA-256, then writes canonical
Silver Parquet and a compact static time-series payload for GitHub Pages.
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
DOI = "doi:10.7910/DVN/VOQCHQ"
SOURCE_ID = "mit_election_lab.county_president"
METADATA_URL = "https://dataverse.harvard.edu/api/datasets/:persistentId/"
ACCESS_URL = "https://dataverse.harvard.edu/api/access/datafile/{file_id}"


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
    stamp = datetime.now(timezone.utc).isoformat()
    raw_dir = DATA / "raw" / SOURCE_ID
    silver_dir = DATA / "silver"
    raw_dir.mkdir(parents=True, exist_ok=True)
    silver_dir.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=180, follow_redirects=True) as client:
        response = client.get(METADATA_URL, params={"persistentId": DOI})
        response.raise_for_status()
        metadata = response.json()["data"]
        version = metadata["latestVersion"]
        candidates = [
            item for item in version["files"]
            if "countypres_2000-2024" in item["dataFile"]["filename"].lower()
        ]
        if not candidates:
            raise RuntimeError("Dataverse latest version has no county presidential data file")
        source_file = candidates[0]["dataFile"]
        file_id = source_file["id"]
        expected_md5 = source_file.get("md5")
        raw_path = raw_dir / source_file["filename"]
        download = client.get(ACCESS_URL.format(file_id=file_id))
        download.raise_for_status()
        raw_path.write_bytes(download.content)

    import hashlib as _hashlib
    actual_md5 = _hashlib.md5(raw_path.read_bytes()).hexdigest()  # noqa: S324 - publisher checksum
    if expected_md5 and actual_md5.lower() != expected_md5.lower():
        raise RuntimeError(f"Dataverse MD5 mismatch: expected {expected_md5}, got {actual_md5}")
    source_sha256 = sha256(raw_path)

    frame = pd.read_csv(raw_path, sep="\t", dtype="string", low_memory=False)
    frame.columns = [str(column).strip() for column in frame.columns]
    aliases = {
        "FIPS": "county_fips", "fips": "county_fips",
        "county_fips": "county_fips", "candidatevotes": "votes",
        "totalvotes": "total_votes", "state_fips": "state_fips",
    }
    frame = frame.rename(columns={key: value for key, value in aliases.items() if key in frame.columns})
    required = {"year", "state", "state_po", "county_name", "office", "candidate",
                "party", "votes", "total_votes"}
    missing = required - set(frame.columns)
    if missing:
        raise RuntimeError(f"Unexpected MIT source schema; missing columns: {sorted(missing)}")

    frame["votes"] = pd.to_numeric(frame["votes"].str.replace(",", "", regex=False), errors="coerce")
    frame["total_votes"] = pd.to_numeric(
        frame["total_votes"].str.replace(",", "", regex=False), errors="coerce"
    )
    frame["election_year"] = pd.to_numeric(frame["year"], errors="raise").astype(int)
    frame["county_fips"] = frame.get("county_fips", pd.Series(pd.NA, index=frame.index)).map(clean_fips)
    frame["state_fips"] = frame.get("state_fips", pd.Series(pd.NA, index=frame.index)).astype("string")
    frame["state_fips"] = frame["state_fips"].str.replace(r"\.0$", "", regex=True).str.zfill(2)
    frame.loc[~frame["state_fips"].str.fullmatch(r"\d{2}", na=False), "state_fips"] = pd.NA
    frame["state_po"] = frame["state_po"].str.upper().str.strip()
    frame["county_name"] = frame["county_name"].str.strip()
    frame["geography_id"] = frame.apply(
        lambda row: f"us-county-{row.county_fips}" if row.county_fips
        else f"{row.state_po}-{re.sub(r'[^A-Z0-9]+', '-', row.county_name.upper()).strip('-')}",
        axis=1,
    )
    frame["election_type"] = "general"
    frame["office"] = "president"
    frame["geography_type"] = "county"
    frame["geography_name"] = frame["county_name"]
    frame["district"] = pd.NA
    frame["result_status"] = "certified"
    frame["source_id"] = SOURCE_ID
    frame["source_url"] = "https://doi.org/10.7910/DVN/VOQCHQ"
    frame["source_published_at"] = frame["version"].astype("string") if "version" in frame else pd.NA
    frame["extracted_at"] = stamp
    # Null candidate vote counts remain missing and are excluded, never coerced to zero.
    omitted_missing_votes = int(frame["votes"].isna().sum())
    frame = frame.loc[frame["votes"].notna()].copy()
    frame["votes"] = frame["votes"].astype("int64")
    frame["total_votes"] = frame["total_votes"].astype("Int64")
    frame = frame.loc[frame["total_votes"].notna()].copy()
    if (frame["votes"] < 0).any() or (frame["total_votes"] < frame["votes"]).any():
        raise RuntimeError("Vote-count integrity check failed")
    if frame.duplicated(["election_year", "geography_id", "candidate", "party"]).any():
        raise RuntimeError("Duplicate candidate-geography-year observations in source")

    canonical_columns = [
        "election_year", "election_type", "office", "geography_type", "geography_id",
        "geography_name", "state_fips", "district", "candidate", "party", "votes",
        "total_votes", "result_status", "source_id", "source_url",
        "source_published_at", "extracted_at",
    ]
    canonical = frame[canonical_columns].copy()
    parquet_path = silver_dir / "mit_county_president_2000_2024.parquet"
    canonical.to_parquet(parquet_path, index=False, compression="zstd")

    # Denominator is deduplicated at county-election level before aggregation.
    totals = frame.groupby(["election_year", "state_po", "geography_id"], as_index=False).agg(
        total_votes=("total_votes", "max")
    )
    party_votes = frame.groupby(["election_year", "state_po", "party"], as_index=False).agg(
        votes=("votes", "sum")
    )
    state_totals = totals.groupby(["election_year", "state_po"], as_index=False).agg(
        total_votes=("total_votes", "sum")
    )
    state_series = party_votes.merge(state_totals, on=["election_year", "state_po"], how="left")
    state_series["vote_share"] = state_series["votes"] / state_series["total_votes"]
    national_votes = frame.groupby(["election_year", "party"], as_index=False).agg(votes=("votes", "sum"))
    national_totals = totals.groupby("election_year", as_index=False).agg(total_votes=("total_votes", "sum"))
    national_series = national_votes.merge(national_totals, on="election_year", how="left")
    national_series["vote_share"] = national_series["votes"] / national_series["total_votes"]

    payload = {
        "metadata": {
            "source": "MIT Election Data and Science Lab",
            "citation": 'MIT Election Data and Science Lab, 2018, "County Presidential Election Returns 2000-2024", https://doi.org/10.7910/DVN/VOQCHQ, Harvard Dataverse, V20.',
            "doi": "10.7910/DVN/VOQCHQ",
            "dataverse_version": version.get("versionNumber"),
            "dataverse_file_id": file_id,
            "publisher_md5": expected_md5,
            "sha256": source_sha256,
            "extracted_at": stamp,
            "rows_source": int(len(frame)),
            "rows_missing_candidate_votes_excluded": omitted_missing_votes,
            "years": sorted(int(year) for year in frame["election_year"].unique()),
            "geography": "county-level, aggregated to state and national series",
            "status": "certified_source_returns",
            "license": "CC0-1.0",
        },
        "national": national_series.sort_values(["election_year", "party"]).to_dict("records"),
        "states": state_series.sort_values(["state_po", "election_year", "party"]).to_dict("records"),
    }
    output = PUBLIC / "presidential-timeseries.json"
    output.write_text(json.dumps(payload, separators=(",", ":"), default=str), encoding="utf-8")
    manifest = {
        **payload["metadata"],
        "raw_file": str(raw_path.relative_to(ROOT)),
        "silver_file": str(parquet_path.relative_to(ROOT)),
        "dashboard_file": str(output.relative_to(ROOT)),
        "rows_silver": int(len(canonical)),
    }
    manifest_path = DATA / "silver" / "mit_county_president_2000_2024.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
