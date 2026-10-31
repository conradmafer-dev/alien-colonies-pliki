package com.conradmafer.aliencolonies.auth;

/** Behavioral checks for the security boundaries recovered from code82 DEX. */
public final class RecoveredMailboxTest {
    private static int assertions;
    private static final String FLOW_A = "flow_aaaaaaaaaaaaaaaa";
    private static final String FLOW_B = "flow_bbbbbbbbbbbbbbbb";
    private static final String PREFIX = "com.conradmafer.aliencolonies://google-auth?";

    private static void check(boolean condition, String message) {
        assertions++;
        if (!condition) throw new AssertionError(message);
    }

    private static String uri(String flow) { return PREFIX + "flow_id=" + flow; }

    private static void nativeAttemptIsolation() {
        NativeSignInMailbox mailbox = new NativeSignInMailbox();
        check(mailbox.take() == null, "empty result must be absent");
        long first = mailbox.begin(FLOW_A);
        long second = mailbox.begin(FLOW_B);
        check(!mailbox.isActive(first) && mailbox.isActive(second), "new account attempt invalidates old attempt");
        mailbox.complete(first, "success", "stale-account-token", null);
        check(mailbox.take() == null, "late success from old attempt must not escape");
        mailbox.complete(second, "success", "current-account-token", null);
        NativeSignInMailbox.Result result = mailbox.take();
        check(result != null && FLOW_B.equals(result.requestId), "result must remain bound to requesting flow");
        check("current-account-token".equals(result.token) && "success".equals(result.status), "current result must survive");
        check(mailbox.take() == null, "result must only be delivered once");
        mailbox.complete(second, "error", null, "provider_error");
        check(mailbox.take() == null, "duplicate callback must not replace consumed success");

        long pending = mailbox.begin(FLOW_A);
        mailbox.complete(pending, "success", "must-be-cleared", null);
        long cancellation = mailbox.cancel();
        check(mailbox.isGeneration(cancellation) && !mailbox.isActive(pending), "cancel changes generation and deactivates attempt");
        check(mailbox.take() == null, "logout must erase an unconsumed token");
        mailbox.complete(pending, "success", "late-after-logout", null);
        check(mailbox.take() == null, "logout must reject late result");
        mailbox.begin(FLOW_B);
        check(!mailbox.isGeneration(cancellation), "new login makes queued old clear-state work obsolete");

        long old = mailbox.begin(FLOW_A);
        mailbox.complete(old, "success", "pending-old-account", null);
        mailbox.begin(FLOW_B);
        check(mailbox.take() == null, "starting new attempt discards pending result from previous account");
    }

    private static void browserReturnValidation() {
        AuthReturnMailbox.setExpectedFlow(null);
        check(!AuthReturnMailbox.accept(uri(FLOW_A)), "unsolicited callback without expected flow rejected");
        AuthReturnMailbox.setExpectedFlow(FLOW_A);
        check(!AuthReturnMailbox.accept(uri(FLOW_B)), "callback for another flow rejected");
        check(AuthReturnMailbox.takePendingReturn().isEmpty(), "invalid callback cannot queue a return");
        String ticket = "ticket_abcdefghijklmnop";
        String reversed = PREFIX + "handoff_ticket=" + ticket + "&flow_id=" + FLOW_A;
        check(AuthReturnMailbox.accept(reversed), "permitted fields in either order accepted");
        check(AuthReturnMailbox.accept(reversed), "duplicate recognized as accepted");
        check((uri(FLOW_A) + "&handoff_ticket=" + ticket).equals(AuthReturnMailbox.takePendingReturn()), "output normalized into fixed field order");
        check(AuthReturnMailbox.takePendingReturn().isEmpty(), "duplicate return queued only once");

        String[] invalid = {
            null,
            "", uri(FLOW_A) + "#fragment", uri(FLOW_A) + "&unknown=" + FLOW_A,
            uri(FLOW_A) + "&flow_id=" + FLOW_A,
            uri(FLOW_A) + "&handoff_ticket=" + ticket + "&handoff_ticket=" + ticket,
            uri(FLOW_A) + "&", uri(FLOW_A) + "=extra", PREFIX + "flow_id=short",
            PREFIX + "flow_id=" + "a".repeat(257), PREFIX + "flow_id=" + FLOW_A + "%41",
            PREFIX + "flow_id=" + FLOW_A + "+", PREFIX + "flow_id=" + FLOW_A + "%00",
            PREFIX + "handoff_ticket=" + ticket, PREFIX + "flow_id=" + FLOW_A + "&handoff_ticket=",
            "COM.CONRADMAFER.ALIENCOLONIES://google-auth?flow_id=" + FLOW_A,
            "com.conradmafer.aliencolonies://GOOGLE-AUTH?flow_id=" + FLOW_A,
            "com.conradmafer.aliencolonies://google-auth/?flow_id=" + FLOW_A,
            "com.conradmafer.aliencolonies://attacker@google-auth?flow_id=" + FLOW_A,
            "com.conradmafer.aliencolonies://google-auth:443?flow_id=" + FLOW_A,
            "https://google-auth?flow_id=" + FLOW_A,
            uri(FLOW_A) + "&handoff_ticket=" + "b".repeat(701)
        };
        for (String candidate : invalid) {
            check(!AuthReturnMailbox.accept(candidate), "malformed or ambiguous return rejected: " + candidate);
            check(AuthReturnMailbox.takePendingReturn().isEmpty(), "rejected return must not enqueue anything");
        }

        check(AuthReturnMailbox.accept(uri(FLOW_A)), "flow-only callback supported");
        AuthReturnMailbox.setExpectedFlow(FLOW_B);
        check(AuthReturnMailbox.takePendingReturn().isEmpty(), "flow change clears previous pending return");
        check(!AuthReturnMailbox.accept(uri(FLOW_A)), "previous flow no longer valid");
        AuthReturnMailbox.setExpectedFlow("invalid");
        check(!AuthReturnMailbox.accept(uri(FLOW_B)), "invalid expected flow disables callback acceptance");

        AuthReturnMailbox.setExpectedFlow(FLOW_A);
        for (int i = 0; i < 5; i++) {
            check(AuthReturnMailbox.accept(uri(FLOW_A) + "&handoff_ticket=ticket_aaaaaaaaaaaa" + i), "valid distinct return accepted");
        }
        check((uri(FLOW_A) + "&handoff_ticket=ticket_aaaaaaaaaaaa1").equals(AuthReturnMailbox.takePendingReturn()), "bounded queue evicts oldest of five returns");
        for (int i = 2; i < 5; i++) {
            check((uri(FLOW_A) + "&handoff_ticket=ticket_aaaaaaaaaaaa" + i).equals(AuthReturnMailbox.takePendingReturn()), "remaining returns retain FIFO order");
        }
        check(AuthReturnMailbox.takePendingReturn().isEmpty(), "callback queue contains at most four results");
    }

    public static void main(String[] args) {
        nativeAttemptIsolation();
        browserReturnValidation();
        System.out.println("PASS " + assertions + " mailbox assertions");
    }
}
