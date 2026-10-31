# Passwordless email sign-in

This is an additional verified sign-in method. Existing Google subjects/accounts
are untouched. A matching email or empire name never merges or claims an account.
New email accounts start with the same server rules as other new accounts.

## Activation

Configure the backend only after verifying a sending domain in Resend:

- `EMAIL_PROVIDER_API_KEY`: a server-only Resend key with Sending access, scoped to the verified sending domain.
- `EMAIL_FROM`: a verified sender, for example `Alien Colonies <login@your-domain.example>`.
- `SITE_ORIGIN`: canonical HTTPS website origin, normally `https://aliencolonies.com`.

Missing/invalid configuration leaves `/api/auth/email/config` disabled. No mail is
sent during startup, deployment, tests or configuration discovery. Disable open
and click tracking for authentication messages at the provider. Do not log request query
strings or email bodies in reverse-proxy/provider diagnostics.

## Client contract

All API responses use `{ok:false,error:message}` on failure. Tokens/proofs must not
appear in logs, analytics, localStorage, game snapshots or user-visible errors.

| Route | Input | Successful result |
|---|---|---|
| `GET /api/auth/email/config` | None | `ok`, `configured` |
| `POST /api/auth/email/start` | `email`, `client: web/android`; Android also `handoff: app_link_v1` | `flow_id`, `poll_secret`, `expires_in:900`, `resend_after:60`, `poll_after:3`, generic `message` |
| `POST /api/auth/email/status` | `flow_id`, `poll_secret`; Android also `handoff_ticket` | `status: pending/ready/needs_name` |
| `POST /api/auth/email/complete` | Same proof; `name` only for a verified new account | Normal `token`, `state`, `message` |

Resending starts a new flow after 60 seconds. Clients replace their active flow
and ignore stale responses. Pending flows expire after 15 minutes; a server
restart invalidates them safely and requires requesting another link. A used
flow cannot issue a second game session.

Web `/start` sets `__Host-alien_email_flow` (Secure, HttpOnly, SameSite=Lax).
The link must open in that browser. `/status` and `/complete` require both its
cookie and originating-tab poll proof. The proof remains only in the original
tab. Email confirmation can open in a new tab; it tells the user to return to the
original tab, which polls and completes. A new tab receives no game credentials.

Android requires the mailbox handoff ticket on **both status and completion**,
plus its independently held poll secret. Confirmation returns an HTML button for
`com.conradmafer.aliencolonies://google-auth?flow_id=…&handoff_ticket=…`.
The existing native bridge accepts only the app's expected flow. Google and email
flows must be mutually exclusive before changing bridge ownership. Open the mail
link on the requesting phone. An invalid early ticket returns `pending` so the
client can process a later legitimate callback; completion never accepts it.

## Confirmation and account safety

The emailed `GET /api/auth/email/open?flow=…&token=…` displays a form. It does not
consume the token, create accounts, or authorize sessions. Explicit same-origin
`POST /api/auth/email/confirm` validates a bound cookie and CSRF proof, consumes the
mail token once, and marks that flow verified. No third-party resources load on
confirmation pages; responses use `no-store`, `strict-origin`, and restrictive CSP.
The referrer policy preserves the confirmation form's exact `Origin` for strict
CSRF checks while disclosing at most the public origin, never the link path or
token query. Opaque (`null`) and foreign origins remain rejected.

Addresses are normalized case-insensitively; plus/dot aliases are not merged.
Only a prefixed address hash is persisted in `email_accounts`, with one unique
identity per empire. The actual address exists in the pending in-memory flow and
is sent to the email provider, then cleared after completion/expiration. A new
account is created only after verification and a valid user-chosen empire name.

`state.account.email_linked` identifies an email account; `password_login_enabled`
is false initially. A new email login issues a fresh proof valid for five minutes
for account deletion, password changes and logout-other-devices. Reauthentication
UI must bind to the current player and reject a different account or new-name
result. Deleting the account cascades through email identities and email session
proofs. Google account behavior is unchanged; no automatic linking is performed.

## Abuse limits

Per address: one mail/minute and five/hour. Per requesting IP: 12 starts/15 minutes.
Server-wide: 30/minute and 300/hour, at most four concurrent deliveries, 1024 flows
and 4096 rate keys. Address-limited attempts receive the same generic pending
response, with no account-existence lookup. Regular API and confirmation routes
also use the existing per-IP request limiter. Provider I/O runs outside world and
flow locks and uses a fixed HTTPS endpoint with an eight-second timeout.

## Verification

`python3 -m unittest discover -s tests -p 'test_email_signin.py'`

Tests use synthetic local worlds and mocked senders. A configured sender still
needs an explicitly authorized delivery test and native-device return test before
claiming that real email delivery is working.
