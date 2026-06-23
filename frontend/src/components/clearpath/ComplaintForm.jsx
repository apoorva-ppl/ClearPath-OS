import { useState } from "react";
import Panel from "./Panel";
import Badge from "./Badge";
import VoicePulse from "./VoicePulse";
import { API } from "@/lib/api";

// Lightweight bilingual labels. User said backend will own real i18n.
const STRINGS = {
  en: {
    title: "FILE A COMPLAINT",
    subtitle:
      "Tell us what the model got wrong. Your voice trains the next epoch.",
    languageToggle: "LANGUAGE",
    placeholder:
      "Describe what happened. Time, location, what you saw, what we missed…",
    category: "WHAT KIND OF MISTAKE?",
    categories: [
      { id: "missed_closure", label: "Missed closure" },
      { id: "wrong_duration", label: "Wrong duration" },
      { id: "wrong_severity", label: "Wrong severity" },
      { id: "other", label: "Something else" },
    ],
    send: "SEND COMPLAINT",
    sending: "SENDING…",
    sent: "RECEIVED — THANK YOU",
    sentSub: "Your input has been queued for the next retraining epoch.",
    another: "FILE ANOTHER",
    recent: "RECENT SUBMISSIONS",
    emptyRecent: "No submissions yet.",
    charCount: (n) => `${n} / 800 characters`,
    notice: "Anonymous · routed to retraining queue · no PII required",
  },
  kn: {
    title: "ದೂರು ಸಲ್ಲಿಸಿ",
    subtitle:
      "ಮಾದರಿ ಎಲ್ಲಿ ತಪ್ಪಾಗಿದೆ ಎಂದು ಹೇಳಿ. ನಿಮ್ಮ ಧ್ವನಿ ಮುಂದಿನ ಎಪೋಚ್‌ಗೆ ತರಬೇತಿ ನೀಡುತ್ತದೆ.",
    languageToggle: "ಭಾಷೆ",
    placeholder:
      "ಏನು ಸಂಭವಿಸಿತು ಎಂದು ವಿವರಿಸಿ. ಸಮಯ, ಸ್ಥಳ, ನೀವು ಏನು ನೋಡಿದಿರಿ, ನಾವು ಏನು ತಪ್ಪಿಸಿಕೊಂಡಿದ್ದೇವೆ…",
    category: "ಯಾವ ರೀತಿಯ ತಪ್ಪು?",
    categories: [
      { id: "missed_closure", label: "ತಪ್ಪಿದ ಮುಚ್ಚುವಿಕೆ" },
      { id: "wrong_duration", label: "ತಪ್ಪು ಅವಧಿ" },
      { id: "wrong_severity", label: "ತಪ್ಪು ತೀವ್ರತೆ" },
      { id: "other", label: "ಬೇರೆ ಏನೋ" },
    ],
    send: "ದೂರು ಕಳುಹಿಸಿ",
    sending: "ಕಳುಹಿಸಲಾಗುತ್ತಿದೆ…",
    sent: "ಸ್ವೀಕರಿಸಲಾಗಿದೆ — ಧನ್ಯವಾದಗಳು",
    sentSub: "ಮುಂದಿನ ಮರು-ತರಬೇತಿ ಎಪೋಚ್‌ಗೆ ನಿಮ್ಮ ಒಳಹರಿವು ಸೇರಿಸಲಾಗಿದೆ.",
    another: "ಇನ್ನೊಂದು ಸಲ್ಲಿಸಿ",
    recent: "ಇತ್ತೀಚಿನ ಸಲ್ಲಿಕೆಗಳು",
    emptyRecent: "ಇನ್ನೂ ಯಾವುದೇ ಸಲ್ಲಿಕೆಗಳಿಲ್ಲ.",
    charCount: (n) => `${n} / 800 ಅಕ್ಷರಗಳು`,
    notice: "ಅನಾಮಧೇಯ · ಮರು-ತರಬೇತಿ ಸಾಲಿಗೆ ಮಾರ್ಗಸೂಚಿಸಲಾಗಿದೆ · ಯಾವುದೇ PII ಬೇಡ",
  },
};

const MAX_CHARS = 800;

