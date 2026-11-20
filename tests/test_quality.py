import pytest

from electoral.quality import validate_records


def row(**overrides):
    base = dict(
        election_year=2024,
        election_type="general",
        office="president",
        contest_id=None,
        source_row_id=None,
        geography_type="state",
        geography_id="US-CA",
        geography_name="California",
        state_fips="06",
        district=None,
        candidate="Candidate A",
        party="DEM",
        votes=100,
        total_votes=200,
        result_status="certified",
        source_id="test.dataset.v1",
        source_url=None,
        source_published_at=None,
        extracted_at="2024-11-10T00:00:00+00:00",
    )
    return base | overrides


def test_valid_record():
    assert len(validate_records([row()])) == 1


def test_reject_negative_votes():
    with pytest.raises(ValueError):
        validate_records([row(votes=-1)])


def test_reject_duplicates():
    with pytest.raises(ValueError, match="duplicate"):
        validate_records([row(), row()])


def test_reject_invalid_fips():
    with pytest.raises(ValueError, match="state_fips"):
        validate_records([row(state_fips="6")])


def test_same_candidate_can_appear_in_distinct_contests():
    records = validate_records([
        row(office="house", contest_id="US-HOUSE-2024-CA-CD1-GEN-S0-R0", geography_type="congressional_district", geography_id="CA-CD1", district="1"),
        row(office="house", contest_id="US-HOUSE-2024-CA-CD2-GEN-S0-R0", geography_type="congressional_district", geography_id="CA-CD2", district="2"),
    ])
    assert len(records) == 2
