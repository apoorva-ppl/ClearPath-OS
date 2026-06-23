import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import LiveDot from "@/components/clearpath/LiveDot";
import SplineLogo from "@/components/clearpath/SplineLogo";
import MeshBackground from "@/components/clearpath/MeshBackground";

export default function Landing() {
  const [phase, setPhase] = useState("intro"); // intro -> dissolve -> landing
  const [muted, setMuted] = useState(true);
  const [entered, setEntered] = useState(false); // gates sound — browsers block autoplay+sound until a real click happens
  const videoRef = useRef(null);

  useEffect(() => {
    if (!entered) return; // don't start the intro timers until the user has clicked in
    // Intro plays for ~3.2s before dissolving (was 5.2s — felt slow on repeat visits)
    const t1 = setTimeout(
      () => setPhase((p) => (p === "intro" ? "dissolve" : p)),
      3200,
    );
    // Dissolve ramp shortened from 1.7s to 0.9s total so the handoff feels snappier
    const t2 = setTimeout(
      () =>
        setPhase((p) => (p === "intro" || p === "dissolve" ? "landing" : p)),
      4100,
    );
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [entered]);

  const handleEnter = () => {
    setEntered(true);
    setMuted(false);
    if (videoRef.current) {
      videoRef.current.muted = false;
      videoRef.current.currentTime = 0;
      videoRef.current.play().catch(() => {});
    }
  };

  const onVideoEnd = () => setPhase((p) => (p === "intro" ? "dissolve" : p));

  const toggleMute = () => {
    setMuted((m) => {
      const next = !m;
      if (videoRef.current) videoRef.current.muted = next;
      return next;
    });
  };

  const introVisible = phase === "intro" || phase === "dissolve";

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--bg)",
        position: "relative",
        overflow: "hidden",
      }}
      data-testid="landing-page"
    >
      {/* Click-to-enter gate — required so the browser allows sound on the intro video.
                Without a real user gesture here, autoplay-with-sound is always blocked. */}
      {!entered && (
        <div
          onClick={handleEnter}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 200,
            background: "#000",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
          data-testid="enter-gate"
        >
          <div
            className="display"
            style={{
              color: "#fff",
              fontSize: 14,
              letterSpacing: "0.3em",
              border: "1px solid rgba(255,255,255,0.4)",
              padding: "16px 32px",
              borderRadius: 8,
            }}
          >
            ⊕ ENTER WITH SOUND
          </div>
        </div>
      )}

      {/* Intro video layer — raw, no filters, plain opacity fade only.
                Visual softness here comes from the source file's native resolution,
                not from CSS — swap /assets/intro.mp4 for a higher-res export to sharpen it. */}
      <div
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 100,
          background: "#000",
          opacity: phase === "landing" ? 0 : 1,
          visibility:
            introVisible || phase === "landing" ? "visible" : "hidden",
          pointerEvents: introVisible ? "auto" : "none",
          transition:
            "opacity 0.9s cubic-bezier(0.16, 1, 0.3, 1), visibility 0s linear 0.9s",
        }}
        data-testid="intro-video-layer"
      >
        <video
          ref={videoRef}
          src="/assets/intro_final.mp4"
          autoPlay
          muted={muted}
          playsInline
          preload="auto"
          onEnded={onVideoEnd}
          onError={onVideoEnd}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            maxWidth: "min(1920px, 100vw)",
            maxHeight: "100vh",
            height: "auto",
            objectFit: "cover",
            imageRendering: "auto",
            filter: "contrast(1.05) saturate(1.05)",
            animation: "introVideoIn 1.4s cubic-bezier(0.16, 1, 0.3, 1)",
            boxShadow: "0 0 120px 40px rgba(0,0,0,0.9)",
          }}
        />

        {/* Watermark cover — 2x size, fully opaque, repositionable if it still doesn't
                    line up with the source video's logo placement */}
        <div
          style={{
            position: "absolute",
            top: 36,
            right: 36,
            zIndex: 5,
            display: "flex",
            alignItems: "center",
            gap: 16,
            padding: "12px 24px",
            borderRadius: 16,
            background: "rgba(3,7,18,1)",
            backdropFilter: "blur(12px)",
          }}
          data-testid="intro-watermark-cover"
        >
          <span
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background:
                "conic-gradient(from 220deg, #f97316, #fbbf24, #06b6d4, #f97316)",
            }}
          />
          <span
            className="display"
            style={{
              color: "#fff",
              letterSpacing: "0.18em",
              fontWeight: 700,
              fontSize: 22,
            }}
          >
            CLEAR<span style={{ color: "#f97316" }}>PATH</span> OS
          </span>
        </div>

        <div
          style={{
            position: "absolute",
            bottom: 40,
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            gap: 10,
            zIndex: 3,
            opacity: phase === "intro" ? 1 : 0,
            transition: "opacity 0.4s ease",
          }}
        >
          <button
            onClick={toggleMute}
            className="btn ghost"
            data-testid="toggle-audio-btn"
          >
            {muted ? "🔇 UNMUTE" : "🔊 MUTE"}
          </button>
          <button
            onClick={() => setPhase("dissolve")}
            className="btn ghost"
            data-testid="skip-intro-btn"
          >
            SKIP →
          </button>
        </div>
      </div>

      {/* Landing content — starts fading in during the dissolve so the intro melts into it */}
      <LandingContent visible={phase === "dissolve" || phase === "landing"} />
    </div>
  );
}

