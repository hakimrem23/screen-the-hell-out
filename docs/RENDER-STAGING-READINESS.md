# Manual Render staging readiness — NOT DEPLOYED

Baseline: Draft frontend PR #1, previously passing commit
`2928a53c7afce3be7f18129ecc21de71b90c6553` (97 tests).
This addition prepares staging only. No resources, purchases, deployment,
production secrets, scheduler edits or private reports are included.

## Cost and isolation

Target: one web service, one instance, 0.5 CPU / 512 MB, US$7/month compute.
The inert `staging/render.yaml.example` uses current plan ID `0.5c-512mb`
(the former Starter name). Auto-deploy and preview generation are off.
No autoscaler, disk, database, worker, cron, paid workspace or second service.
Do NOT connect/import the template before explicit owner approval: an initial
Blueprint creation can deploy even with automatic deployments disabled.

The launcher checks the declared $7 / one-viewer policy, but cannot enforce
Render account billing or prevent dashboard edits. It makes no Render API calls.
Owner must verify the final price, workspace/build/bandwidth allowances and any
other charges before creation. A budget alert is not a hard spending cap.
If a strict $7 total cap cannot be guaranteed, do not activate. Never upgrade to
2 GB automatically; suspend staging if 512 MB fails. Previous documentation's
$25 fallback requires a NEW budget approval and is outside this task.

Single viewer means one allowlisted Google identity in private mode, one instance
and one active browser tab during acceptance. It is not a distributed session
concurrency limiter; duplicate tabs remain possible and must be tested.
The endpoint is Internet-reachable; private report authorization occurs in app.

## Prepared files and local rehearsal

- `staging/render.yaml.example`: manual configuration reference, not root Blueprint.
- `staging/environment.example`: nonsecret defaults and private secret instructions.
- `staging/app.py`: separate compact V6.5.3-only entrypoint; V5 remains unchanged.
- `staging/launch.py`: fresh temporary HOME/cwd, synthetic secrets by default,
  dark theme, CORS/XSRF enabled, sanitized 5-second memory samples.

Install locked dependencies, then `python staging/launch.py` from repository root.
Default `PORT=8501`; check `http://127.0.0.1:8501/_stcore/health` returns `ok`.
The health endpoint proves process availability only, not OIDC, GitHub access,
record freshness or strategy accuracy. No credential belongs in health output.
Synthetic mode ignores mounted private settings. No private inputs are needed.
Do not publish real secrets, raw logs, screenshots or reports in this public repo.

## Android-friendly owner steps — approval gates, not actions already taken

1. Review Draft PR #1 and passing CI on its exact head SHA. Save that SHA as the
   candidate release; save the previous SHA above as the code rollback reference.
2. Approve a separate synthetic-only staging service and a maximum $7 monthly
   compute commitment explicitly. Check Render checkout on Android Chrome using
   Desktop site if controls are hidden. Stop before Create if any cost differs.
3. Only after approval, create a NEW uniquely named service using the inert
   template values. Do not attach an existing public app or engine service.
   Disable automatic deploys and previews; confirm one instance/no autoscaling.
   Deploy the reviewed specific commit manually, not an unchecked branch tip.
4. Test synthetic screens and health. Do not add GitHub credentials yet.
5. Separate approval is required for private sealed data. Create staging-only
   Google OAuth Web client; register exact HTTPS `/oauth2callback`. Limit Google
   test users and application `allowed_emails` to the one approved owner identity.
6. In Render Secret Files create `staging-secrets.toml` from the commented template
   `.streamlit/secrets.example.toml` plus the `[auth]` keys described in
   `staging/environment.example`. Fill server-side only. Set reviewed source and
   protocol pins; cutoff/generations and unique cookie secret are mandatory.
   Use a NEW narrowly scoped read-only GitHub credential, never production token.
   Set private mode and explicit private approval flag only after permission.
   Secret saves/restarts may deploy: treat these as owner-approved operations.
7. Restart the isolated service, complete the hosted gates below, retain evidence
   privately. Do not merge this PR or alter either production environment.

## Hosted acceptance matrix — ALL NOT RUN

