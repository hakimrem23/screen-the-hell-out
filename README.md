# STHO — V5 dashboard + V6.5.3 Screening Integration V1

The existing mobile-first dark V5 dashboard keeps its Discover, Watchlist, Deep Dive and Syariah views. A fifth navigation tab, **V6.5.3 Screening**, consumes read-only reports from the separate screening engine. It never runs or changes a trading strategy.

**Default: synthetic preview.** Every V6.5.3 example is invented, including tickers, prices, dates and counts. No private data, GitHub token or market connection is needed. This public repository contains no private screening snapshots.

## Run the preview

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Select **V6.5.3 Screening**. Test each category and the zero-qualified toggle. Unknown entry prices/stops remain blank. The existing V5 snapshot files remain separate; V6.5.3 never writes to `data/` or uses the V5 on-demand quote functions. Streamlit's authentication extra/minimum 1.50 supports stable server-side identity APIs; existing V5 functions and safeguards remain unchanged. No hosting deployment or merge is performed by this change.

## What the new tab shows

- US exchange screening-session date; verified-record/current/stale status.
- Stock inventory accounted for, valid histories and category-level unique tickers.
- Qualified, Watchlist, Rejected and Data Unavailable, with overlapping model counts disclosed.
- Data-quality exceptions, benchmark warnings and unresolved coverage.
- Per-stock model, pattern, reasons, trend/volume, support/resistance, entry plan, initial stop/risk and reference reward/risk where supplied.
- Independent Track B paper-journal counts. No strategy performance estimate or trading recommendation is inferred.

Technical qualification is separate from unchanged fail-closed manual Shariah evidence checks. Neither a technical match nor a manually recorded compliant report is independent certification. Adjusted reference levels are not broker-executable orders.

## Private access — disabled until explicitly approved

**Security guards are implemented; private activation remains NO-GO until hosted OIDC, rotation and capped-memory acceptance pass.** See the [security changes, measured memory and Android checklist](docs/SECURITY-HARDENING-READINESS.md). See the [hosting recommendation and Android runbook](docs/PHASE2-PRIVATE-HOSTING.md) and [actual-record acceptance plan](docs/PHASE2-PRIVATE-E2E.md). No deployment is authorized.

An owner must approve **authenticated private disclosure**, configure OIDC authentication and allowlisted verified emails, and add a narrowly scoped server-side GitHub credential. A token alone, a public deployment, an unverified identity, a query parameter or a UI checkbox cannot enable private results.

See [setup and security](docs/V653-INTEGRATION.md) and the placeholder-only [secrets example](.streamlit/secrets.example.toml). Never commit real secrets or put private outputs into public issues, PR descriptions, CI artifacts, screenshots, caches or downloads. Public display of private results is unsupported in V1; it would require a separate owner-approved change.

## Tests

```bash
python -B -m tests.run --output /tmp/stho-integration-tests
```

Tests use fictional reports and mocked GET transports. They cover complete coordinator-to-UI ingestion, both-track hashes/bindings, freshness/holidays/DST/early closes, credentials/authentication/redirect handling, zero signals, unavailable data, safe text rendering, cache revocation/failed refresh and V5/Shariah preservation. They do not test trading accuracy. [Validation and delivery status](docs/VALIDATION.md).

Manual-only staging: [Render 512 MB / $7 readiness and owner gates](docs/RENDER-STAGING-READINESS.md). No deployment or purchase has been authorized.
