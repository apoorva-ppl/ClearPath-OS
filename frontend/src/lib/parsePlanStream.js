// Shared SSE-over-fetch utility for /api/plan/stream.
// Backend sends `data: {json}\n\n` chunks. We accumulate decoded text,
// split on the SSE delimiter, JSON.parse the payload, and pass each
// event to the onEvent callback.

export async function parsePlanStream(response, onEvent) {
    if (!response.ok || !response.body) {
        throw new Error(`plan/stream failed: HTTP ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        let idx;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
            const raw = buf.slice(0, idx).trim();
            buf = buf.slice(idx + 2);
            if (!raw) continue;

            // Each event may contain multiple lines; we only care about `data:`.
            const dataLines = raw
                .split("\n")
                .filter((l) => l.startsWith("data:"))
                .map((l) => l.slice(5).trim());

            if (!dataLines.length) continue;
            const payload = dataLines.join("\n");

            try {
                const evt = JSON.parse(payload);
                onEvent(evt);
            } catch (err) {
                // tolerate malformed events
                console.warn("plan/stream parse failed", err, payload);
            }
        }
    }
}

export async function callPlanStream(apiBase, body, onEvent) {
    const res = await fetch(`${apiBase}/plan/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    await parsePlanStream(res, onEvent);
}
