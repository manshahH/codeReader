"""Static candidate gate: AST + text scan, before any sandbox execution.

Rejects forbidden imports/calls, code outside the sampled line budget, any
hinting name or comment (bug/fix/wrong/careful/note), a basic secret/profanity
screen, and any use of a set literal/comprehension (nondeterministic iteration
order). Purely static -- no execution -- so it runs cheaply before the
expensive sandbox stage.
"""

from __future__ import annotations

import ast
import dataclasses
import io
import re
import tokenize

FORBIDDEN_IMPORTS = frozenset(
    {
        "random",
        "time",
        "os",
        "sys",
        "io",
        "socket",
        "socketserver",
        "ssl",
        "threading",
        "asyncio",
        "subprocess",
        "multiprocessing",
        "uuid",
        "urllib",
        "http",
        "ftplib",
        "smtplib",
    },
)
FORBIDDEN_CALL_NAMES = frozenset({"input", "id", "exec", "eval", "compile", "open", "__import__"})
FORBIDDEN_ATTR_CALLS = frozenset({"now", "today", "utcnow"})

HINT_WORDS = ("bug", "fix", "wrong", "careful", "note")
# Common inflections, for matching identifier parts exactly (e.g. "buggy",
# "fixed") without falling back to substring matching, which would false
# -positive on unrelated words like "prefix" or "notebook".
_HINT_WORD_FORMS: dict[str, frozenset[str]] = {
    "bug": frozenset({"bug", "bugs", "buggy"}),
    "fix": frozenset({"fix", "fixes", "fixed", "fixing"}),
    "wrong": frozenset({"wrong", "wrongly"}),
    "careful": frozenset({"careful", "carefully"}),
    "note": frozenset({"note", "notes", "noted", "noting"}),
}
_ALL_HINT_FORMS = frozenset().union(*_HINT_WORD_FORMS.values())
_CAMEL_SPLIT = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")

_SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)api[_-]?key\s*=\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)password\s*=\s*['\"][^'\"]+['\"]"),
)
_PROFANITY = frozenset({"fuck", "shit", "asshole", "bitch"})


@dataclasses.dataclass(frozen=True)
class StaticGateResult:
    accepted: bool
    violations: list[str]


def _split_identifier(name: str) -> list[str]:
    """Split snake_case/camelCase into lowercase parts for exact hint matching.

    Whole-part matching (rather than substring) avoids false positives like
    "prefix"/"suffix"/"notebook" incidentally containing "fix"/"note".
    """
    parts: list[str] = []
    for underscore_part in name.split("_"):
        parts.extend(m.group(0).lower() for m in _CAMEL_SPLIT.finditer(underscore_part))
    return [p for p in parts if p]


def _iter_comments(code: str) -> list[str]:
    comments = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type == tokenize.COMMENT:
                comments.append(tok.string)
    except (tokenize.TokenizeError, IndentationError):
        pass
    return comments


def _iter_docstrings(tree: ast.AST) -> list[str]:
    docstrings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                docstrings.append(doc)
    return docstrings


def _iter_identifiers(tree: ast.AST) -> list[str]:
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.append(node.name)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
    return names


def check(code: str, *, line_budget: tuple[int, int] | None) -> StaticGateResult:
    """`line_budget=None` skips the length check only (D-51): the budget is a
    UX constraint on the code the user reads (buggy_code / trace code), so a
    fixed_code that legitimately grew past it via an inserted fix line is not
    a violation. Every other check always runs.
    """
    violations: list[str] = []

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return StaticGateResult(accepted=False, violations=[f"syntax_error: {exc}"])

    if line_budget is not None:
        line_count = len(code.splitlines())
        lo, hi = line_budget
        if not (lo <= line_count <= hi):
            violations.append(f"line_count {line_count} outside budget [{lo}, {hi}]")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_IMPORTS:
                    violations.append(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in FORBIDDEN_IMPORTS:
                violations.append(f"forbidden import: {node.module}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALL_NAMES:
                violations.append(f"forbidden call: {func.id}(...)")
            elif isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_ATTR_CALLS:
                violations.append(f"forbidden call: .{func.attr}(...)")
        elif isinstance(node, ast.Set | ast.SetComp):
            violations.append("set literal/comprehension used (nondeterministic iteration order)")

    for name in _iter_identifiers(tree):
        hit_parts = set(_split_identifier(name)) & _ALL_HINT_FORMS
        if hit_parts:
            violations.append(f"hinting name {name!r} contains {sorted(hit_parts)}")

    for comment in _iter_comments(code):
        for word in HINT_WORDS:
            if re.search(rf"\b{re.escape(word)}\b", comment, re.IGNORECASE):
                violations.append(
                    f"hinting word {word!r} found in comment: {comment.strip()[:60]!r}",
                )

    for docstring in _iter_docstrings(tree):
        for word in HINT_WORDS:
            if re.search(rf"\b{re.escape(word)}\b", docstring, re.IGNORECASE):
                violations.append(
                    f"hinting word {word!r} found in docstring: {docstring.strip()[:60]!r}",
                )

    for pattern in _SECRET_PATTERNS:
        if pattern.search(code):
            violations.append(f"possible secret matching pattern: {pattern.pattern}")

    lowered = code.lower()
    for word in _PROFANITY:
        if word in lowered:
            violations.append(f"profanity screen hit: {word!r}")

    return StaticGateResult(accepted=len(violations) == 0, violations=violations)
