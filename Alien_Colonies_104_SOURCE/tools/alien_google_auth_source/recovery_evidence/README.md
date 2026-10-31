# Authentication recovery audit

These checks exercise the reconstructed pure Java mailboxes against behavior
recovered directly from the code82 DEX. They do not exercise Android lifecycle,
Credential Manager, Google OAuth configuration, or an installed device build.

Compile `NativeSignInMailbox.java`, `AuthReturnMailbox.java`, and
`RecoveredMailboxTest.java` together with a JDK17 compiler, then run
`com.conradmafer.aliencolonies.auth.RecoveredMailboxTest`. The mailbox classes are
package-private, so the test deliberately uses their package.

Executed on 2026-10-20 against the reconstructed sources: **PASS 77 mailbox
assertions**. The installed Java17 runtime includes `jdk.compiler`, which was
invoked as `java --module jdk.compiler/com.sun.tools.javac.Main`.

The four reconstructed classes were also compared with their recovered Java and
Dalvik instruction listings. No material behavioral difference was identified.
This is a source-level recovery review, not byte-for-byte original-source recovery.

## DEX invariants

- Native attempt results are guarded by an incrementing generation. Starting a
  new login clears a pending result. Cancelling changes generation, clears pending
  tokens, and rejects subsequent stale callbacks. A successful completion makes
  its attempt inactive; taking a result consumes it.
- The Android plugin releases its active cancellation signal only when the
  completed attempt ID matches the signal's attempt. Queued credential-state
  clearing is guarded by the generation created at logout.
- Browser callbacks require an explicitly registered expected flow. Flow and
  ticket must be 16–256 characters from `[A-Za-z0-9_-]`. Only the exact application
  scheme/authority with an empty path and no fragment is accepted. Duplicate or
  unknown query keys, percent encoding, empty values and extra separators fail.
- Accepted callbacks are normalized, deduplicated, and queued FIFO with a maximum
  of four entries. Setting a new expected flow always clears that queue. Native
  tokens and browser tickets are separate mailboxes.
- These are recovered implementation properties, not proof that real device
  sign-in works. The ID token is handed back to the game for server verification.

`annotations.json` records the seven runtime `@UsedByGodot` annotations read
directly from the DEX annotation directory. `manifest_tree.txt` records original
merged AAB manifest attributes; authentication entries are lines 27–33.
