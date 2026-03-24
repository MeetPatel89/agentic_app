import { memo, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

interface Props {
  text: string;
  isStreaming: boolean;
}

/**
 * How often (ms) to re-parse markdown during streaming.
 * Higher = less flicker but more visual "staleness".
 * 300ms is a sweet spot: fast enough to feel live, slow enough to let
 * KaTeX finish rendering between updates.
 */
const MD_THROTTLE_MS = 300;

// ---------------------------------------------------------------------------
// LaTeX document-command → Markdown conversion
// ---------------------------------------------------------------------------

/** LaTeX environments that represent document structure, not math. */
const DOCUMENT_ENVS = new Set([
  "itemize", "enumerate", "description",
  "quote", "quotation", "verbatim",
  "center", "flushleft", "flushright",
  "abstract", "document", "figure", "table", "tabular",
  "minipage", "titlepage",
]);

/**
 * Convert LaTeX document-level commands to Markdown equivalents.
 * Runs BEFORE math delimiter conversion so that \begin{itemize} etc. are
 * never mistaken for math environments.
 */
function convertLatexDocumentCommands(text: string): string {
  // Sectioning commands → Markdown headings
  text = text.replace(/\\chapter\{([^}]*)\}/g, "# $1");
  text = text.replace(/\\section\{([^}]*)\}/g, "## $1");
  text = text.replace(/\\subsection\{([^}]*)\}/g, "### $1");
  text = text.replace(/\\subsubsection\{([^}]*)\}/g, "#### $1");
  text = text.replace(/\\paragraph\{([^}]*)\}/g, "**$1**");

  // Text formatting — iterate to resolve nesting
  for (let i = 0; i < 3; i++) {
    text = text.replace(/\\textbf\{([^{}]*)\}/g, "**$1**");
    text = text.replace(/\\textit\{([^{}]*)\}/g, "*$1*");
    text = text.replace(/\\emph\{([^{}]*)\}/g, "*$1*");
    text = text.replace(/\\underline\{([^{}]*)\}/g, "$1");
    text = text.replace(/\\texttt\{([^{}]*)\}/g, "`$1`");
  }

  // LaTeX dashes → unicode
  text = text.replace(/---/g, "\u2014");
  text = text.replace(/--/g, "\u2013");

  // \begin{itemize/enumerate}...\end{...} → markdown lists
  text = text.replace(
    /\\begin\{(itemize|enumerate)\}([\s\S]*?)\\end\{\1\}/g,
    (_, env: string, body: string) => {
      const numbered = env === "enumerate";
      let counter = 0;
      const lines: string[] = [];
      for (const item of body.split(/\\item\b\s*/)) {
        const trimmed = item.trim();
        if (!trimmed) continue;
        counter++;
        lines.push((numbered ? `${counter}. ` : "- ") + trimmed);
      }
      return "\n" + lines.join("\n") + "\n";
    },
  );

  // \begin{description}
  text = text.replace(
    /\\begin\{description\}([\s\S]*?)\\end\{description\}/g,
    (_, body: string) => {
      const items = body.split(/\\item\s*\[([^\]]*)\]\s*/);
      const lines: string[] = [];
      for (let i = 1; i < items.length; i += 2) {
        const label = items[i]?.trim() ?? "";
        const content = items[i + 1]?.trim() ?? "";
        lines.push(`- **${label}** ${content}`);
      }
      return "\n" + lines.join("\n") + "\n";
    },
  );

  // \begin{quote/quotation}
  text = text.replace(
    /\\begin\{(?:quote|quotation)\}([\s\S]*?)\\end\{(?:quote|quotation)\}/g,
    (_, body: string) =>
      "\n" + body.trim().split("\n").map((l: string) => "> " + l.trim()).join("\n") + "\n",
  );

  // \begin{verbatim}
  text = text.replace(
    /\\begin\{verbatim\}([\s\S]*?)\\end\{verbatim\}/g,
    (_, body: string) => "\n```\n" + body.trim() + "\n```\n",
  );

  // \begin{center}
  text = text.replace(
    /\\begin\{center\}([\s\S]*?)\\end\{center\}/g,
    (_, body: string) => "\n" + body.trim() + "\n",
  );

  // Strip no-op document commands
  text = text.replace(/\\(?:maketitle|tableofcontents|newpage|clearpage|centering|noindent)\b/g, "");
  text = text.replace(/\\(?:vspace|hspace)\{[^}]*\}/g, "");
  text = text.replace(/\\(?:bigskip|medskip|smallskip)\b/g, "\n");
  text = text.replace(/\\(?:label|ref|cite)\{[^}]*\}/g, "");
  text = text.replace(/\\footnote\{([^}]*)\}/g, " ($1)");
  text = text.replace(/\\begin\{document\}/g, "");
  text = text.replace(/\\end\{document\}/g, "");
  text = text.replace(/\\documentclass(?:\[[^\]]*\])?\{[^}]*\}/g, "");
  text = text.replace(/\\usepackage(?:\[[^\]]*\])?\{[^}]*\}/g, "");
  text = text.replace(/\\title\{([^}]*)\}/g, "# $1");
  text = text.replace(/\\author\{([^}]*)\}/g, "*$1*");
  text = text.replace(/\\date\{([^}]*)\}/g, "*$1*");

  return text;
}

