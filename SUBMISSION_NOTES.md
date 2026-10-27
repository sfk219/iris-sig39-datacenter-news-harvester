# Reviewer handoff · IRIS-SIG-39

**Scope:** DataCenter-Insider RSS/Atom to DACH signal staging.

This repository contains an independent demonstration adapter with Python 3.12, PostgreSQL 16, PostGIS 3.4, sample RSS fixture, pytest tests and GitHub Actions smoke tests.

**Run fixture:**
```bash
python -m pip install -r requirements.txt
python -m pytest -v
python harvester.py --fixture tests/fixtures_rss.xml --dry-run
```

**Database demonstration:**
```bash
cp .env.example .env
docker compose up -d --wait
python harvester.py --fixture tests/fixtures_rss.xml
python harvester.py --fixture tests/fixtures_rss.xml
```

**Data and schema caveat:** This demo does not access or claim compatibility with undisclosed IRIS production credentials or DDL. Fixture content is synthetic. Publisher feed live access and Docker database outcomes must be validated in a network-capable environment. A more extensive offline source bundle and detailed PDF are included with the email submission.
