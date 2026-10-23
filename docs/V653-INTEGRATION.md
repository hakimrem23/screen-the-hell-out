# Integration contract, setup and security

## Inspected contracts

The frontend V5 `app.py`, manual `shariah_gate.py`, strategy helpers, existing scan workflow and dark/mobile theme were inspected. The private engine's actual committed Track A `screen.json`, binding/hash inventory, Track B daily/seal schemas, approved coordinator/finalizer source and successful-run metadata were inspected read-only. This document deliberately records **schema only**, with no private observation date, ticker, price, result count, credential or real approval/source digest.

Track A V1: `schema_version`, `track=A_OPERATIONAL_SCREEN_ONLY`, `mode=AS_OBSERVED_SNAPSHOT_NOT_VALIDATED_RECOMMENDATIONS`, `session`, `source_sha`, `activation_receipt`, `snapshot_manifest_sha256`, `provider`, `data_observed_at`, `benchmark_status`, `universe_stocks`, `evaluated_tickers`, `category_rows`, `categories_by_unique_ticker`, `rows`, and safety flags. Rows are stock/model/setup records, not unique trade IDs. Each has ticker/date/model/category, pattern/confirmation, trend/volume context, trigger/plan, optional entry/stop/reward-risk/support/resistance, reasons, price basis and next-open gates. There can be multiple setups per stock/model; duplicate rows are not deduplicated into trades.

Track A's exact six-file inventory is `screen.json`, `screen.csv`, `REPORT.md`, `binding.json`, `accounting-audit.json`, `SHA256SUMS.json`. Its binding identifies immutable Track B commit, bundle digest, seal and shared activation/source identity. Track B's `seal.json` inventories its thirteen committed record files. `daily.json` has prospective mode, session/source/protocol/activation/snapshot identities, observed time, benchmark readiness, integrity, counts and exceptions. Its raw-history unavailable count can differ from Track A's indicator-context unavailable count.

The completed finalizer emits `BOTH_TRACKS_VERIFIED` with commit SHAs, hashes, session, activation receipt, coverage and verification time. The adapter reads this exact structured log record from the successful finalize job of a completed approved dispatcher run. It never treats an arbitrary successful Action or an unsealed JSON file as a verified report.

## Acquisition and verification

Only HTTPS GET requests to the fixed GitHub engine repository are implemented. No GitHub mutation, broker API, Yahoo call, workflow dispatch or engine execution exists in the adapter. The configured token needs **Contents: read**, **Actions: read** and implicit Metadata read, restricted to the engine repository. Do not grant write permissions for private draft-release access: this adapter reads committed files and run logs instead of large private release bundles.

Search is bounded to the last 20 completed dispatcher runs, newest first. Waiting/holiday runs with skipped finalize steps do not fabricate a session. Newer failed runs are disclosed. The latest finalized successful run must reference the owner-approved reusable source SHA and have a completed successful finalize job. Its exact proof is required; ambiguous or missing/expired logs fail closed. A corrupt selected finalized run never silently falls back to an older CURRENT result.

Both tracks are fetched by immutable **proof-selected commit SHAs**, never by a moving branch or an untrusted download URL. Files above the Contents API inline threshold use the Git Blob API, with strict byte-size/base64/Git SHA-1 verification followed by SHA-256 inventory/proof verification. Session, source, protocol, activation, snapshot, journal, category counts, full stock/model coverage and original safety flags must agree. This validates committed report integrity and trusts the approved finalizer's full archive checks; it does not redownload raw OHLCV, independently certify prices, reconstruct the entire predecessor chain or authenticate vendor lineage.

Signed job-log redirects allow only HTTPS GitHub Actions Azure/blob hosts, with Authorization removed. Redirects on ordinary API reads and redirects to other hosts are rejected. Requests are bounded by bytes and time, and errors shown to viewers use fixed safe messages rather than raw responses, exceptions or signed URLs. Provider strings are rendered as plain text/structured JSON; only escaped numeric summary values enter our HTML.

