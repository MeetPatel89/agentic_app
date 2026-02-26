import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

interface Props {
  text: string;
  isStreaming: boolean;
}

/**
 * LLMs often emit LaTeX with \(...\) and \[...\] delimiters.
 * remark-math expects $...$ and $$...$$ — convert before parsing.
 */
function preprocessLatex(text: string): string {
  // Display math: \[...\] → $$...$$
  text = text.replace(/\\\[([\s\S]*?)\\\]/g, "$$$$\n$1\n$$$$");
  // Inline math: \(...\) → $...$
  text = text.replace(/\\\(([\s\S]*?)\\\)/g, "$$$1$$");
  return text;
}

export function StreamOutput({ text, isStreaming }: Props) {
  const processed = preprocessLatex(text);

  return (
    <div className={`output-panel ${isStreaming ? "streaming" : ""}`}>
      {text ? (
        <div className="markdown-output">
          <ReactMarkdown
            remarkPlugins={[remarkMath]}
            rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
          >
            {processed}
          </ReactMarkdown>
          {isStreaming && <span className="cursor-blink" />}
        </div>
      ) : (
        <>
          {!isStreaming && (
            <span style={{ color: "var(--text-muted)" }}>Output will appear here...</span>
          )}
          {isStreaming && <span className="cursor-blink" />}
        </>
      )}
    </div>
  );
}