// ---------------------------------------------------------------------------
// Math-environment wrapping (math envs only — document envs are already gone)
// ---------------------------------------------------------------------------

/** Regex matching common LaTeX *math* commands. */
const MATH_COMMAND_RE =
  /\\(?:mathbf|mathbb|mathcal|mathrm|mathsf|mathit|frac|dfrac|tfrac|sum|prod|int|iint|iiint|oint|lim|inf|sup|max|min|det|ln|log|exp|sin|cos|tan|sec|csc|sqrt|vec|hat|bar|tilde|dot|ddot|overline|underline|overbrace|underbrace|left|right|big|Big|bigg|Bigg|text|operatorname|quad|qquad|alpha|beta|gamma|Gamma|delta|Delta|epsilon|varepsilon|zeta|eta|theta|Theta|iota|kappa|lambda|Lambda|mu|nu|xi|Xi|pi|Pi|rho|sigma|Sigma|tau|phi|Phi|varphi|chi|psi|Psi|omega|Omega|infty|partial|nabla|forall|exists|in|notin|subset|subseteq|supset|supseteq|cup|cap|cdot|cdots|ldots|times|div|pm|mp|leq|geq|neq|approx|equiv|sim|propto|to|rightarrow|Rightarrow|leftarrow|Leftarrow|mapsto)\b/;

/** Document-level commands that should NOT be treated as bare math. */
const DOC_COMMAND_RE =
  /^\\(?:section|subsection|subsubsection|paragraph|chapter|part|item|label|ref|cite|begin|end|textbf|textit|emph|underline|texttt|footnote|caption|centering|title|author|date|maketitle|tableofcontents|newpage|clearpage|vspace|hspace|noindent|bigskip|medskip|smallskip)\b/;

