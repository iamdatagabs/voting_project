import pandas as pd

from scripts.ingest_mit_countypres import clean_fips


def test_clean_fips_preserves_leading_zeroes():
    assert clean_fips("1001") == "01001"
    assert clean_fips("06037") == "06037"


def test_clean_fips_rejects_non_fips_units():
    assert clean_fips("—") is None
    assert clean_fips(pd.NA) is None
