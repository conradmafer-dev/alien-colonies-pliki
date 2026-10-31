# Native Android Google sign-in

The Android Credential Manager integration uses the same verified Google `sub`
as the existing browser OAuth flow. Existing empires, sessions and subscriptions
are not migrated or reset. Google email and profile claims are discarded; email
matching never links accounts.

## Configuration

The existing `ALIEN_GOOGLE_CLIENT_ID` is the **Web application** OAuth client ID
used as the ID token audience and returned as `server_client_id`. Existing browser
Google sign-in still uses `ALIEN_GOOGLE_CLIENT_SECRET` and
`ALIEN_GOOGLE_ORIGIN`; keep those settings unchanged.

Google Auth Platform must also contain an **Android** OAuth client in the same
Google project, configured for package `com.conradmafer.aliencolonies` and the
SHA-1 fingerprint of the certificate used by **Google Play app signing**. The
upload keystore's fingerprint can differ. Local builds require their own matching
Android OAuth client if signed by a different certificate. The server cannot
infer or provision this Console setting from an ID token. Backend
`native_configured: true` means the endpoints and server verifier are configured;
it does not prove that the Android OAuth client or Play signing certificate is
configured correctly.

No new server environment variables or database schema are required. Do not
raise the server's minimum Android version until the replacement release is
available to users.

## Protocol

All requests use HTTPS JSON POST, `X-PGR-Client-Platform: android` and a valid
`X-PGR-Client-Version` meeting the existing release policy.

1. `/api/auth/google/native/start` with `{"mode":"login","client":"android"}`
   returns `ok`, `flow_id`, `poll_secret`, `nonce`, `server_client_id`, and
   `expires_in` (600 seconds). The nonce is a random 32-byte URL-safe string;
   pass it unchanged to Credential Manager `setNonce`.
2. Credential Manager returns a Google ID token. Send it to
   `/api/auth/google/native/verify` with `flow_id`, `poll_secret`, and `id_token`.
   The response is `{"ok":true,"status":"ready"}` for an existing Google
   identity or `needs_name` for a new identity.
3. `/api/auth/google/complete` with the same flow/poll proof and, if needed, a
   valid empire `name`, returns the existing game session/state response.
   Invalid names are retryable; successful completion consumes the flow.

Native verification uses a single attempt. After a provider error or expired
challenge, begin a fresh flow. Cancellation is local; abandoned flows expire.
Existing `/status` remains usable for a verified native flow but needs no browser
handoff ticket. Web and older Android browser OAuth routes are unchanged. The
existing custom-scheme Android receiver remains necessary for email magic links.

## Verification and limits

Google's maintained `google-auth` library verifies the JWT signature and server
client audience. The server additionally checks issuer, exact one-use nonce,
subject, expiry, issuance time (not before the challenge minus 60 seconds), and
claim types. A signed native `azp` may identify the Android OAuth client instead
of the Web client, as documented for Google's hybrid applications. It must be a
well-formed Google OAuth client ID; browser OAuth retains its stricter presenter
check. The audience must always equal the configured Web/server client ID.

Only verified `sub` is used to find the original empire. A fresh game session
also retains the existing recent-Google-authentication rules for account actions.
If the existing link API is explicitly used, it requires the original account's
reauthentication and rechecks that original session at completion.

Public PEM signing certificates are fetched from Google's fixed certificate
endpoint with an 8-second timeout and cached according to `Cache-Control` and
`Age`, capped at one hour. Tokens are not sent to `tokeninfo`, cached, logged or
saved. There are at most four concurrent native verifications, at most 512 total
pending auth flows, and the existing per-IP authentication rate limit. Provider
I/O holds neither the flow lock nor the simulation lock. Restart discards pending
challenges without altering identities or game saves.

## References and verification

- [Credential Manager implementation](https://developer.android.com/identity/sign-in/credential-manager-siwg-implementation)
- [Google server-side token verification](https://developers.google.com/identity/sign-in/android/backend-auth)
- [Google OIDC claims, including hybrid Android `azp`](https://developers.google.com/identity/openid-connect/openid-connect)

`tests/test_google_native_credentials.py` covers real locally signed RSA JWT
verification through Google's verifier, malformed/forged tokens, audience and
nonce binding, expiry, single use, original empire preservation, version/platform
HTTP guards, lock isolation, concurrency bounds and certificate cache expiry.
Real Google Play installation/account selection still requires a device check
with the correctly configured Android OAuth client.