/* ===== Kinetic word that reveals char-by-char ===== */
function Kinetic({ text, delay = 0, color, gradient }) {
  return (
    <span style={{ display: "inline-block" }}>
      {text.split("").map((ch, i) => (
        <span
          key={i}
          className={`kinetic-char ${gradient ? "gradient" : ""}`}
          style={{
            animationDelay: `${delay + i * 0.04}s`,
            color: gradient ? undefined : color,
          }}
        >
          {ch === " " ? "\u00A0" : ch}
        </span>
      ))}
    </span>
  );
}

function useInView(ref, rootMargin = "-80px") {
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    if (!ref.current) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setSeen(true);
          obs.disconnect();
        }
      },
      { rootMargin },
    );
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, [ref, rootMargin]);
  return seen;
}

function Reveal({ children, delay = 0 }) {
  const ref = useRef(null);
  const seen = useInView(ref);
  return (
    <div
      ref={ref}
      className={`reveal ${seen ? "in" : ""}`}
      style={{ transitionDelay: `${delay}s` }}
    >
      {children}
    </div>
  );
}

function Magnet({ children, strength = 16, style, ...rest }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onMove = (e) => {
      const r = el.getBoundingClientRect();
      const dx = (e.clientX - (r.left + r.width / 2)) / r.width;
      const dy = (e.clientY - (r.top + r.height / 2)) / r.height;
      el.style.transform = `translate(${dx * strength}px, ${dy * strength}px)`;
    };
    const onLeave = () => (el.style.transform = "translate(0,0)");
    el.addEventListener("mousemove", onMove);
    el.addEventListener("mouseleave", onLeave);
    return () => {
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
    };
  }, [strength]);
  return (
    <span ref={ref} className="magnet" style={style} {...rest}>
      {children}
    </span>
  );
}