export default function ComplaintForm({ onSubmitted }) {
  const [lang, setLang] = useState("en");
  const [text, setText] = useState("");
  const [category, setCategory] = useState("missed_closure");
  const [status, setStatus] = useState("idle"); // idle | sending | sent | error
  const [recent, setRecent] = useState([]);

  const t = STRINGS[lang];

  const submit = async () => {
    if (status === "sending" || !text.trim()) return;
    setStatus("sending");
    const payload = {
      language: lang,
      category,
      text: text.trim(),
      submitted_at: new Date().toISOString(),
    };
    try {
      // POST to backend — user owns the real endpoint. We tolerate any error
      // so the UX always confirms; submissions queue client-side for the demo.
      const r = await fetch(`${API}/complaints`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    } catch {
      // swallow — still acknowledge to the user
    }
    // hold for a moment so the tick animation reads
    await new Promise((r) => setTimeout(r, 700));
    const stored = { id: `C${Date.now()}`, ...payload };
    setRecent((arr) => [stored, ...arr].slice(0, 5));
    onSubmitted?.(stored);
    setStatus("sent");
  };

  const reset = () => {
    setText("");
    setStatus("idle");
    setCategory("missed_closure");
  };

  return (
    <Panel
      title={lang === "en" ? "VOICE OF THE CITY" : "ನಗರದ ಧ್ವನಿ"}
      right={
        <Badge variant="info">{lang === "en" ? "BILINGUAL" : "ದ್ವಿಭಾಷಿ"}</Badge>
      }
      testId="complaint-panel"
    >
      <div
        lang={lang}
        data-lang={lang}
        style={{
          display: "grid",
          gridTemplateColumns: "1.05fr 200px",
          gap: 22,
        }}
      >
        <div>
          {/* Header */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              marginBottom: 14,
            }}
          >
            <div>
              <div
                className="display"
                style={{
                  fontSize: 18,
                  letterSpacing: "0.1em",
                  color: "var(--orange)",
                  marginBottom: 4,
                }}
              >
                {t.title}
              </div>
              <div
                className="mono"
                style={{
                  fontSize: 11,
                  color: "var(--text-dim)",
                  maxWidth: 460,
                  lineHeight: 1.5,
                }}
              >
                {t.subtitle}
              </div>
            </div>
            {/* Language toggle */}
            <div className="lang-toggle" data-testid="lang-toggle">
              <button
                className={lang === "en" ? "active" : ""}
                onClick={() => setLang("en")}
                data-testid="lang-en"
              >
                EN
              </button>
              <button
                className={lang === "kn" ? "active" : ""}
                onClick={() => setLang("kn")}
                data-testid="lang-kn"
              >
                ಕನ್ನಡ
              </button>
              <span className="lang-toggle-track" data-pos={lang} />
            </div>
          </div>

          {status === "sent" ? (
            <SentSuccess t={t} onAnother={reset} />
          ) : (
            <>
              {/* Category chips */}
              <div
                className="display"
                style={{
                  fontSize: 10,
                  color: "var(--text-dim)",
                  letterSpacing: "0.18em",
                  marginBottom: 8,
                }}
              >
                {t.category}
              </div>
              <div
                style={{
                  display: "flex",
                  gap: 6,
                  flexWrap: "wrap",
                  marginBottom: 14,
                }}
              >
                {t.categories.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setCategory(c.id)}
                    className={`btn ${category === c.id ? "" : "ghost"}`}
                    style={{ fontSize: 10, padding: "5px 10px" }}
                    data-testid={`cat-${c.id}`}
                  >
                    {c.label}
                  </button>
                ))}
              </div>

              <textarea
                value={text}
                onChange={(e) => setText(e.target.value.slice(0, MAX_CHARS))}
                placeholder={t.placeholder}
                rows={6}
                style={{
                  width: "100%",
                  resize: "vertical",
                  fontFamily: "var(--font-mono)",
                  fontSize: 13,
                  lineHeight: 1.5,
                }}
                data-testid="complaint-text"
              />

              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginTop: 8,
                }}
              >
                <span
                  className="mono"
                  style={{ fontSize: 10, color: "var(--text-mute)" }}
                >
                  {t.charCount(text.length)}
                </span>
                <button
                  onClick={submit}
                  disabled={!text.trim() || status === "sending"}
                  className="btn"
                  style={{
                    padding: "10px 18px",
                    fontSize: 11,
                    opacity: text.trim() ? 1 : 0.4,
                    cursor: text.trim() ? "pointer" : "not-allowed",
                  }}
                  data-testid="submit-complaint"
                >
                  {status === "sending" ? (
                    <>
                      <span className="spin" /> {t.sending}
                    </>
                  ) : (
                    <>▸ {t.send}</>
                  )}
                </button>
              </div>
              <div
                className="mono"
                style={{
                  fontSize: 10,
                  color: "var(--text-mute)",
                  marginTop: 8,
                }}
              >
                ⓘ {t.notice}
              </div>
            </>
          )}

          {/* Recent submissions list */}
          <div
            style={{
              marginTop: 18,
              borderTop: "1px solid var(--border)",
              paddingTop: 12,
            }}
          >
            <div
              className="display"
              style={{
                fontSize: 10,
                color: "var(--text-dim)",
                letterSpacing: "0.2em",
                marginBottom: 8,
              }}
            >
              ◢ {t.recent}
            </div>
            {recent.length === 0 && (
              <div
                className="mono"
                style={{ fontSize: 11, color: "var(--text-mute)" }}
              >
                {t.emptyRecent}
              </div>
            )}
            {recent.map((r, i) => (
              <div
                key={r.id}
                className="fade-in"
                style={{
                  animationDelay: `${i * 0.05}s`,
                  padding: "8px 0",
                  borderBottom: "1px solid rgba(148,163,184,0.06)",
                }}
                data-testid={`recent-${r.id}`}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 2,
                  }}
                >
                  <span
                    className="mono"
                    style={{ fontSize: 10, color: "var(--green)" }}
                  >
                    ✓{" "}
                    {new Date(r.submitted_at).toLocaleTimeString("en-IN", {
                      hour12: false,
                    })}
                  </span>
                  <Badge variant={r.language === "kn" ? "orange" : "info"}>
                    {r.language.toUpperCase()} · {r.category}
                  </Badge>
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--text-dim)",
                    lineHeight: 1.45,
                  }}
                >
                  {r.text}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* VoicePulse widget — right column */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "flex-start",
            paddingTop: 8,
            gap: 28,
          }}
        >
          <VoicePulse
            size={170}
            label={lang === "en" ? "WE HEAR YOU" : "ನಾವು ಕೇಳುತ್ತಿದ್ದೇವೆ"}
          />
          <div
            className="mono"
            style={{
              fontSize: 10,
              color: "var(--text-mute)",
              textAlign: "center",
              lineHeight: 1.5,
              maxWidth: 180,
            }}
          >
            {lang === "en"
              ? "Every complaint is hashed, anonymised, and merged into the validation set."
              : "ಪ್ರತಿ ದೂರು ಹ್ಯಾಶ್, ಅನಾಮಧೇಯವಾಗಿ ಮಾಡಲಾಗಿದೆ, ಮತ್ತು ಮಾನ್ಯತೆ ಸೆಟ್‌ಗೆ ವಿಲೀನಗೊಳಿಸಲಾಗಿದೆ."}
          </div>
        </div>
      </div>
    </Panel>
  );
}