## Freshness

XNYS exchange calendar (`exchange-calendars==4.11.2`) determines the latest completed session after a 30-minute data-availability grace. Weekends, exchange holidays, early closes and DST are handled by the exchange calendar. The grace is a presentation availability policy matching the engine, not a strategy threshold. Once a newer session is expected, an older verified result is **STALE**, even before a delayed scheduled job runs. A future/incomplete session is withheld. No calendar fallback guesses a trading day. US session dates remain US session dates; fetch timestamps are additionally labeled in Asia/Kuala_Lumpur time.

`VERIFIED RECORDS` means integrity and binding checks passed, never independently verified market data or validated signals. Degraded benchmark/history/context exceptions remain visible. Historical reconstructed data and synthetic fixtures are not prospective evidence.

## Owner setup checklist — review before enabling

1. Review the draft implementation and synthetic preview. Keep the public deployment in default `synthetic_preview` mode. No actual credential is needed for review.
2. Explicitly approve authenticated private disclosure and record the approval reference. V1 does not support public disclosure of private results, even if an authenticated operator opens a public URL.
3. Use a hosting deployment approved for the data's audience. Configure Streamlit OIDC `[auth]` in the hosting secret store with correct HTTPS callback, identity-provider client secret and cookie secret. Install requirements (including `streamlit[auth]`). The new tab offers sign-in only when this authentication is configured. Private rendering requires `st.user.is_logged_in`, a verified email claim and exact server allowlist membership on every render. Providers without a verified-email claim are blocked until a separately reviewed identity policy exists.
4. Store the placeholder example's `[v653]` values **only on the server**. Set `mode=private`, explicit owner approval, `audience=authenticated_private`, an approval reference, approved email list and the **exact reviewed** executable SHA/protocol digest from private engine records. Do not use `main` as a source pin. No real pins/approval dates are prefilled in this public repo.
5. Supply a dedicated fine-grained read-only token or appropriately scoped short-lived GitHub App token for the engine. Configure server outbound HTTPS to `api.github.com` and approved signed GitHub Actions log hosts. Never use browser token inputs or frontend build variables. Revoke/rotate according to the host's policy.
6. Authenticate as an approved viewer. Verify the selected run, hashes, session, coverage and degraded warnings against the private engine. Test an unauthorized/anonymous session, invalid token, altered pin and failed refresh: no private rows should render. This real authenticated deployment check remains an owner action; mocked tests do not establish it.
7. Only after review, decide separately whether to merge and deploy. Neither this change nor its CI merges, publishes a site, enables a scheduler or changes an engine pin.

No shared Streamlit data cache, disk cache, public export or private CI fixture is used. Private results reside only in the authorized viewer's server session for at most 120 seconds before revalidation; freshness and access are rechecked on render. Token values are not cached with the report. A failed refresh clears the old result. Revoked viewer access clears cached data before another fetch. Time passage alone does not refresh a closed or idle browser; opening/rerendering or Refresh rechecks it.

## Limits and safe failure

- Production workflow logs can expire or be deleted. Without the exact final proof the adapter reports UNVERIFIED; it does not weaken permissions or invent a durable proof. A future durable verification index requires separate engine review.
- GitHub rate limits, oversized responses, schema drift, missing files, unavailable calendar or unapproved source changes withhold records. Reads are sequential and bounded, with no aggressive retries. Refreshes may involve several dozen read requests; provision suitable per-token rate limits before multiuser rollout.
- This task does not enable authentication on an existing public deployment, configure a token, test an actual private browser session, deploy, or grant public disclosure approval. It provides the implementation and explicit gate for owner-controlled setup.
- V5 registry/technical functions and scheduler remain unchanged. V6.5.3 categories never write back to V5 data or paper journals. No paper trades are created and no performance statistics are inferred.