function isBareLatexMath(line: string): boolean {
  if (!line || line.length < 3) return false;
  if (/^(?:#{1,6}\s|[-*+]\s|\d+\.\s|```|>|\|)/.test(line)) return false;
  if (line.includes("$")) return false;
  if (!line.includes("\\")) return false;
  if (DOC_COMMAND_RE.test(line)) return false;
  return MATH_COMMAND_RE.test(line);
}

function wrapBareLatexBlocks(text: string): string {
  const lines = text.split("\n");
  const result: string[] = [];
  let inDollarBlock = false;
  let inLatexEnv = false;
  let currentEnvName = "";
  const envBuffer: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed === "$$") {
      inDollarBlock = !inDollarBlock;
      result.push(line);
      continue;
    }
    if (inDollarBlock) { result.push(line); continue; }

    const beginMatch = !inLatexEnv && trimmed.match(/^\\begin\{(\w+)\}/);
    if (beginMatch) {
      const envName = beginMatch[1]!;
      if (DOCUMENT_ENVS.has(envName)) { result.push(line); continue; }
      inLatexEnv = true;
      currentEnvName = envName;
      envBuffer.length = 0;
      envBuffer.push(trimmed);
      if (/\\end\{/.test(trimmed)) {
        result.push("$$", ...envBuffer, "$$");
        inLatexEnv = false;
        envBuffer.length = 0;
      }
      continue;
    }

    if (inLatexEnv) {
      envBuffer.push(trimmed);
      if (new RegExp(`\\\\end\\{${currentEnvName}\\}`).test(trimmed)) {
        result.push("$$", ...envBuffer, "$$");
        inLatexEnv = false;
        envBuffer.length = 0;
      }
      continue;
    }

    if (isBareLatexMath(trimmed)) {
      result.push("$$", trimmed, "$$");
    } else {
      result.push(line);
    }
  }

  // Unclosed env mid-stream → push raw (don't wrap in broken $$)
  if (inLatexEnv && envBuffer.length > 0) {
    result.push(...envBuffer);
  }

  return result.join("\n");
}

// ---------------------------------------------------------------------------
// Streaming-safe LaTeX preprocessing
// ---------------------------------------------------------------------------

/**
 * Strip an incomplete (unclosed) math delimiter at the very end of the text.
 * During streaming the final chunk often ends with `\(` or `\[` that hasn't
 * been closed yet.  Leaving it in causes KaTeX parse errors.
 *
 * We also handle incomplete trailing `$$` blocks:  if there's an odd number
 * of `$$` fences the last one is unclosed, so we strip from it to the end.
 */
function stripTrailingIncompleteMath(text: string): string {
  // Incomplete \(...  or  \[...
  text = text.replace(/\\\((?:(?!\\\)).)*$/s, "");
  text = text.replace(/\\\[(?:(?!\\\]).)*$/s, "");

  // Incomplete trailing $$ block (odd count means the last one is unclosed)
  const ddParts = text.split("$$");
  if (ddParts.length > 1 && ddParts.length % 2 === 0) {
    // Even number of parts = odd number of $$ = last block is unclosed
    // Remove everything from the last $$
    ddParts.pop();
    text = ddParts.join("$$");
  }

  // Incomplete trailing single $ (odd number of single-$ delimiters on the
  // last line means there's an unclosed inline math span).
  const lastNewline = text.lastIndexOf("\n");
  const lastLine = text.slice(lastNewline + 1);
  // Count un-escaped $ that are not part of $$
  const singleDollars = lastLine.match(/(?<!\$)\$(?!\$)/g);
  if (singleDollars && singleDollars.length % 2 === 1) {
    // Strip from the last $ to end of string
    const idx = text.lastIndexOf("$");
    if (idx >= 0) text = text.slice(0, idx);
  }

  return text;
}

/**
 * Master preprocessing: LaTeX document commands → Markdown, then normalize
 * math delimiters into the $/$$ format that remark-math expects.
 */
function preprocessLatex(text: string): string {
  // 0. Convert document-level LaTeX → Markdown (before math processing)
  text = convertLatexDocumentCommands(text);

  // 1. Display math: \[...\] → $$...$$ (only complete pairs)
  text = text.replace(/\\\[([\s\S]*?)\\\]/g, "\n$$\n$1\n$$\n");

  // 2. Inline math: \(...\) → $...$ (only complete pairs)
  text = text.replace(
    /\\\(([\s\S]*?)\\\)/g,
    (_, c: string) => `$${c.trim()}$`,
  );

  // 2b. Promote multi-line $...$ to display math $$...$$
  //     remark-math only supports single-line inline $ delimiters.
  //     If $...$ spans multiple lines (common with \begin{aligned}, \begin{pmatrix}, etc.)
  //     convert to display math so KaTeX can render it.
  text = text.replace(
    /(?<!\$)\$(?!\$)((?:[^$]|\\\$)+?)\$(?!\$)/gs,
    (match, content: string) => {
      if (content.includes("\n")) {
        return "\n$$\n" + content.trim() + "\n$$\n";
      }
      return match;
    },
  );

  // 3. Fix spaced single-dollar signs:  $ x $ → $x$
  //    remark-math requires no space after opening / before closing $.
  text = text.replace(
    /(?<=\s|^)\$\s+((?:[^$\\]|\\.)+?)\s+\$(?!\$)/gm,
    (_, c: string) => ` $${c}$`,
  );

  // 4. Wrap bare math \begin...\end and standalone math lines in $$
  text = wrapBareLatexBlocks(text);

  // 5. Strip incomplete trailing math delimiters (streaming safety)
  text = stripTrailingIncompleteMath(text);

  // 6. Collapse excessive blank lines
  text = text.replace(/\n{3,}/g, "\n\n");

  return text;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Stable reference for remark/rehype plugin arrays.
 * Avoids re-creating arrays on every render, which would cause ReactMarkdown
 * to re-initialize its unified pipeline and fully re-render the tree.
 */
const remarkPlugins = [remarkGfm, remarkMath];
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const rehypePlugins: any[] = [
  [rehypeKatex, { throwOnError: false, strict: false, output: "htmlAndMathml" }],
];

export const StreamOutput = memo(function StreamOutput({ text, isStreaming }: Props) {
  // Throttle the expensive markdown+KaTeX pipeline during streaming.
  const [markdownSource, setMarkdownSource] = useState(text);
  const latestTextRef = useRef(text);
  latestTextRef.current = text;

  // When not streaming, sync immediately
  useEffect(() => {
    if (!isStreaming) {
      setMarkdownSource(text);
    }
  }, [text, isStreaming]);

  // When streaming, update on a throttled interval
  useEffect(() => {
    if (!isStreaming) return;
    setMarkdownSource(latestTextRef.current);
    const id = setInterval(() => setMarkdownSource(latestTextRef.current), MD_THROTTLE_MS);
    return () => clearInterval(id);
  }, [isStreaming]);

  const processed = useMemo(() => preprocessLatex(markdownSource), [markdownSource]);

  return (
    <div className={`output-panel ${isStreaming ? "streaming" : ""}`}>
      {text ? (
        <div className="markdown-output">
          <ReactMarkdown
            remarkPlugins={remarkPlugins}
            rehypePlugins={rehypePlugins}
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
});
