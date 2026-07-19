// "What am I inside?" for the sticky context header (D-130).
//
// Scrolling into the middle of a long function costs you the line that makes
// the body legible -- the signature. This finds it: the nearest enclosing
// definition above the first visible line, by indentation.
//
// Deliberately a heuristic on text, not a parse. A real parser for every
// language we might ship is a large dependency and a large surface for being
// subtly wrong; being approximately right about "you are inside
// `def apply_discount`" is worth almost all of the value. When it cannot
// decide, it returns null and the header does not render, which is the correct
// failure: no header beats a wrong header.

export interface Signature {
  line: number;
  text: string;
}

/** Definition-like line starts, by language family. Ordered by how strongly
 * they indicate an enclosing scope worth pinning. */
const PATTERNS: Record<string, RegExp[]> = {
  python: [/^\s*(?:async\s+def|def|class)\s+\w+/],
  javascript: [
    /^\s*(?:export\s+)?(?:async\s+)?function\s*\*?\s*\w*/,
    /^\s*(?:export\s+)?class\s+\w+/,
    /^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?(?:function|\([^)]*\)\s*=>|\w+\s*=>)/,
    /^\s*\w+\s*\([^)]*\)\s*\{\s*$/,
  ],
};

// Languages that share a family's syntax closely enough to share its patterns.
const FAMILY: Record<string, string> = {
  python: 'python',
  py: 'python',
  javascript: 'javascript',
  js: 'javascript',
  jsx: 'javascript',
  typescript: 'javascript',
  ts: 'javascript',
  tsx: 'javascript',
  java: 'javascript',
  go: 'javascript',
  rust: 'javascript',
  c: 'javascript',
  cpp: 'javascript',
  csharp: 'javascript',
};

function indentOf(line: string): number {
  const match = /^[ \t]*/.exec(line);
  if (!match) return 0;
  // A tab counts as one level, same as any run of spaces: the comparison here
  // is "less indented than", and mixing the two within one file is rare enough
  // that resolving tab width precisely would be false precision.
  return match[0].replace(/\t/g, '    ').length;
}

function isBlank(line: string): boolean {
  return line.trim().length === 0;
}

/**
 * The signature enclosing `line` (1-based), or null when there is none worth
 * pinning -- including the common case where the first visible line IS the
 * definition, since a header repeating the line directly under it is noise.
 */
export function enclosingSignature(code: string, language: string, line: number): Signature | null {
  if (line <= 1) return null;

  const lines = code.replace(/\n+$/, '').split('\n');
  const index = line - 1;
  if (index <= 0 || index >= lines.length) return null;

  const patterns = PATTERNS[FAMILY[language?.toLowerCase()] ?? ''] ?? null;
  if (!patterns) return null;

  // Indentation of the first NON-BLANK line at or after the fold. A blank line
  // has no indentation to speak of, and using its zero would defeat every
  // enclosure test below it.
  let referenceIndex = index;
  while (referenceIndex < lines.length && isBlank(lines[referenceIndex])) referenceIndex += 1;
  if (referenceIndex >= lines.length) return null;
  const reference = indentOf(lines[referenceIndex]);

  for (let i = referenceIndex - 1; i >= 0; i -= 1) {
    const candidate = lines[i];
    if (isBlank(candidate)) continue;
    // Strictly less indented: a sibling at the same level does not enclose.
    if (indentOf(candidate) >= reference) continue;
    if (patterns.some((pattern) => pattern.test(candidate))) {
      return { line: i + 1, text: candidate.trim() };
    }
  }
  return null;
}