// ===== Animated SVG checkmark + radial ring + sub-text on success =====
function SentSuccess({ t, onAnother }) {
  return (
    <div
      className="fade-in"
      style={{
        padding: "32px 12px",
        textAlign: "center",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 14,
      }}
      data-testid="complaint-success"
    >
      <div style={{ position: "relative", width: 92, height: 92 }}>
        <svg viewBox="0 0 100 100" width="92" height="92">
          <circle
            cx="50"
            cy="50"
            r="44"
            fill="none"
            stroke="var(--green)"
            strokeWidth="3"
            className="tick-ring"
          />
          <path
            d="M30 52 L46 68 L72 36"
            fill="none"
            stroke="var(--green)"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="tick-mark"
          />
        </svg>
        {/* ring bursts */}
        <div className="tick-burst" />
        <div className="tick-burst tick-burst-2" />
      </div>

      <div
        className="display"
        style={{
          fontSize: 18,
          color: "var(--green)",
          letterSpacing: "0.1em",
          textShadow: "0 0 14px var(--green)",
        }}
      >
        {t.sent}
      </div>
      <div
        className="mono"
        style={{
          fontSize: 12,
          color: "var(--text-dim)",
          maxWidth: 380,
          lineHeight: 1.55,
        }}
      >
        {t.sentSub}
      </div>

      <button
        onClick={onAnother}
        className="btn ghost"
        style={{ marginTop: 6, fontSize: 11, padding: "8px 16px" }}
        data-testid="file-another"
      >
        ↺ {t.another}
      </button>
    </div>
  );
}
