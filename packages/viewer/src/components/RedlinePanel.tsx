interface Props {
  html: string;
  loading: boolean;
}

/**
 * Renders the redline HTML produced by the core CLI (or local fallback) inside
 * a sandboxed iframe so its inline styles can't leak into the app shell and any
 * markup is isolated from the host document.
 */
export function RedlinePanel({ html, loading }: Props) {
  if (loading) {
    return <div className="redline-status">Rendering redline…</div>;
  }
  if (!html) {
    return <div className="redline-status">Load a journal to see the redline.</div>;
  }
  return (
    <iframe
      className="redline-frame"
      title="ChangeX redline"
      sandbox=""
      srcDoc={html}
    />
  );
}
