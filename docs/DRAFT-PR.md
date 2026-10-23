# STHO V6.5.3 Streamlit Integration V1 — synthetic preview and gated read-only adapter

Adds a **V6.5.3 Screening** navigation tab to the existing dark/mobile V5 dashboard. Default output is entirely synthetic; no private report samples or credentials are committed. Existing V5 functions, technical helpers, manual Shariah safeguards and scheduler are preserved.

The server-only GitHub adapter accepts the latest completed approved dispatcher run with a successful finalizer, then verifies both committed tracks at immutable SHAs: SHA-256 inventories, source/protocol/activation/session/snapshot bindings, coverage and category counts. It uses HTTPS GET only with Contents/Actions read scope, strips Authorization on allowed signed log redirects and never calls a market/broker API or workflow dispatch. Missing proofs, unapproved pins, mismatches and expired logs fail closed as UNVERIFIED; the exchange calendar marks old sessions STALE.

Displays date, accounted-for/valid histories, qualified/watchlist/rejected/unavailable categories, preserved quality warnings, stock context and supplied entry/stop/support/resistance references. Pending entries remain blank; a zero-signal day stays zero. Track B paper counts remain separate. A technical result never becomes a BUY or independent Shariah certification.

Private access is disabled unless server owner approval, private audience, reviewed pins, read-only credential, OIDC verified identity and email allowlist all pass. No public disclosure mode, shared report cache, disk cache, private CI fixtures or private export. Failed refresh/revocation clears the prior result.

Validation: **65 local tests passed, zero failures/errors/skips**, including real Streamlit AppTest and preserved V5/Shariah checks. `pip check` passed. Actual sealed-report compatibility was checked read-only via the existing authorized connection, without copying any private payload into this public change. Real application-token/OIDC deployment remains unverified until owner setup. No remote CI result is claimed before branch creation.

See README.md, docs/V653-INTEGRATION.md and docs/VALIDATION.md for setup, verification boundaries, exact results and remaining limitations. Engine source, thresholds, schedulers, journals and historical evidence are unchanged. This must remain a draft; do not merge or deploy automatically.