function LandingContent({ visible }) {
  const heroRef = useRef(null);
  // hero parallax tilt
  useEffect(() => {
    const el = heroRef.current;
    if (!el) return;
    const onMove = (e) => {
      const r = el.getBoundingClientRect();
      const dx = (e.clientX - (r.left + r.width / 2)) / r.width;
      const dy = (e.clientY - (r.top + r.height / 2)) / r.height;
      el.style.setProperty("--mx", `${dx * 30}px`);
      el.style.setProperty("--my", `${dy * 30}px`);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  return (
    <div
      style={{
        opacity: visible ? 1 : 0,
        transition: "opacity 0.8s ease 0.2s",
        minHeight: "100vh",
        position: "relative",
      }}
    >
      <MeshBackground height="120vh" />

      {/* NAV */}
      <header
        style={{
          padding: "18px 32px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          backdropFilter: "blur(24px)",
          background: "rgba(3,7,18,0.55)",
          borderBottom: "1px solid var(--border)",
          position: "sticky",
          top: 0,
          zIndex: 20,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background:
                "conic-gradient(from 220deg, #f97316, #fbbf24, #06b6d4, #f97316)",
              boxShadow: "0 0 16px rgba(249,115,22,0.6)",
              position: "relative",
            }}
          >
            <span
              style={{
                position: "absolute",
                inset: 4,
                background: "var(--bg)",
                borderRadius: 4,
              }}
            />
          </span>
          <span
            className="display"
            style={{
              color: "var(--text)",
              letterSpacing: "0.22em",
              fontWeight: 700,
              fontSize: 14,
            }}
          >
            CLEAR<span style={{ color: "var(--orange)" }}>PATH</span> OS
          </span>
        </div>
        <nav style={{ display: "flex", gap: 18, alignItems: "center" }}>
          {[
            ["GOD MODE", "/god-mode"],
            ["SENTINEL", "/sentinel"],
            ["INTELLIGENCE", "/intelligence"],
            ["DEBRIEF", "/debrief"],
            ["VULNERABLE", "/vulnerable"],
          ].map(([t, to]) => (
            <Link
              key={to}
              to={to}
              className="display"
              style={{
                fontSize: 11,
                color: "var(--text-dim)",
                letterSpacing: "0.16em",
                textDecoration: "none",
              }}
              data-testid={`nav-cta-${to.slice(1)}`}
            >
              {t}
            </Link>
          ))}
          <span
            className="mono"
            style={{
              color: "var(--text-mute)",
              fontSize: 11,
              display: "flex",
              alignItems: "center",
              gap: 6,
              paddingLeft: 14,
              borderLeft: "1px solid var(--border)",
            }}
          >
            <LiveDot variant="green" /> BENGALURU
          </span>
        </nav>
      </header>

      {/* HERO */}
      <section
        ref={heroRef}
        style={{
          position: "relative",
          minHeight: "92vh",
          padding: "72px 32px 40px",
          maxWidth: 1380,
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: "1.25fr 1fr",
          gap: 60,
          alignItems: "center",
          zIndex: 2,
        }}
      >
        <div>
          <Reveal>
            <div
              className="mono"
              style={{
                color: "var(--cyan)",
                fontSize: 12,
                letterSpacing: "0.3em",
                marginBottom: 24,
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <LiveDot variant="green" />
              BENGALURU TRAFFIC POLICE · COMMAND PLATFORM
            </div>
          </Reveal>

          <h1
            className="display"
            style={{
              fontSize: "clamp(56px, 8vw, 112px)",
              lineHeight: 0.95,
              margin: 0,
              fontWeight: 700,
              letterSpacing: "-0.005em",
            }}
          >
            <Kinetic text="INCIDENT." delay={0.05} />
            <br />
            <Kinetic text="ROUTE." delay={0.4} gradient />
            <br />
            <Kinetic text="RESPOND." delay={0.7} />
          </h1>

          <Reveal delay={0.3}>
            <p
              style={{
                color: "var(--text-dim)",
                fontSize: 17,
                maxWidth: 580,
                marginTop: 32,
                lineHeight: 1.6,
              }}
            >
              A predictive command-center for road closures, dispatch, and
              citizen-sourced verification. Multi-agent triage, spatial
              diversion, and logistics optimization —{" "}
              <em style={{ color: "var(--orange)", fontStyle: "normal" }}>
                streamed
              </em>{" "}
              in real time.
            </p>
          </Reveal>

          <Reveal delay={0.45}>
            <div
              style={{
                display: "flex",
                gap: 14,
                marginTop: 36,
                flexWrap: "wrap",
              }}
            >
              <Magnet>
                <Link
                  to="/god-mode"
                  className="btn"
                  data-testid="cta-godmode"
                  style={{ fontSize: 12, padding: "12px 22px" }}
                >
                  ⊕ ENTER GOD MODE →
                </Link>
              </Magnet>
              <Magnet>
                <Link
                  to="/intelligence"
                  className="btn ghost"
                  data-testid="cta-intel"
                  style={{ fontSize: 12, padding: "12px 22px" }}
                >
                  VIEW INTELLIGENCE
                </Link>
              </Magnet>
            </div>
          </Reveal>

          <Reveal delay={0.6}>
            <div
              style={{
                display: "flex",
                gap: 44,
                marginTop: 64,
                flexWrap: "wrap",
              }}
            >
              {[
                { k: "150", l: "INCIDENTS TRACKED" },
                { k: "54", l: "STATIONS LIVE" },
                { k: "5", l: "AGENT PIPELINE" },
                { k: "<3s", l: "DISPATCH P50" },
              ].map((s) => (
                <div key={s.l}>
                  <div
                    className="mono flow-gradient"
                    style={{ fontSize: 34, lineHeight: 1 }}
                  >
                    {s.k}
                  </div>
                  <div
                    className="display"
                    style={{
                      fontSize: 10,
                      color: "var(--text-mute)",
                      letterSpacing: "0.18em",
                      marginTop: 6,
                    }}
                  >
                    {s.l}
                  </div>
                </div>
              ))}
            </div>
          </Reveal>
        </div>

        <div
          style={{
            position: "relative",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            height: 540,
            transform: "translate(var(--mx, 0), var(--my, 0))",
            transition: "transform 0.6s cubic-bezier(0.16,1,0.3,1)",
          }}
        >
          <SplineLogo size={460} />
        </div>
      </section>

      {/* MARQUEE */}
      <section
        style={{
          position: "relative",
          zIndex: 2,
          padding: "12px 0",
          borderBlock: "1px solid var(--border)",
          background: "rgba(3,7,18,0.5)",
          backdropFilter: "blur(12px)",
        }}
      >
        <div className="marquee">
          <div
            className="marquee-track display"
            style={{
              fontSize: 22,
              color: "var(--text-dim)",
              letterSpacing: "0.18em",
            }}
          >
            {Array.from({ length: 2 })
              .flatMap((_, copy) => [
                ["TRIAGE", "var(--orange)"],
                ["·", "var(--text-mute)"],
                ["SPATIAL", "var(--cyan)"],
                ["·", "var(--text-mute)"],
                ["LOGISTICS", "var(--green)"],
                ["·", "var(--text-mute)"],
                ["SUPERVISOR", "var(--amber)"],
                ["·", "var(--text-mute)"],
                ["CRISIS COMMS", "var(--red)"],
                ["·", "var(--text-mute)"],
                ["AUTONOMOUS DISPATCH", "var(--orange)"],
                ["·", "var(--text-mute)"],
              ])
              .map(([w, c], i) => (
                <span key={i} style={{ color: c }}>
                  {w}
                </span>
              ))}
          </div>
        </div>
      </section>

      {/* MODULES */}
      <section
        style={{
          position: "relative",
          zIndex: 2,
          padding: "88px 32px",
          maxWidth: 1380,
          margin: "0 auto",
        }}
      >
        <Reveal>
          <div
            className="display"
            style={{
              fontSize: 11,
              color: "var(--cyan)",
              letterSpacing: "0.3em",
              marginBottom: 16,
            }}
          >
            ◢ FOUR MODULES · ONE COMMAND DECK
          </div>
        </Reveal>
        <Reveal delay={0.1}>
          <h2
            className="display"
            style={{ fontSize: 48, margin: 0, lineHeight: 1, maxWidth: 760 }}
          >
            Built for the <span className="flow-gradient">three seconds</span>{" "}
            after the call comes in.
          </h2>
        </Reveal>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: 18,
            marginTop: 56,
          }}
        >
          {[
            {
              t: "GOD MODE",
              sub: "/god-mode",
              d: "Full-map dispatch · 150 incidents · streaming agent activity · stress test loop.",
              to: "/god-mode",
              c: "var(--orange)",
              tag: "01",
            },
            {
              t: "SENTINEL GRID",
              sub: "/sentinel",
              d: "Citizen reports → swarm verification → autonomous dispatch when threshold crosses.",
              to: "/sentinel",
              c: "var(--cyan)",
              tag: "02",
            },
            {
              t: "INTELLIGENCE",
              sub: "/intelligence",
              d: "Closure metrics, confusion matrix, hourly heatmap, corridor risk top-10.",
              to: "/intelligence",
              c: "var(--green)",
              tag: "03",
            },
            {
              t: "DEBRIEF",
              sub: "/debrief",
              d: "Every mistake the model made — drift gauge, anomalies, retraining flags.",
              to: "/debrief",
              c: "var(--amber)",
              tag: "04",
            },
            {
              t: "VULNERABLE ZONES",
              sub: "/vulnerable",
              d: "Hospital corridors · school zones · fire stations. Human context, not just traffic volume.",
              to: "/vulnerable",
              c: "var(--red)",
              tag: "05",
            },
          ].map((card, i) => (
            <Reveal key={card.t} delay={i * 0.08}>
              <Link
                to={card.to}
                className="panel module-card"
                style={{
                  padding: 22,
                  textDecoration: "none",
                  color: "inherit",
                  display: "block",
                  height: "100%",
                  position: "relative",
                  transition:
                    "transform 0.4s cubic-bezier(0.16,1,0.3,1), box-shadow 0.4s",
                  overflow: "hidden",
                }}
                data-testid={`landing-card-${card.to.slice(1)}`}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-6px)";
                  e.currentTarget.style.boxShadow = `0 24px 60px ${card.c}33, 0 0 0 1px ${card.c}55 inset`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "none";
                  e.currentTarget.style.boxShadow = "";
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    right: 16,
                    top: 12,
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: card.c,
                    opacity: 0.5,
                  }}
                >
                  {card.tag}
                </div>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 4,
                    background: `linear-gradient(135deg, ${card.c}, transparent)`,
                    border: `1px solid ${card.c}`,
                    marginBottom: 14,
                    boxShadow: `0 0 18px ${card.c}66`,
                  }}
                />
                <div
                  className="display"
                  style={{
                    fontSize: 16,
                    color: card.c,
                    letterSpacing: "0.18em",
                    marginBottom: 4,
                  }}
                >
                  {card.t}
                </div>
                <div
                  className="mono"
                  style={{
                    fontSize: 10,
                    color: "var(--text-mute)",
                    marginBottom: 14,
                  }}
                >
                  {card.sub}
                </div>
                <div
                  style={{
                    fontSize: 13,
                    color: "var(--text-dim)",
                    lineHeight: 1.55,
                  }}
                >
                  {card.d}
                </div>
                <div
                  className="display"
                  style={{
                    marginTop: 24,
                    fontSize: 11,
                    color: card.c,
                    letterSpacing: "0.18em",
                  }}
                >
                  OPEN MODULE →
                </div>
              </Link>
            </Reveal>
          ))}
        </div>
      </section>

      {/* PIPELINE BAND */}
      <section
        style={{
          position: "relative",
          zIndex: 2,
          padding: "60px 32px 88px",
          maxWidth: 1380,
          margin: "0 auto",
        }}
      >
        <Reveal>
          <div
            className="display"
            style={{
              fontSize: 11,
              color: "var(--cyan)",
              letterSpacing: "0.3em",
              marginBottom: 16,
            }}
          >
            ◢ THE FIVE-AGENT PIPELINE
          </div>
        </Reveal>
        <Reveal delay={0.1}>
          <h2
            className="display"
            style={{ fontSize: 38, margin: 0, lineHeight: 1.05, maxWidth: 760 }}
          >
            Streamed via{" "}
            <span className="flow-gradient">Server-Sent Events</span>,
            frame-by-frame.
          </h2>
        </Reveal>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5,1fr)",
            gap: 12,
            marginTop: 48,
          }}
        >
          {[
            ["TRIAGE", "var(--orange)", "severity, closure prob, duration"],
            ["SPATIAL", "var(--cyan)", "baseline + diversion + buffer"],
            ["LOGISTICS", "var(--green)", "officers + barricades, MILP solve"],
            ["SUPERVISOR", "var(--amber)", "escalation, retry, expansion"],
            ["DIRECTIVE", "var(--red)", "tweet · sms · dispatch audio"],
          ].map(([n, c, d], i) => (
            <Reveal key={n} delay={i * 0.06}>
              <div
                className="panel"
                style={{
                  padding: 18,
                  height: "100%",
                  borderTop: `2px solid ${c}`,
                }}
              >
                <div className="mono" style={{ fontSize: 11, color: c }}>
                  0{i + 1}
                </div>
                <div
                  className="display"
                  style={{
                    fontSize: 14,
                    color: c,
                    marginTop: 8,
                    letterSpacing: "0.16em",
                  }}
                >
                  {n}
                </div>
                <div
                  className="mono"
                  style={{
                    fontSize: 11,
                    color: "var(--text-mute)",
                    marginTop: 8,
                    lineHeight: 1.5,
                  }}
                >
                  {d}
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* FINAL CTA */}
      <section
        style={{
          position: "relative",
          zIndex: 2,
          padding: "100px 32px",
          textAlign: "center",
          borderTop: "1px solid var(--border)",
          background:
            "linear-gradient(180deg, transparent, rgba(249,115,22,0.06))",
        }}
      >
        <Reveal>
          <div
            className="display flow-gradient"
            style={{
              fontSize: "clamp(40px, 6vw, 76px)",
              lineHeight: 1,
              fontWeight: 700,
              letterSpacing: "0.04em",
            }}
          >
            SHIP THE NEXT THREE SECONDS.
          </div>
        </Reveal>
        <Reveal delay={0.15}>
          <p
            style={{
              color: "var(--text-dim)",
              fontSize: 16,
              marginTop: 22,
              maxWidth: 540,
              marginLeft: "auto",
              marginRight: "auto",
              lineHeight: 1.55,
            }}
          >
            Press{" "}
            <kbd
              style={{
                color: "var(--orange)",
                border: "1px solid var(--orange)",
                padding: "2px 6px",
                borderRadius: 3,
                fontFamily: "var(--font-mono)",
              }}
            >
              ⌘K
            </kbd>{" "}
            from any page to jump.
          </p>
        </Reveal>
        <Reveal delay={0.25}>
          <div
            style={{
              display: "flex",
              gap: 14,
              justifyContent: "center",
              marginTop: 28,
            }}
          >
            <Magnet>
              <Link
                to="/god-mode"
                className="btn"
                style={{ fontSize: 12, padding: "14px 26px" }}
                data-testid="cta-final"
              >
                ⊕ ENTER GOD MODE →
              </Link>
            </Magnet>
          </div>
        </Reveal>
      </section>

      <footer
        style={{
          position: "relative",
          zIndex: 2,
          padding: "24px 32px",
          borderTop: "1px solid var(--border)",
          color: "var(--text-mute)",
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>CLEARPATH OS · v0.1 · HACKATHON BUILD</span>
        <span>BUILT FOR BENGALURU TRAFFIC POLICE</span>
      </footer>
    </div>
  );
}
