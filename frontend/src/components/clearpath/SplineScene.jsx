import Spline from "@splinetool/react-spline";

export default function SplineScene({ style }) {
  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        overflow: "hidden",
        ...style,
      }}
    >
      <Spline
        scene="https://prod.spline.design/VqcdJa5MXeqyx7HK/scene.splinecode"
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%) scale(1.1)",
          transformOrigin: "center center",
          width: "100%",
          height: "100%",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 12,
          right: 12,
          left: 20,
          height: 40,
          padding: "0 20px",
          background: "rgba(10,14,22,0.92)",
          borderRadius: 20,
          zIndex: 10,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          backdropFilter: "blur(6px)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <span
          style={{
            width: 9,
            height: 9,
            borderRadius: "50%",
            background: "var(--cyan)",
            boxShadow: "0 0 6px var(--cyan)",
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 15,
            color: "rgba(255,255,255,0.75)",
            letterSpacing: "0.08em",
            whiteSpace: "nowrap",
          }}
        >
          CLEARPATH OS
        </span>
      </div>
    </div>
  );
}
