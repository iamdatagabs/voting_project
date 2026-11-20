"""Ingest MIT MEDSL U.S. Senate statewide returns, 1976–2024."""
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

from electoral.config import DATA_DIR
from electoral.quality import validate_records

API = "https://api.electiondata.dev/v1/senate-results"
DATASET_ID = "mit_election_lab.us_senate_statewide_1976_2024"
DOI = "10.7910/DVN/PEJ5QU"


def as_text(value, fallback=""):
    if value is None or pd.isna(value):
        return fallback
    return str(value).strip()


def as_int(value):
    if value is None or pd.isna(value) or str(value).strip() in {"", "—", "NA"}:
        return None
    return int(str(value).replace(",", "").strip())


def main():
    stamp = datetime.now(timezone.utc).isoformat()
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        metadata_response = client.get(API)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        if metadata.get("validation", {}).get("status") != "pass":
            raise RuntimeError("Publisher mirror validation did not pass.")
        source = metadata.get("source", {})
        attribution = source.get("attribution", "")
        if DOI not in attribution or source.get("license") != "CC0-1.0":
            raise RuntimeError("Unexpected source attribution or license.")
        version = metadata.get("current_version")
        if not version:
            raise RuntimeError("Dataset version is missing.")
        url = f"https://api.electiondata.dev/v1/senate-results@{version}/download/senate-results.csv"
        response = client.get(url)
        response.raise_for_status()
        payload = response.content

    digest = hashlib.sha256(payload).hexdigest()
    raw_dir = DATA_DIR / "raw" / DATASET_ID
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{digest[:12]}-senate-results.csv"
    raw_path.write_bytes(payload)
    frame = pd.read_csv(io.BytesIO(payload), dtype=str)

    required = {
        "year", "state", "state_po", "state_fips", "stage", "special",
        "race_row", "candidate", "party_simplified", "candidatevotes",
        "totalvotes", "mode", "unofficial", "version",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Senate source schema changed; missing columns: {sorted(missing)}")

    # MEDSL's TOTAL rows are the candidate-level statewide totals. Summing
    # precinct/mode subtotals together with TOTAL would double-count ballots.
    totals = frame[frame["mode"].str.upper() == "TOTAL"].copy()
    if totals.empty:
        raise ValueError("No mode=TOTAL rows found; refusing to aggregate mode subtotals.")

    bronze = []
    for row in totals.to_dict("records"):
        year = int(row["year"])
        state_po = as_text(row["state_po"])
        stage = as_text(row["stage"]).upper()
        special = str(row["special"]).strip().lower() in {"true", "yes", "1"}
        contest_id = f"US-SENATE-{year}-{state_po}-{stage}-S{int(special)}"
        votes = as_int(row["candidatevotes"])
        total_votes = as_int(row["totalvotes"])
        party = as_text(row["party_simplified"], None)
        candidate = as_text(row["candidate"], "Unlisted candidate")
        state_name = as_text(row["state"], state_po)
        bronze.append({
            "election_year": year,
            "election_type": "general" if stage == "GEN" else stage.lower(),
            "office": "senate",
            "contest_id": contest_id,
            "source_row_id": str(row["race_row"]),
            "geography_type": "state",
            "geography_id": state_po,
            "geography_name": state_name.title(),
            "state_fips": str(int(row["state_fips"])).zfill(2),
            "district": None,
            "candidate": candidate,
            "party": None if party in {None, "", "—"} else party,
            "votes": votes,
            "total_votes": total_votes,
            "result_status": "preliminary" if str(row["unofficial"]).lower() in {"true", "yes", "1"} else "historical_final",
            "source_id": DATASET_ID,
            "source_url": url,
            "source_published_at": row["version"],
            "extracted_at": stamp,
        })

    bronze_frame = pd.DataFrame(bronze)
    missing_vote_rows = int(bronze_frame["votes"].isna().sum())
    usable = bronze_frame[bronze_frame["votes"].notna()].copy()
    normalized = [
        {key: None if pd.isna(value) else (int(value) if key in {"votes", "total_votes"} else value)
         for key, value in item.items()}
        for item in usable.to_dict("records")
    ]
    silver = pd.DataFrame(validate_records(normalized))

    bronze_path = DATA_DIR / "bronze" / "mit_us_senate_1976_2024.parquet"
    silver_path = DATA_DIR / "silver" / "mit_us_senate_1976_2024.parquet"
    bronze_path.parent.mkdir(parents=True, exist_ok=True)
    silver_path.parent.mkdir(parents=True, exist_ok=True)
    bronze_frame.to_parquet(bronze_path, index=False)
    silver.to_parquet(silver_path, index=False)

    # The public comparison includes regular general-election contests only.
    general = silver[silver["election_type"] == "general"].copy()
    totals_by_party = (
        general.dropna(subset=["party"])
        .groupby(["election_year", "state_fips", "party"], as_index=False)["votes"]
        .sum()
    )
    denominators = (
        general.drop_duplicates("contest_id")
        .groupby(["election_year", "state_fips"], as_index=False)["total_votes"]
        .sum(min_count=1)
    )
    aggregates = totals_by_party.merge(denominators, on=["election_year", "state_fips"], how="left")
    state_lookup = totals[["state_fips", "state_po", "state"]].drop_duplicates().copy()
    state_lookup["state_fips"] = state_lookup["state_fips"].map(lambda value: str(int(value)).zfill(2))
    aggregates = aggregates.merge(state_lookup, on="state_fips", how="left")
    aggregates["vote_share"] = aggregates["votes"] / aggregates["total_votes"]

    public = {
        "metadata": {
            "dataset": DATASET_ID,
            "title": metadata["title"],
            "doi": DOI,
            "version": version,
            "license": source["license"],
            "attribution": attribution,
            "source_validation": metadata["validation"]["status"],
            "source_url": url,
            "download_sha256": digest,
            "raw_rows": len(frame),
            "total_mode_rows": len(totals),
            "silver_rows": len(silver),
            "missing_candidate_votes_excluded": missing_vote_rows,
            "years": sorted(int(value) for value in frame["year"].unique()),
            "contests": int(silver["contest_id"].nunique()),
            "extracted_at": stamp,
        },
        "states": aggregates.where(pd.notna(aggregates), None).to_dict("records"),
    }
    public_path = Path("apps/web/data/senate-timeseries.json")
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        **public["metadata"],
        "raw_path": str(raw_path),
        "bronze_path": str(bronze_path),
        "silver_path": str(silver_path),
    }
    (DATA_DIR / "silver" / "mit_us_senate_1976_2024.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(public["metadata"], indent=2))


if __name__ == "__main__":
    main()
