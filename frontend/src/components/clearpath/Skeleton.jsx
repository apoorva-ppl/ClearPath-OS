export default function Skeleton({ width = "100%", height = 14, className = "", style }) {
    return (
        <div
            className={`skel ${className}`}
            style={{ width, height, ...style }}
        />
    );
}
