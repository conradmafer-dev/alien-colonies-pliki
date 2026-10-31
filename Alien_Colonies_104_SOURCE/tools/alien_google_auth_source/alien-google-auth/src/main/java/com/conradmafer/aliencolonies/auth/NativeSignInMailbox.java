package com.conradmafer.aliencolonies.auth;

/** Reconstructed from the code 82 DEX. Keeps late callbacks out of newer flows. */
final class NativeSignInMailbox {
    private boolean active;
    private long generation;
    private Result pending;
    private String requestId = "";

    synchronized long begin(String requestId) {
        generation++;
        this.requestId = requestId;
        active = true;
        pending = null;
        return generation;
    }

    synchronized long cancel() {
        generation++;
        active = false;
        requestId = "";
        pending = null;
        return generation;
    }

    synchronized void complete(long attempt, String status, String token, String error) {
        if (!isActive(attempt)) return;
        pending = new Result(requestId, status, token, error);
        active = false;
        requestId = "";
    }

    synchronized boolean isActive(long attempt) {
        return active && attempt == generation;
    }

    synchronized boolean isGeneration(long attempt) {
        return attempt == generation;
    }

    synchronized Result take() {
        Result result = pending;
        pending = null;
        return result;
    }

    static final class Result {
        final String requestId;
        final String status;
        final String token;
        final String error;

        Result(String requestId, String status, String token, String error) {
            this.requestId = requestId;
            this.status = status;
            this.token = token;
            this.error = error;
        }
    }
}
