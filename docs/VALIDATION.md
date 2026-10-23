# Integration V1 validation and delivery

**Local software tests: 65 passed, 0 failures, 0 errors, 0 skips.** See [exact summary](validation/summary.json), [test log](validation/tests.log) and [environment](validation/environment.json).

| Suite | Passed |
|---|---:|
| Record schema, seals, bindings, coverage and exchange calendar | 23 |
| Authorization, GET transport, redirects and complete read lifecycle | 24 |
| Real Streamlit AppTest navigation, preview and privacy failures | 12 |
| V5 source/function preservation and Shariah safeguards | 6 |
| Total | 65 |

All software cases use invented symbols, dates, values, credentials and proofs, with network transports mocked. The complete existing V5 function ASTs, Shariah/strategy modules, theme, registry and production scan workflow are checked against public frontend baseline `8bf90309058dc043efc94191b341a8ba02926493`. No scanner workflow, strategy, threshold or journal is modified. Only app navigation/routing is added; dependencies include Streamlit's authentication extra and the exchange calendar.

Tests include XNYS holidays, weekends, early close and DST; pending/zero signals; stale/future observations; exact all-file hashes, duplicate/nonfinite JSON, incomplete/model coverage, source/receipt/session mismatches; strict Git commit reads; failed and waiting runs; expired proof logs; signed redirects without Authorization; login/allowlist/owner gates; failed refresh and revoked-access cache removal; unsafe-looking provider text; and unchanged manual evidence expiry/duplicate/noncompliance behavior.

A separate **authorized private contract check passed** against actual sealed Track A/B bytes and the completed finalizer log obtained through the existing GitHub connection. Only the boolean result is recorded here. Those bytes were kept outside the frontend workspace and are absent from public code, fixtures, previews and test artifacts. This verifies compatibility with inspected report schemas/hashes; it is **not** an end-to-end test of a newly configured application token, OIDC deployment, independent stock-price verification or trading accuracy.

`pip check` passed. No GitHub-hosted CI success is claimed before an actual remote run. The new read-only CI workflow is prepared but cannot run until the frontend branch is pushed.

## Publication status

The earlier GitHub App repository-scope blocker is resolved. The owner added the frontend to the selected repositories, and access was independently confirmed before publication. All 65 local tests were rerun successfully with zero failures/errors/skips; no implementation changes were needed.

This change is published only on `feature/v653-streamlit-integration-v1` for a draft PR against `main`. Synthetic-only read-only CI runs on that branch/PR. The previous HTTP 403 remains historical context, not a current blocker. Real application-token/OIDC deployment and private disclosure approval remain separate owner actions.

Main, the existing frontend scanner, private engine scheduler, approved executable pin, paper journals and original research remain untouched. Private mode remains disabled; no merge or deployment is authorized or performed.


## Security hardening follow-up

The original 65 scenarios are retained. Current local result: **97 passed, 0 failures, 0 errors, 0 skips**, including 32 identity/session security cases. [Current exact receipt](security-validation/summary.json), [test log](security-validation/tests.log) and [security/memory/readiness report](SECURITY-HARDENING-READINESS.md). Hosted OIDC and capped-container acceptance remain NOT RUN.
