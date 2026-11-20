from collections.abc import Iterable

from .schema import ElectionRecord

REQUIRED_COLUMNS = set(ElectionRecord.model_fields)


def validate_records(rows: Iterable[dict]) -> list[dict]:
    accepted, seen = [], set()
    for row in rows:
        record = ElectionRecord.model_validate(row)
        key = (
            record.contest_id,
            record.election_year,
            record.office,
            record.geography_type,
            record.geography_id,
            record.district,
            record.source_row_id or record.candidate,
            record.candidate,
            record.party,
        )
        if key in seen:
            raise ValueError(f"duplicate election observation: {key}")
        seen.add(key)
        accepted.append(record.model_dump())
    return accepted
