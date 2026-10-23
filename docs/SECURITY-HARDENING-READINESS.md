# Private-viewer security hardening and cost readiness

24 October 2026, Asia/Kuala_Lumpur. **Review-ready code; hosted activation NOT APPROVED.** Nothing is merged, deployed or purchased. No production source pin, schedule, strategy, data or paper journal was changed.

## Recovery / what was already saved

Draft frontend PR #1 previously contained integration commit `c682faea4b8dcfb50fa23f367ef5bb02620efca7` and documentation commit `ee73f5e5b5a53b23332e40d25daf0d7dea1b0d5c`. The interrupted workspace retained four changed files, two new security/test files and a 91-pass local test receipt; none of those security files had been pushed. Those changes were continued, not recreated. A recovery checkpoint is saved as `b8b81eb399c05c8cbec4e9426a5e46f0730c2757` with 93 passing cases. This report describes the completed follow-up.

## Repository identity and dependencies

[Draft PR #1](https://github.com/hakimrem23/screen-the-hell-out/pull/1) targets the **main branch of `hakimrem23/screen-the-hell-out`**, the existing V5 frontend repository. It does **not** target `hakimrem23/stho-moomoo-test`, the separate main STHO screening/research engine. Neither main branch is modified.

The integration requires the existing engine's approved dispatcher/finalizer, accessible completed-run logs, committed Track A/B schemas/seals and immutable source/protocol trust anchors. No research PR merge or new engine workflow is required. Runtime dependencies: Python 3.12, Streamlit OIDC/Authlib, exchange calendar and the tested `requirements-private.lock`; Google/OIDC issuer/client/claims; host HTTPS, cookies and WebSockets; narrowly scoped GitHub Contents/Actions read access. The chat's GitHub App connection is not the deployed application's credential.

## Implemented controls

- Explicit **Sign out of private screening** clears private records, session receipts and stock/category selectors before `st.logout()`. V5 session state is preserved. A logout failure still withholds data and displays a safe message.
- Authentication requires exact configured issuer/client audience, subject, verified allowlisted email, valid numeric `iat`/`exp`, no future issuance, unexpired identity and a bounded maximum age (default one hour). Multiple-audience tokens need the reviewed authorized-party claim. Unknown/malformed claims fail closed.
- Mandatory server cutoff `auth_not_before_utc` rejects older signed identities in **new browser sessions too**. Required credential/session generation strings support controlled revocation. Generation changes and a GitHub token digest invalidate active-session receipts and cached results immediately on the next check. The digest stays server-side and is never rendered or logged; actual tokens are not stored with report records.
- Private-only fragments recheck authorization every 30 seconds while connected, before cached reads and again after a network retrieval. Credentials/identity changing during a read cannot produce a displayed/cached result. The public synthetic preview has no new timer or network operation.
- Already delivered information cannot be retroactively removed from a viewer's memory or screenshots. Idle/disconnected tabs are not an instant revocation channel. The policy applies on connected rechecks/reconnects; host restart plus cutoff handles existing sessions across replicas.
- `requirements-private.lock` records the tested Linux/Python dependency set; CI resolves both the public requirements and this lock. Existing V5 function and protected-file checks remain in place.

### Rotation / revocation procedure — part of the security boundary

A secret-store edit is not assumed visible to running Python processes. Before re-enabling a rotated private service: stop/restart **all** instances/sessions, install the replacement read-only token, revoke the old one, advance `credential_generation` and `session_generation`, set `auth_not_before_utc` to the rotation boundary, and rotate the Streamlit `[auth]` cookie secret. Deploy/restart requires separate owner approval and is not performed here. Newly signed identities must satisfy the cutoff. Removing a viewer also requires active configuration/restart where the host does not hot-reload secrets.

Automatic token-digest comparison protects an already-running session once updated settings are visible; it is **not** a substitute for the full rotation procedure. Missing generation/cutoff configuration locks private mode rather than accepting old cookies. Public hosting never receives these private settings.

## Automated versus hosted verification

Local completed result: **97 passed, zero failures/errors/skips**: the original 65 cases plus 32 security cases. Test fixture identities now include explicit valid claims; original test scenarios remain. Coverage includes expiry/max age, malformed claims, wrong issuer/audience/party, cutoff rejection, fresh re-login, identity switch, token/generation rotation, retry bypass attempts, cached expiry, expiry/rotation during retrieval, explicit sign-out, logout failure and no unauthorized fetch/render. Network providers are mocked; fixtures are invented.

The original V5/Shariah protection checks pass. Hosted Google/OIDC callback, real cookies/logout/multitab revocation, active-secret propagation, bearer scope/expiry, WebSocket reconnect, Android behavior, complete container memory and concurrency tests are **NOT RUN**. Software tests and earlier local sealed-record compatibility do not imply hosted authentication, quote correctness or trading accuracy. See [private E2E plan](PHASE2-PRIVATE-E2E.md); no raw private observation is added to public fixtures/artifacts.

## Measured memory and cheapest reasonable pilot

Method: fresh isolated Linux processes, two repetitions each, using an authorized **local copy of a sealed historical observation**, public V5 snapshot loading, imports/calendar, GitHub JSON/base64 allocation simulation, independent retained AppTest sessions, all category tables and three refreshes. All input bytes remained unchanged. Only sanitized RSS/time measurements are published in [sealed-fixture results](security-validation/memory-local-sealed.json); no session identity, ticker, price, stock/trade count or original digest is published. A small [synthetic comparison](security-validation/memory-local-synthetic.json) is explicitly separate.

| Retained viewers | Measured peak process RSS, MiB (two runs) |
|---|---:|
| 1 | 216.00 / 217.20 |
| 3 | 231.26 / 240.42 |
| 5 | 258.50 / 255.54 |

These are **process high-water marks, not complete service requirements**. AppTest sessions were retained together but requests refreshed sequentially. No real HTTP/TLS/OIDC server, browser, parallel fetch burst, V5 on-demand charts, day-long soak or enforced memory limit was tested. RSS includes shared mappings and differs from platform/cgroup memory accounting. Do not extrapolate beyond measured sessions.

| Hosting tier | Planning comparison | Decision |
|---|---|---|
| 512 MB, about US$7/month | Conservatively 488.28 MiB if provider labels use decimal MB; a 25% reserve leaves 366.21 MiB. Maximum measured RSS 258.50 MiB leaves roughly 107.71 MiB within that illustrative budget for unmeasured overhead. Actual provider units/overhead remain unverified. | **Plausible minimum-cost single-viewer staging pilot**, subject to owner approval and capped hosted tests; reliable operation is not yet proven. |
| 2 GB, about US$25/month | Conservatively 1907.35 MiB if decimal; 25% reserve leaves 1430.51 MiB. Much larger headroom. | Fallback for memory/load failures or broader use. Current local results do not justify requiring it for the first single-viewer pilot. |

Prices are planning figures from [Render pricing](https://render.com/pricing) and its [official tier comparison](https://render.com/articles/top-heroku-alternatives-agencies), excluding applicable taxes, workspace/identity charges and excess usage. Confirm checkout before buying; nothing was purchased. A provider-managed HTTPS web service still needs the application's authentication gate. Keep public preview and private credentials on separate services.

Before accepting 512 MB, run the real locked server under the provider's actual cap, measure cgroup/container peak through login/category refresh/reconnect and a soak, and verify no OOM/restart, failed authorized request or credential leakage. Start with one viewer and monitor; upgrade only on evidence. Also measure GitHub rate budget: 30-second authorization checks can trigger per-viewer data reloads after the existing 120-second cache TTL. Small RSS alone does not establish affordable/reliable multiuser service.

### Reproduce without exposing private data

```bash
python -m pip install -r requirements.txt -r requirements-private.lock
python -B -m tests.run --output /tmp/security-tests
python -B -m tools.memory_profile --output /tmp/synthetic-memory.json --viewers 1,3 --repeats 2
# Authorized LOCAL fixture only; output must be outside the source directory:
python -B -m tools.memory_profile --sealed-folder /OWNER/PRIVATE/COPY --output /tmp/sealed-memory.json --viewers 1,3,5 --repeats 2
```

The optional private directory has `a/`, `b/` and `log.txt` copied through authorized read access. The tool verifies inventories/proofs, never makes market requests, never outputs payloads and refuses output inside the input directory. Private records must never be mounted into public CI. Normal CI remains synthetic-only.

## Android-friendly owner checklist — no provisioning today

1. Review this code PR and name the intended private viewers in a secure owner record. Confirm the optional **US$7/month single-user staging budget**; approving code is not approval to purchase/deploy.
2. Use Android Chrome → Desktop site for hosting/Google dashboards and a password manager for secrets. Keep the current public app and its settings untouched. Do not paste tokens/cookies into chat, GitHub or screenshots.
3. After separate deployment approval, create a separate private-data runtime from the reviewed commit/lock. Disable auto-deploy and secret-bearing PR previews. Begin in synthetic mode with no engine token. Use the [hosting runbook](PHASE2-PRIVATE-HOSTING.md) for future setup commands; none has been executed.
4. Register the exact HTTPS origin and `/oauth2callback` URL with the chosen OIDC provider. In server `[auth]`, configure client ID/secret and stable random cookie secret. In `[v653]`, configure matching `oidc_issuer` and `oidc_client_id`, verified-email allowlist, one-hour max age (or reviewed policy), cutoff/generations, owner approval and reviewed engine pins. The expanded [example](../.streamlit/secrets.example.toml) contains placeholders only and remains synthetic by default.
5. Add a dedicated engine-only read credential: Contents read, Actions read, implicit metadata; no write/admin/dispatch scope. Follow the rotation procedure above. A Community Cloud viewer login or reverse proxy alone does not populate the OIDC identity required by this code.
6. Only after authorization, run actual-record acceptance privately: allowed user, unauthorized/Incognito user, expiry, sign-out, second tab, revoked identity, token rotation, Wi-Fi/mobile reconnect, date/status, all A/B counts/warnings, unchanged original hashes and capped memory. No public screenshots or browser token capture. Existing records are not new prospective evidence.
7. Accept the small tier only if real memory, API-rate and OIDC tests pass; otherwise keep private mode disabled and reassess the 2 GB tier. Stop before any public merge or rollout; obtain separate approval for each deployment change.

**Outstanding blockers:** live hosted acceptance, actual 512 MB cap/soak/API measurements, configured and verified OIDC/read-only credentials, owner hosting/privacy/budget approval. Community Cloud suitability for private financial records remains unresolved as documented in the earlier plan. No production scheduler or original research integration change is needed.
