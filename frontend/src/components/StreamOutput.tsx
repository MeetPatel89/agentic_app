import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

interface Props {
  text: string;
  isStreaming: boolean;
}

/**
 * Regex matching common LaTeX math commands — used to detect bare math lines
 * that have no $...$ or $$...$$ delimiters.
 */
const MATH_COMMAND_RE =
  /\\(?:mathbf|mathbb|mathcal|mathrm|mathsf|mathit|frac|dfrac|tfrac|sum|prod|int|iint|iiint|oint|lim|inf|sup|max|min|det|ln|log|exp|sin|cos|tan|sec|csc|sqrt|vec|hat|bar|tilde|dot|ddot|overline|underline|overbrace|underbrace|left|right|big|Big|bigg|Bigg|text|operatorname|quad|qquad|alpha|beta|gamma|Gamma|delta|Delta|epsilon|varepsilon|zeta|eta|theta|Theta|iota|kappa|lambda|Lambda|mu|nu|xi|Xi|pi|Pi|rho|sigma|Sigma|tau|phi|Phi|varphi|chi|psi|Psi|omega|Omega|infty|partial|nabla|forall|exists|in|notin|subset|subseteq|supset|supseteq|cup|cap|cdot|cdots|ldots|times|div|pm|mp|leq|geq|neq|approx|equiv|sim|propto|to|rightarrow|Rightarrow|leftarrow|Leftarrow|mapsto)\b/;

/**
 * Check if a line is bare LaTeX math (no $ delimiters) that should be
 * wrapped in $$...$$ for display math rendering.
 */
function isBareLatexMath(line: string): boolean {
  if (!line || line.length < 3) return false;
  // Skip markdown syntax
  if (/^(?:#{1,6}\s|[-*+]\s|\d+\.\s|```|>|\|)/.test(line)) return false;
  // Skip lines that already have $ delimiters
  if (line.includes("$")) return false;
  // Skip lines with no backslash (can't be LaTeX)
  if (!line.includes("\\")) return false;
  // Must contain a recognized math command
  return MATH_COMMAND_RE.test(line);
}

/**
 * Wrap bare \begin{env}...\end{env} blocks and standalone math lines in $$.
 */
function wrapBareLatexBlocks(text: string): string {
  const lines = text.split("\n");
  const result: string[] = [];
  let inDollarBlock = false;
  let inLatexEnv = false;
  const envBuffer: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();

    // Track existing $$...$$ blocks so we don't double-wrap
    if (trimmed === "$$") {
      inDollarBlock = !inDollarBlock;
      result.push(line);
      continue;
    }

    if (inDollarBlock) {
      result.push(line);
      continue;
    }

    // Detect \begin{...} opening (not already in a $ block)
    if (!inLatexEnv && /^\\begin\{/.test(trimmed)) {
      inLatexEnv = true;
      envBuffer.length = 0;
      envBuffer.push(trimmed);
      // Single-line environment: \begin{...}...\end{...} on one line
      if (/\\end\{/.test(trimmed)) {
        result.push("$$", ...envBuffer, "$$");
        inLatexEnv = false;
        envBuffer.length = 0;
      }
      continue;
    }

    if (inLatexEnv) {
      envBuffer.push(trimmed);
      if (/\\end\{/.test(trimmed)) {
        result.push("$$", ...envBuffer, "$$");
        inLatexEnv = false;
        envBuffer.length = 0;
      }
      continue;
    }

    // Wrap standalone bare math lines
    if (isBareLatexMath(trimmed)) {
      result.push("$$", trimmed, "$$");
    } else {
      result.push(line);
    }
  }

  // Flush unclosed env (may happen mid-stream)
  if (inLatexEnv && envBuffer.length > 0) {
    result.push("$$", ...envBuffer, "$$");
  }

  return result.join("\n");
}

/**
 * Normalize all common LLM LaTeX formats into $...$ / $$...$$ that
 * remark-math can parse.
 */
function preprocessLatex(text: string): string {
  // 1. Display math: \[...\] → $$\n...\n$$
  text = text.replace(/\\\[([\s\S]*?)\\\]/g, "\n$$\n$1\n$$\n");

  // 2. Inline math: \(...\) → $...$  (trim inner spaces)
  text = text.replace(
    /\\\(([\s\S]*?)\\\)/g,
    (_, c: string) => `$${c.trim()}$`,
  );

  // 3. Fix spaced single-dollar signs: $ content $ → $content$
  //    remark-math rejects inline math with spaces adjacent to the delimiter.
  //    The opening $ must be preceded by whitespace or start-of-line to avoid
  //    matching the *closing* $ of a valid $x$ group and eating text between groups.
  text = text.replace(
    /(?<=\s|^)\$\s+((?:[^$\\]|\\.)+?)\s+\$(?!\$)/gm,
    (_, c: string) => ` $${c}$`,
  );

  // 4. Wrap bare LaTeX lines / \begin...\end blocks in $$...$$
  text = wrapBareLatexBlocks(text);

  // 5. Collapse excessive blank lines left by the transformations
  text = text.replace(/\n{3,}/g, "\n\n");

  return text;
}

export function StreamOutput({ text, isStreaming }: Props) {
  const processed = preprocessLatex(text);

  return (
    <div className={`output-panel ${isStreaming ? "streaming" : ""}`}>
      {text ? (
        <div className="markdown-output">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[
              [rehypeKatex, { throwOnError: false, strict: false }],
            ]}
          >
            {processed}
          </ReactMarkdown>
          {isStreaming && <span className="cursor-blink" />}
        </div>
      ) : (
        <>
          {!isStreaming && (
            <span style={{ color: "var(--text-muted)" }}>
              Output will appear here...
            </span>
          )}
          {isStreaming && <span className="cursor-blink" />}
        </>
      )}
    </div>
  );
}
