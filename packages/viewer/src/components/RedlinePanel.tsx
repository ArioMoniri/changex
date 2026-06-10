import { useEffect, useRef } from "react";

interface Props {
  html: string;
  loading: boolean;
  /**
   * When set, the panel runs in "document" mode: the iframe runs un-sandboxed so the host
   * can reach into its (same-origin) document and scroll to / highlight the paragraph a
   * selected commit changed (by node_id). The doc HTML is our own, fully-escaped, script-free
   * renderer output — WebKit reports a null contentDocument for a sandboxed srcDoc frame even
   * with allow-same-origin, so dropping the sandbox is what makes the highlight reachable.
   */
  focusNode?: string | null;
}

/**
 * Renders the redline HTML produced by the core CLI (or local fallback) inside
 * a sandboxed iframe so its inline styles can't leak into the app shell and any
 * markup is isolated from the host document.
 */
export function RedlinePanel({ html, loading, focusNode }: Props) {
  const ref = useRef<HTMLIFrameElement>(null);
  const docMode = focusNode !== undefined;

  // In document mode, scroll to + highlight the paragraph for the selected commit.
  // Re-runs when the focused node changes OR when fresh HTML loads into the frame.
  useEffect(() => {
    if (!docMode || !focusNode) return;
    const scrollToNode = () => {
      const doc = ref.current?.contentDocument;
      if (!doc) return;
      doc.querySelectorAll(".cx-focus").forEach((el) => el.classList.remove("cx-focus"));
      const target = doc.getElementById(`cx-node-${focusNode}`);
      if (target) {
        target.classList.add("cx-focus");
        target.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    };
    // The doc may still be loading the first time; try now and again on load.
    scrollToNode();
    const frame = ref.current;
    frame?.addEventListener("load", scrollToNode);
    return () => frame?.removeEventListener("load", scrollToNode);
  }, [docMode, focusNode, html]);

  if (loading) {
    return <div className="redline-status">Rendering…</div>;
  }
  if (!html) {
    return <div className="redline-status">Load a journal to see the redline.</div>;
  }
  return (
    <iframe
      ref={ref}
      className="redline-frame"
      title="ChangeX redline"
      // Graph mode is fully sandboxed (purely visual). Document mode runs un-sandboxed so the
      // host can scroll to / highlight the changed paragraph — the content is our own
      // script-free, fully-escaped renderer output, so this is safe.
      {...(docMode ? {} : { sandbox: "" })}
      srcDoc={html}
    />
  );
}
