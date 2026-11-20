"""Ingest MIT MEDSL U.S. House district returns, 1976–2024."""
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

from electoral.config import DATA_DIR
from electoral.quality import validate_records

API = "https://api.electiondata.dev/v1/house-results"
DATASET_ID = "mit_election_lab.us_house_1976_2024"
DOI = "10.7910/DVN/IG0UN2"


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
        version = metadata["current_version"]
        if not version:
            raise RuntimeError("Dataset version is missing.")
        url = f"https://api.electiondata.dev/v1/house-results@{version}/download/house-results.csv"
        response = client.get(url)
        response.raise_for_status()
        payload = response.content

    digest = hashlib.sha256(payload).hexdigest()
    raw_dir = DATA_DIR / "raw" / DATASET_ID
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{digest[:12]}-house-results.csv"
    raw_path.write_bytes(payload)

    frame = pd.read_csv(io.BytesIO(payload), dtype=str)
    required = {
        "year", "state", "state_po", "state_fips", "district", "stage",
        "special", "runoff", "race_row", "candidate", "party",
        "candidatevotes", "totalvotes", "unofficial", "version",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"House source schema changed; missing columns: {sorted(missing)}")

    bronze = []
    for row in frame.to_dict("records"):
        year = int(row["year"])
        state_po = row["state_po"].strip()
        district = str(int(row["district"]))
        stage = row["stage"].strip().upper()
        special = str(row["special"]).strip().lower() == "true"
        runoff = str(row["runoff"]).strip().lower() == "true"
        contest_id = f"US-HOUSE-{year}-{state_po}-CD{district}-{stage}-S{int(special)}-R{int(runoff)}"
        votes = as_int(row["candidatevotes"])
        total_votes = as_int(row["totalvotes"])
        bronze.append({
            "election_year": year,
            "election_type": "primary" if stage == "PRI" else "general",
            "office": "house",
            "contest_id": contest_id,
            "source_row_id": str(row["race_row"]),
            "geography_type": "congressional_district",
            "geography_id": f"{state_po}-CD{district}",
            "geography_name": f"{row['state'].title()} · District {district}",
            "state_fips": str(int(row["state_fips"])).zfill(2),
            "district": district,
            "candidate": row["candidate"].strip(),
            "party": None if pd.isna(row["party"]) or row["party"].strip() in {"", "—"} else row["party"].strip(),
            "votes": votes,
            "total_votes": total_votes,
            "result_status": "preliminary" if str(row["unofficial"]).lower() == "true" else "historical_final",
            "source_id": DATASET_ID,
            "source_url": DOI,
            "source_published_at": row["version"],
            "extracted_at": stamp,
        })

    bronze_frame = pd.DataFrame(bronze)
    missing_vote_rows = int(bronze_frame["votes"].isna().sum())
    usable = bronze_frame[bronze_frame["votes"].notna()].copy()
    usable["votes"] = usable["votes"].astype(int)
    usable["total_votes"] = usable["total_votes"].astype("Int64")
    records = validate_records(usable.to_dict("records"))
    silver = pd.DataFrame(records)

    bronze_path = DATA_DIR / "bronze" / "mit_us_house_1976_2024.parquet"
    silver_path = DATA_DIR / "silver" / "mit_us_house_1976_2024.parquet"
    bronze_path.parent.mkdir(parents=True, exist_ok=True)
    silver_path.parent.mkdir(parents=True, exist_ok=True)
    bronze_frame.to_parquet(bronze_path, index=False)
    silver.to_parquet(silver_path, index=False)

    # Denominator is counted once per distinct contest, never once per candidate.
    totals = (
        silver.dropna(subset=["party"])
        .groupby(["election_year", "state_fips", "geography_name", "party"], as_index=False)["votes"]
        .sum()
    )
    denominators = (
        silver.drop_duplicates("contest_id")
        .groupby(["election_year", "state_fips"], as_index=False)["total_votes"]
        .sum(min_count=1)
    )
    aggregates = totals.merge(denominators, on=["election_year", "state_fips"], how="left")
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
            "silver_rows": len(silver),
            "missing_candidate_votes_excluded": missing_vote_rows,
            "years": sorted(int(x) for x in frame["year"].unique()),
            "contests": int(silver["contest_id"].nunique()),
            "extracted_at": stamp,
        },
        "states": aggregates.where(pd.notna(aggregates), None).to_dict("records"),
    }
    public_path = Path("apps/web/data/house-timeseries.json")
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        **public["metadata"],
        "raw_path": str(raw_path),
        "bronze_path": str(bronze_path),
        "silver_path": str(silver_path),
    }
    manifest_path = DATA_DIR / "silver" / "mit_us_house_1976_2024.manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(public["metadata"], indent=2))


if __name__ == "__main__":
    main()
