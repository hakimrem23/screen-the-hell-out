# Private actual-record acceptance plan — not executed

> Historical planning baseline. The code gaps and cost recommendation are updated in [security-hardening readiness](SECURITY-HARDENING-READINESS.md). Hosted verification remains NOT RUN.

This plan is for a separately approved, authenticated staging deployment after the Phase 2 audit's hardening blockers are resolved. It never initiates orders or alters sealed records. The public preview and public CI remain synthetic. Existing contract compatibility checks do not equal a hosted end-to-end pass.

## Evidence boundary and inputs

An authorized reviewer selects the latest **completed and finalized** engine observation at test time. Freeze the dispatcher run ID, exact frontend/runtime version, approved engine source/protocol, both immutable journal commits, activation receipt, snapshot digest and finalizer proof. Record their identities only in approved private evidence storage. Do not hard-code a previously observed date as the latest session.

Use two independent read paths: the app's dedicated read-only GitHub credential and the owner's authorized GitHub review of the original sealed files. Compare byte hashes before checking visible fields. Do not rerun the scheduler, regenerate prices or count this later viewing as a new prospective observation. If fresh records do not exist, show the last verified session as STALE; do not manufacture today's result.

## Acceptance cases

| Case | Procedure | Required result |
|---|---|---|
| Anonymous access | Fresh Incognito session before OIDC; inspect ordinary page and WebSocket payloads in a controlled private test | No private ticker, date, count, price, proof or credential; no engine request before authorization |
| Wrong account / claims | Use a nonallowlisted account and a provider identity lacking verified email | Locked; no private data or fetch |
| Real OIDC | Sign in as approved owner; verify correct issuer/client/callback and identity mapping without dumping tokens | App identity authorized; no reliance on Community Cloud viewer identity |
| Expired/old identity | Exercise expired/missing/invalid issuance and expiry claims and approved maximum age | Denied before data retrieval/render; reauthentication required after hardening |
| Logout and multitab | Sign out, reopen URL, try another already-open tab | Current session clears private state; other tabs cannot regain private data beyond the documented enforced session policy |
| Revocation / rotation | Remove allowlist membership; rotate credential/cookie secret using approved invalidation/restart procedure | Denied/reauthenticated as defined; old report never appears newly current after a failed refresh |
| Actual provenance | Read latest finalized run; compare all A/B inventories, seal/snapshot hashes, pinned source/protocol and activation identities | Exact agreement; preserve exceptions; mismatch withholds records |
| Track A UI | Compare every category's row and distinct-ticker counts with original JSON; sample each available model and stock detail | Exact values; model overlap disclosed; adjusted levels labeled; missing entry/stop stays missing |
| No qualifying setups | If actual selected session has zero, verify zero; if not, retain synthetic negative test separately | No invented qualification or retrospective entry |
| Track B independence | Compare displayed paper counts and exceptions with sealed daily.json, separately from A | Exact agreement; no generated positions/outcomes; unchanged journal hashes |
| Data-quality failures | Compare raw-history failures, context failures, benchmark status and inherited exclusions | Missing stocks remain accounted for; no fill/repair or misleading clean status |
| Stale/future/calendar | Test real exchange timing and isolated fixture negative cases | Prior session marked STALE after readiness cutoff; future/incomplete/unverifiable record withheld |
| Token/proof errors | Invalid/revoked token, expired/missing log proof, schema mismatch and GitHub failure in isolated read-test harness | UNVERIFIED, no raw exception/secret/old current display; no fallback to unchecked prices |
| Redirect security | Instrument a controlled transport, never capture an actual bearer header in shared artifacts | GET only; bearer goes only to GitHub API, not signed blob redirect |
| Android operation | Chrome normal/Incognito, portrait, account switch, Wi-Fi ↔ mobile data, connection loss/reconnect | Usable controls; reauthorization on reconnect; no cross-user/server-session data bleed |
| Capacity | Measure response time, GitHub request count/rate budget and peak RSS with actual report size and approved viewer concurrency | Owner-defined limits met; no claim 512 MB is sufficient without measurement |
| Preservation | Recompare original A/B bytes; inspect frontend main, engine configuration and scheduler audit trail | No writes, dispatches, merges, journal changes or private content in public app/CI |

Some negative cases require a local/private instrumented harness; do not tamper with actual sealed files or weaken the production verifier to create them. Browser/network payload review may require an authorized desktop reviewer; Android alone cannot prove absence of browser-side leakage. No screenshots containing actual results should be stored publicly.

## Machine-readable private receipt

Retain: test ID, reviewer/time, selected immutable evidence identities, expected/actual boolean checks, failure reason codes, request-method/host counts with sensitive URLs removed, capacity measurements and overall result. Use PASS/FAIL/NOT RUN, not guessed passes. Keep real dates, tickers, counts, hashes, emails, browser captures and logs private. Publish only sanitized test status and approved source-code references to the public frontend PR. Never retain bearer tokens, cookies, OIDC tokens or signed URLs as test evidence.

**Acceptance state today: NOT RUN.** The 65 synthetic regression cases and earlier authorized sealed-schema compatibility check remain valid within their narrower scope. No real runtime GitHub token, OIDC login, hosting privacy setting, browser session or load/cost measurement has been validated.
