export default function Panel({ title, right, children, className = "", style, testId }) {
    return (
        <div className={`panel ${className}`} style={style} data-testid={testId}>
            {(title || right) && (
                <div className="panel-header">
                    <span>{title}</span>
                    {right && <span>{right}</span>}
                </div>
            )}
            <div className="panel-body">{children}</div>
        </div>
    );
}
