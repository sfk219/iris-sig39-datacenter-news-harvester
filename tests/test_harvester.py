from pathlib import Path
from harvester import canonical_url, parse_date, process, normalize, parse_feed

FIXTURE = Path(__file__).parent / "fixtures_rss.xml"

def test_fixture_count():
    records, report = process(FIXTURE.read_bytes())
    assert report["fetched"] == 7
    assert report["accepted"] == 4
    assert len({r.source_id for r in records}) == 4

def test_duplicate_identity_with_tracking():
    a = canonical_url("https://www.datacenter-insider.de/demo/?utm_source=x")
    b = canonical_url("https://www.datacenter-insider.de/demo/")
    assert a == b

def test_dach_geography_and_null_geometry():
    records, _ = process(FIXTURE.read_bytes())
    assert {r.country_code for r in records} <= {"DE","AT","CH"}
    for r in records:
        if r.geo_status != "resolved":
            assert r.latitude is None and r.longitude is None

def test_malformed_feed_rejected():
    import pytest
    with pytest.raises(ValueError):
        parse_feed(b"<rss><item>")

def test_date_normalized():
    assert parse_date("Mon, 26 Oct 2026 09:00:00 +0100").startswith("2026-10-26T08:00:00")

def test_reject_missing_title():
    record, reason = normalize({"title":"","link":"https://www.datacenter-insider.de/test"})
    assert record is None and reason == "missing_title"
