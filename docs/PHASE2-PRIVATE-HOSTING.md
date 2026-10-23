# Integration Phase 2 — private hosting decision and Android runbook

> Historical planning baseline. The code gaps and cost recommendation are updated in [security-hardening readiness](SECURITY-HARDENING-READINESS.md). Hosted verification remains NOT RUN.

Prepared 24 October 2026 (Asia/Kuala_Lumpur). **Planning/audit only: NO-GO for enabling private results today.** No merge, deployment, secret configuration, actual-result exposure or scheduler change is performed. The public V5 and synthetic preview remain unchanged.

## Recommendation and estimated cost

Use a **separate managed Render web service**, one instance, with Google OIDC and an explicit application email allowlist. Keep the existing public app in synthetic-preview mode. This separates private credentials, runtime sessions and release controls from the public deployment while avoiding VPS patching or a new database. GitHub remains the record authority. A publicly reachable HTTPS endpoint is not a public-data approval: anonymous users must receive no private payload.

Budget **USD 25/month compute for a 2 GB instance**, plus applicable taxes, excess usage, workspace or identity-provider charges. The documented USD 7/month / 512 MB option is a smaller pilot option; memory suitability for this dashboard is unmeasured. Do not buy it assuming capacity is proven. Confirm current checkout pricing and the applicable workspace plan before paying. No subscription or account has been created. [Render's official plan comparison](https://render.com/articles/top-heroku-alternatives-agencies) and [pricing](https://render.com/pricing).

| Option | Compatibility and tradeoff | Estimate |
|---|---|---|
| Separate managed Render service | Recommended after hardening. HTTPS/WebSockets, runtime secret files, OIDC; access control is our application's responsibility. No automatic service-level private viewer gate is assumed. | USD 25/month suggested compute budget; USD 7 pilot capacity unproven |
| Streamlit Community Cloud | Technically supports private sharing and OIDC. Suitable for considering a zero-cost pilot only after eligibility and terms clarification. Not recommended for this private rollout yet. | Hosting advertised as free; provider/account limits apply |
| VPS or enterprise Snowflake deployment | More operating work or enterprise setup than this small read-only application currently needs. Neither provisioned nor priced here. | Not estimated |

## Community Cloud compatibility: verified documentation, not a tested deployment

Official documentation describes private viewer settings and one private app. A public source repository defaults to a public app; changing app sharing is separate. OIDC-configured apps also count toward the private-app allowance. Community Cloud's own viewer login does **not** populate the OIDC identity our code requires. Both layers must be tested if used together. Secrets belong in the app's settings, never GitHub.

The current Community Cloud terms include a restriction concerning financial information. Its applicability to these private stock-research/paper records is unresolved; obtain provider clarification before choosing that host for actual results. Do not infer approval from technical OIDC support. The existing public deployment is not altered or assessed as a deployment action here.

Sources checked: [sharing](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app), [st.user](https://docs.streamlit.io/1.65.0/develop/api-reference/user/st.user), [secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management), [Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud), [terms](https://streamlit.io/terms-of-use). Hosting eligibility in the owner's account, private-app capacity and the combined login/callback flow remain untested.

## Code audit of draft PR #1

Reviewed executable: `c682faea4b8dcfb50fa23f367ef5bb02620efca7`. The existing 65 software cases pass. They do not establish real OIDC or hosted private access.

| Area | Evidence and readiness |
|---|---|
| Owner/identity gate | `authorize` requires server private mode/approval/reference, private audience, logged-in verified-email allowlist, read-only credential and reviewed source/protocol pins before a request. Strong existing boundary; OIDC issuer/client configuration must still be verified live. |
| Credential path | Server secrets only, token hidden from Access repr; fixed repository, GET-only methods, bounded reads. Signed log redirects strip Authorization. No workflow dispatch, broker, quote or journal write API exists. |
| Report provenance | Completed dispatcher + successful finalize proof; exact committed file inventories, Git/SHA-256 hashes, A/B session/source/activation/snapshot/coverage bindings. This trusts the approved finalizer, not an independent price certification. |
| Provider/session trust | Exact owner source/protocol pins required. Run-log retention and the 20-completed-run search window can cause UNVERIFIED. There is no durable-proof fallback or tolerance weakening. |
| Private caching | Per-viewer server session, no shared data/disk cache; checks access on render and clears old data on failed refresh/revocation. Freshness is recalculated. An idle page is not continually reauthorized. |
| Authentication gap — blocking | No sign-out control calls `st.logout`. No explicit issued-at/expiry/maximum-session-age enforcement in `authorize`. A logged-in identity cookie alone must not be treated as fresh authentication indefinitely. |
| Rotation gap — blocking test | Cache identity includes source, protocol, approval reference and subject, but not credential generation. Rotating only the GitHub token can reuse prior data for the remaining 120-second cache window. Before private activation, define explicit session invalidation/restart on rotation and test it; a reviewed cache-generation field is an alternative. |
| Release/runtime gap — blocking | Broad Streamlit/dependency ranges remain. Pin the chosen deployment's tested dependency set and verify its real callback, cookie and WebSocket behavior. Disable automatic deploys and secret-bearing PR previews. |

Streamlit documents identity cookies lasting up to 30 days and per-session identity snapshots; logout in one session does not terminate already-open other sessions. Its API also says issued-at/expiry require application enforcement. Therefore the next small code review should add sign-out, an explicit expiry/max-age policy and multitab/revocation tests. Do not interpret 65 green tests as coverage of those absent controls. [Authentication](https://docs.streamlit.io/develop/concepts/connections/authentication), [identity API](https://docs.streamlit.io/1.65.0/develop/api-reference/user/st.user).

The renderer provides Track A details and independent Track B counts/exceptions only. A full Track B positions/closed-trades browser is outside V1 and needs separate scope; it must never be inferred from Track A categories.

## Android-friendly future setup — stop before provisioning today

These are owner-operated instructions for a **later explicitly approved staging rollout**, not permission to deploy now. Chrome's menu → **Desktop site** helps with provider dashboards. Use a password manager; do not put secrets in chat, GitHub issues, screenshots, shared notes or browser query parameters.

1. **Decide first:** approve the hosting budget, intended viewers, OIDC provider, session-expiry/revocation policy and permission to run a private staging acceptance test. Keep public-app secrets untouched. Complete the blocking authentication hardening review before provisioning.
2. **Prepare credentials privately:** plan a dedicated fine-grained GitHub token for `stho-moomoo-test` only, with Contents read, Actions read and metadata. No write/PR/admin/workflow permission. Use a short expiry and record its rotation date securely. The GitHub App repository-access grant used by this chat is not an application-runtime token.
3. **Prepare identity:** plan a Google OIDC Web application client. Authorized origin will be the exact staging HTTPS origin; callback must be `https://YOUR-PRIVATE-HOST/oauth2callback`. Configure consent/test users as needed. The application allowlist is separately enforced and requires a boolean verified-email claim. Use MFA on owner/provider accounts.
4. **Future approved staging only:** select a separate service and the reviewed frontend branch/commit. Turn automatic deploy and PR-preview deploys off; never connect private credentials to an untrusted build. Start with synthetic mode and no engine token. Keep one instance for the first acceptance exercise. Build: `python -m pip install -r requirements.txt`, with the separately reviewed deployment lock applied.
5. **Runtime secret file:** Render's Environment → Secret Files accepts a file named `secrets.toml`; it is available at `/etc/secrets/secrets.toml`. Save placeholder material only while planning; saving configuration can trigger a deployment, so do not do it now. After approval, a runtime start command can place the file where Streamlit expects it:

   ```sh
   umask 077 && mkdir -p .streamlit && cp /etc/secrets/secrets.toml .streamlit/secrets.toml && exec streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT --server.headless=true
   ```

   This is not executed by this document. Do not copy secrets during image builds, disable CORS/XSRF protection, print environment variables or mount an observation archive into the web app. [Render secret-file documentation](https://render.com/docs/configure-environment-variables), [WebSockets](https://render.com/docs/websocket).
6. **Finish OIDC:** once an approved synthetic staging URL exists, register its exact callback/origin in Google. Put client ID, client secret, stable random cookie secret and Google discovery URL in server `[auth]`. Keep `mode=synthetic_preview` until the authentication-only negative tests are complete. Host privacy authentication is not a substitute for this app identity.
7. **Controlled actual-record test later:** only after hardening, consent and negative tests, configure reviewed engine pins/read-only token, the named viewers and approval reference in the separate staging secret store. Then run the [private acceptance plan](PHASE2-PRIVATE-E2E.md). Retain private evidence only in approved private storage. No merge or production scheduler change is needed for the read test.
8. **Android use after acceptance:** open the approved private URL in Chrome, sign in as an allowlisted user, inspect the US session date/status, and test all categories and unavailable warnings. Public V5 remains on its existing URL. Use the new sign-out control once implemented; test a second tab, Incognito, account switching and Wi-Fi/mobile reconnection. Closing a tab is not sign-out.

## Secret structure — placeholders only, intentionally disabled

```toml
[auth]
redirect_uri = "https://YOUR-PRIVATE-HOST/oauth2callback"
cookie_secret = "GENERATE_IN_OWNER_PASSWORD_MANAGER"
client_id = "OWNER_GOOGLE_CLIENT_ID"
client_secret = "OWNER_GOOGLE_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

[v653]
mode = "synthetic_preview"
owner_approved_private_access = false
audience = "authenticated_private"
approval_reference = "REQUIRES_SEPARATE_OWNER_APPROVAL"
allowed_emails = ["approved-viewer@example.test"]
github_token = "SERVER_ONLY_READ_ONLY_ENGINE_TOKEN"
approved_source_sha = "OWNER_REVIEWED_40_HEX_ENGINE_EXECUTABLE"
approved_protocol_sha256 = "OWNER_REVIEWED_64_HEX_PROTOCOL_DIGEST"
```

The final two pins are engine trust anchors, not the frontend commit. Real values stay out of this public document. No credentials were generated, purchased, configured or tested during this audit. The host operator can access runtime secrets/data, so limit collaborators and log retention. Do not log `st.user`, provider tokens, private payloads or signed download URLs.

## Decision

**GO for owner review of this plan; NO-GO for private activation.** Next owner action: choose the separate managed-host budget and named viewers, then authorize a small authentication/session-hardening draft. Deployment and actual private browser testing require a later explicit approval after that review. No service has been created or deployed.
