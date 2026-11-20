"""Ingest 2024 state-office precinct returns from MEDSL's state archives.

Downloads the 51 state/DC ZIP archives from a pinned Git commit, verifies each
archive against its Git blob SHA-1, and keeps governor/state-legislative races.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

from electoral.config import DATA_DIR
from electoral.quality import validate_records

REPO_API = "https://api.github.com/repos/MEDSL/2024-elections-official"
SOURCE_ID = "mit_medsl_state_precinct_2024"
SOURCE_URL = "https://github.com/MEDSL/2024-elections-official"
RAW_DIR = DATA_DIR / "raw" / SOURCE_ID
BRONZE_PATH = DATA_DIR / "bronze" / "mit_state_offices_precinct_2024.parquet"
SILVER_PATH = DATA_DIR / "silver" / "mit_state_offices_2024.parquet"
MANIFEST_PATH = DATA_DIR / "silver" / "mit_state_offices_2024.manifest.json"
PUBLIC_PATH = Path("apps/web/data/state-offices-2024.json")
OFFICE_MAP = {
    "GOVERNOR": ("governor", "state"),
    "STATE HOUSE": ("state_house", "state_legislative_district"),
    "STATE SENATE": ("state_senate", "state_legislative_district"),
}
REQUIRED = {
    "office", "candidate", "party_simplified", "votes", "mode",
    "state_po", "state_fips", "district", "precinct", "date",
}


def git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload).hexdigest()


def parse_votes(value: object) -> int | None:
    text = str(value).strip()
    if text in {"", "*", "NA", "nan", "None"}:
        return None
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


def normalize_text(value: object, fallback: str = "") -> str:
    if value is None or pd.isna(value):
        return fallback
    result = str(value).strip()
    return result if result else fallback


def archive_csv(payload: bytes, archive_name: str) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [
            name for name in archive.namelist()
            if name.lower().endswith((".csv", ".tab"))
            and not name.startswith("__MACOSX/")
        ]
        if not members:
            raise ValueError(f"No CSV/TAB file found in {archive_name}")
        # State archives should contain one canonical precinct table. Fail on
        # ambiguity instead of silently selecting a codebook or partial table.
        if len(members) != 1:
            candidates = [name for name in members if "precinct" in name.lower()]
            if len(candidates) != 1:
                raise ValueError(f"Ambiguous tabular files in {archive_name}: {members}")
            member = candidates[0]
        else:
            member = members[0]
        with archive.open(member) as stream:
            header = stream.readline().decode("utf-8-sig", errors="replace")
            delimiter = "\t" if header.count("\t") > header.count(",") else ","
            stream.seek(0)
            chunks = []
            for chunk in pd.read_csv(
                stream, sep=delimiter, dtype=str, keep_default_na=False,
                chunksize=100_000, low_memory=False,
            ):
                missing = REQUIRED - set(chunk.columns)
                if missing:
                    raise ValueError(f"{archive_name}: source schema missing {sorted(missing)}")
                selected = chunk[chunk["office"].str.upper().isin(OFFICE_MAP)].copy()
                if not selected.empty:
                    chunks.append(selected)
            return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(
                columns=sorted(REQUIRED)
            )


def main() -> None:
    stamp = datetime.now(timezone.utc).isoformat()
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    with httpx.Client(timeout=180, follow_redirects=True, headers=headers) as client:
        commit_response = client.get(f"{REPO_API}/commits/main")
        commit_response.raise_for_status()
        commit_sha = commit_response.json()["sha"]
        listing_response = client.get(
            f"{REPO_API}/contents/individual_states", params={"ref": commit_sha}
        )
        listing_response.raise_for_status()
        archives = sorted(
            (
                item for item in listing_response.json()
                if item["name"].lower().endswith("24.zip")
            ),
            key=lambda item: item["name"],
        )
        if len(archives) != 51:
            raise RuntimeError(f"Expected 51 state/DC archives, found {len(archives)}")

        RAW_DIR.mkdir(parents=True, exist_ok=True)
        tables, source_files = [], []
        for item in archives:
            url = (
                f"https://raw.githubusercontent.com/MEDSL/2024-elections-official/"
                f"{commit_sha}/{item['path']}"
            )
            response = client.get(url)
            response.raise_for_status()
            payload = response.content
            actual_blob_sha = git_blob_sha1(payload)
            if actual_blob_sha != item["sha"]:
                raise RuntimeError(f"Git blob checksum mismatch for {item['name']}")
            local_sha = hashlib.sha256(payload).hexdigest()
            raw_path = RAW_DIR / f"{item['name']}"
            raw_path.write_bytes(payload)
            frame = archive_csv(payload, item["name"])
            if not frame.empty:
                frame["archive_name"] = item["name"]
                frame["archive_sha256"] = local_sha
                tables.append(frame)
            source_files.append({
                "name": item["name"], "size": len(payload),
                "git_blob_sha1": actual_blob_sha, "download_sha256": local_sha,
                "raw_path": str(raw_path),
            })

    if not tables:
        raise RuntimeError("No state-office observations found in MEDSL archives.")
    bronze = pd.concat(tables, ignore_index=True)
    bronze["office"] = bronze["office"].str.upper()
    bronze["mode"] = bronze["mode"].str.upper()
    bronze["votes_numeric"] = bronze["votes"].map(parse_votes)
    bronze["district"] = bronze["district"].map(lambda x: normalize_text(x, ""))
    bronze["candidate"] = bronze["candidate"].map(lambda x: normalize_text(x, "Unlisted candidate"))
    bronze["party_simplified"] = bronze["party_simplified"].map(lambda x: normalize_text(x, ""))
    bronze["state_po"] = bronze["state_po"].map(lambda x: normalize_text(x).upper())
    bronze["state_fips"] = bronze["state_fips"].map(lambda x: normalize_text(x).zfill(2))
    bronze["date"] = bronze["date"].map(lambda x: normalize_text(x, "2024-11-05"))
    bronze["precinct"] = bronze["precinct"].map(lambda x: normalize_text(x, "Unknown precinct"))

    # MEDSL explicitly warns that TOTAL rows and disaggregated voting modes
    # must not be summed together. We use TOTAL only and report excluded modes.
    total_rows = bronze[bronze["mode"] == "TOTAL"].copy()
    if total_rows.empty:
        raise RuntimeError("No mode=TOTAL observations found; refusing to sum mixed voting modes.")
    total_rows["votes"] = total_rows["votes_numeric"]
    missing_votes = int(total_rows["votes"].isna().sum())
    negative_votes = int((total_rows["votes"].fillna(0) < 0).sum())
    missing_district_rows = int(
        total_rows["office"].isin(["STATE HOUSE", "STATE SENATE"])
        .mul(total_rows["district"].eq(""))
        .sum()
    )
    valid = total_rows[total_rows["votes"].notna() & (total_rows["votes"] >= 0)].copy()

    normalized = []
    for office_name, group in valid.groupby("office", sort=True):
        office, geography = OFFICE_MAP[office_name]
        for row in group.to_dict("records"):
            state = row["state_po"]
            district = row["district"] or None
            if geography == "state_legislative_district" and not district:
                continue
            geography_id = state if geography == "state" else f"{state}:{district}"
            contest_id = f"US-{office.upper()}-2024-{state}-{district or 'STATEWIDE'}-{row['date']}"
            normalized.append({
                "election_year": 2024,
                "election_type": "general",
                "office": office,
                "contest_id": contest_id,
                "source_row_id": hashlib.sha256(
                    "|".join([
                        contest_id, row["precinct"], row["candidate"],
                        row["party_simplified"], row["county_fips"] if "county_fips" in row else "",
                    ]).encode()
                ).hexdigest()[:24],
                "geography_type": geography,
                "geography_id": geography_id,
                "geography_name": (
                    f"{office.replace('_', ' ').title()} District {district}"
                    if district else normalize_text(row.get("state"), state)
                ),
                "state_fips": row["state_fips"],
                "district": district,
                "candidate": row["candidate"],
                "party": row["party_simplified"] or None,
                "votes": int(row["votes"]),
                "total_votes": None,
                "result_status": "historical_final",
                "source_id": SOURCE_ID,
                "source_url": SOURCE_URL,
                "source_published_at": commit_sha,
                "extracted_at": stamp,
            })

    candidate_rows = pd.DataFrame(normalized)
    if candidate_rows.empty:
        raise RuntimeError("No usable governor/state-legislative rows after validation rules.")
    grouping = ["contest_id", "election_year", "office", "geography_type",
                "geography_id", "geography_name", "state_fips", "district",
                "candidate", "party"]
    aggregated = candidate_rows.groupby(grouping, dropna=False, as_index=False)["votes"].sum()
    denominators = aggregated.groupby("contest_id", as_index=False)["votes"].sum()
    denominators = denominators.rename(columns={"votes": "total_votes"})
    aggregated = aggregated.merge(denominators, on="contest_id", how="left")
    aggregated["source_row_id"] = aggregated.apply(
        lambda row: hashlib.sha256(
            f"{row['contest_id']}|{row['candidate']}|{row['party']}".encode()
        ).hexdigest()[:24], axis=1
    )
    aggregated["result_status"] = "historical_final"
    aggregated["source_id"] = SOURCE_ID
    aggregated["source_url"] = SOURCE_URL
    aggregated["source_published_at"] = commit_sha
    aggregated["extracted_at"] = stamp
    silver = pd.DataFrame(validate_records(aggregated.to_dict("records")))

    DATA_DIR.joinpath("bronze").mkdir(parents=True, exist_ok=True)
    DATA_DIR.joinpath("silver").mkdir(parents=True, exist_ok=True)
    bronze.to_parquet(BRONZE_PATH, index=False)
    silver.to_parquet(SILVER_PATH, index=False)

    public = (
        silver.dropna(subset=["party"])
        .groupby(
            ["election_year", "office", "state_fips", "geography_id",
             "geography_name", "district", "party", "total_votes"],
            as_index=False,
        )["votes"].sum()
    )
    public["state_po"] = public["geography_id"].str.split(":").str[0]
    public["vote_share"] = public["votes"] / public["total_votes"]
    public["contest_count"] = 1
    metadata = {
        "dataset": SOURCE_ID,
        "title": "MEDSL 2024 State Precinct-Level Returns",
        "doi": "10.7910/DVN/DODOBJ",
        "individual_state_doi": "10.7910/DVN/NYTPDU",
        "license": "CC0-1.0",
        "repository_commit": commit_sha,
        "source_validation": "git_blob_sha1_verified",
        "archive_count": len(source_files),
        "archive_bytes": sum(item["size"] for item in source_files),
        "bronze_rows": len(bronze),
        "total_mode_rows": len(total_rows),
        "silver_rows": len(silver),
        "contests": int(silver["contest_id"].nunique()),
        "missing_votes_excluded": missing_votes,
        "negative_votes_excluded": negative_votes,
        "missing_legislative_district_rows_excluded": missing_district_rows,
        "non_total_mode_rows_excluded": int((bronze["mode"] != "TOTAL").sum()),
        "years": [2024],
        "offices": sorted(silver["office"].unique().tolist()),
        "states_by_office": {
            office: sorted(group["state_po"].unique().tolist())
            for office, group in public.groupby("office")
        },
        "extracted_at": stamp,
        "source_files": source_files,
    }
    payload = {
        "metadata": metadata,
        "results": public.where(pd.notna(public), None).to_dict("records"),
    }
    PUBLIC_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        **{key: value for key, value in metadata.items() if key != "source_files"},
        "source_files": source_files,
        "bronze_path": str(BRONZE_PATH),
        "silver_path": str(SILVER_PATH),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in metadata.items() if key != "source_files"}, indent=2))


if __name__ == "__main__":
    main()