| Gate | Required evidence / pass condition |
| --- | --- |
| Google OIDC | Exact HTTPS callback; correct iss/aud/sub/verified email; approved account works, another account and anonymous session get no private payload; browser contains no GitHub credential. |
| Sign-out | Logout clears cached rows; refresh, browser back, second tab and reconnect cannot fetch authorized data after logout/session policy expiry. Record any pre-rendered browser content limitation; no claim of remote erasure. |
| Expiry | Short test max age (minimum supported 60s); idle, reconnect and refresh with expired identity all withhold results. Active UI reevaluates every 30s; inactive/disconnected tabs recheck on reconnect. |
| Revocation | Revoke staging GitHub token; retrieval fails closed. Rotate cookie secret, cutoff and both generations; restart every replica; old cookies/new tabs rejected, fresh login accepted. Google account revocation alone is not guaranteed immediate app-session revocation. |
| 512 MB | Actual provider cap visible; one viewer, repeated refresh/category changes, reconnects, credential rotation and 24-hour soak. No OOM/restarts; total cgroup peak <=75% of actual cap. RSS alone insufficient. Fail => suspend, no upgrade. |
| GitHub limits | Use staging-only read credential; record sanitized limit/remaining/reset and request counts privately. Test 401,403,429,5xx and Retry-After with synthetic transport; current adapter withholds data on errors. No rapid retries. Budget daily usage below 50% of credential's actual quota; no assumption that limits are fixed. |
| Sealed contract | GET-only retrieve approved completed finalizer, proof, immutable A/B commits. Match hashes, source/protocol/session/activation bindings; stale or invalid records withheld/labeled. No workflow dispatch or engine writes. |
| Isolation | Public V5 URL/source and engine scheduler pins unchanged; no production token mounted; staging logs/health contain no payload/identity/secret. |

The adapter's 120-second per-session cache is not a global API limiter. Browser
refreshes/reconnects or several tabs can consume more requests. Until hosted
request counts are known keep one tab, avoid repeated manual refresh, and stop
private access if quota headroom fails. No hosted rate-limit or OIDC test is claimed.

## Memory monitoring and rollback

Launcher writes only `STAGING_MEMORY` numeric RSS and cgroup v2 current/limit;
missing/unlimited values are null (UNKNOWN), not zero or proof of safety.
Compare with Render container metrics and restart/OOM events; verify cgroup path
on the host. Monitoring alerts only; no automatic scaling or paid action.
Previously measured local sealed-fixture AppTest peak: 217.20 MiB for one viewer.
This excludes real OIDC/HTTP/container concurrency, and is not capped-host proof.

Failure/revocation: owner suspend staging immediately; revoke staging token,
rotate cookie/cutoff/generations, remove private secret file and switch to synthetic.
Manually redeploy the reviewed previous code SHA only if it includes the intended
launcher, otherwise use the previous Streamlit app command with synthetic secrets.
Do not restore a private secret from an earlier deployment. Confirm Render's
rollback handling of environment/secret changes separately: code rollback is not
credential rollback. Restart, recheck synthetic health and absence of private rows.
Delete or suspend only this new staging service to stop its ongoing compute;
verify billing consequences in account UI. Never touch production services.

## Integration evidence and limitations

The unchanged frontend adapter is fixed to `hakimrem23/stho-moomoo-test`, GET only.
Requires Contents read, Actions read and metadata; no write/dispatch permissions.
Existing automated cross-track tests cover complete mocked reads, sealed hashes,
source/session bindings, errors and unauthorized access. An authorized local copy
of real sealed A/B records can be verified offline without publishing its contents.
This establishes schema compatibility only: hosted credential permissions, log
availability, current source approval, corporate-action truth and OAuth behavior
still need owner-authorized live checks. The engine/scheduler require no changes.
Public code/config contains no real sealed session or provider data.

Offline results: **105 passed, 0 failures, 0 errors, 0 skips** (all inherited 97 plus 8 staging tests). Includes a real loopback Streamlit health check and a synthetic UI test with adapter calls forbidden. Initial socket-restricted attempt failed; rerun with network permission passed. Authorized local sealed A/B contract verification also passed without publishing any payload or changing evidence. Results are in `docs/staging-validation/`. Hosted gates remain NOT RUN.
These tests are software evidence, never trading-accuracy evidence.

Official references checked for preparation:
- https://render.com/docs/blueprint-spec (current plan/auto-deploy fields)
- https://render.com/pricing (512 MB / $7 target; owner checkout confirmation required)
- https://render.com/docs/configure-environment-variables (server secret files)
- https://docs.streamlit.io/develop/concepts/connections/authentication

Recommendation: configuration ready for review; NO-GO for private activation
until owner budget/data approval and all hosted gates pass.
