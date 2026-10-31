package com.conradmafer.aliencolonies.auth;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Pattern;

/** Strict, flow-bound browser return queue, reconstructed from the code 82 DEX. */
final class AuthReturnMailbox {
    private static final String PREFIX = "com.conradmafer.aliencolonies://google-auth?";
    private static final Pattern TOKEN = Pattern.compile("[A-Za-z0-9_-]{16,256}");
    private static String expectedFlow = "";
    private static final ArrayDeque<String> pendingReturns = new ArrayDeque<>(4);

    static synchronized void setExpectedFlow(String flow) {
        expectedFlow = flow != null && TOKEN.matcher(flow).matches() ? flow : "";
        pendingReturns.clear();
    }

    static synchronized boolean accept(String url) {
        if (expectedFlow.isEmpty() || url == null || url.length() > 700) return false;
        Map<String, String> values = parse(url);
        if (values == null || !expectedFlow.equals(values.get("flow_id"))) return false;
        String normalized = PREFIX + "flow_id=" + expectedFlow;
        if (values.containsKey("handoff_ticket")) {
            normalized += "&handoff_ticket=" + values.get("handoff_ticket");
        }
        if (!pendingReturns.contains(normalized)) {
            if (pendingReturns.size() >= 4) pendingReturns.removeFirst();
            pendingReturns.addLast(normalized);
        }
        return true;
    }

    static Map<String, String> parse(String url) {
        if (url == null || url.length() > 700 || !url.startsWith(PREFIX)) return null;
        try {
            URI uri = new URI(url);
            if (!"com.conradmafer.aliencolonies".equals(uri.getScheme())
                    || !"google-auth".equals(uri.getRawAuthority())
                    || !"".equals(uri.getRawPath()) || uri.getRawFragment() != null) return null;
            String query = uri.getRawQuery();
            if (query == null) return null;
            Map<String, String> values = new HashMap<>();
            for (String part : query.split("&", -1)) {
                String[] pair = part.split("=", -1);
                if (pair.length != 2
                        || !(pair[0].equals("flow_id") || pair[0].equals("handoff_ticket"))
                        || !TOKEN.matcher(pair[1]).matches()
                        || values.put(pair[0], pair[1]) != null) return null;
            }
            return values.containsKey("flow_id") ? values : null;
        } catch (URISyntaxException ignored) {
            return null;
        }
    }

    static synchronized String takePendingReturn() {
        String result = pendingReturns.pollFirst();
        return result == null ? "" : result;
    }
}
