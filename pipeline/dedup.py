"""AST-normalized deduplication.

Strips user-defined identifiers (variables, parameters, function/class names),
literals, and comments/docstrings from a candidate, then hashes the canonical
form with sha256. Builtin/library names (dict, round, len, ...) are left
alone: they are never rebound in the snippet, so renaming them would collapse
structurally-similar-but-semantically-different code into false duplicates.

The hash is stored as `source.content_hash` on the exercise row -- no schema
migration needed, `source` is already a JSONB column -- and checked against
the live pool. Embedding similarity (cosine > 0.92 vs the live pool per
docs/01) is skipped at MVP.
TODO(post-M3): add an embeddings-based near-duplicate pass once the corpus is
large enough for near-duplicates (not just exact structural clones) to matter,
and an embedding provider/model is chosen.
"""

from __future__ import annotations

import ast
import hashlib


class _NameCollector(ast.NodeVisitor):
    """Collects names that are actually bound in this snippet (assignment
    targets, del targets, function/class names, parameters) -- as opposed to
    builtins or other names that are only ever read.
    """

    def __init__(self) -> None:
        self.user_names: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.user_names.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.user_names.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.user_names.add(node.name)
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        self.user_names.add(node.arg)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store | ast.Del):
            self.user_names.add(node.id)
        self.generic_visit(node)


def _strip_docstring(node: ast.AST) -> None:
    body = getattr(node, "body", None)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body.pop(0)


class _NormalizingTransformer(ast.NodeTransformer):
    def __init__(self, user_names: set[str]) -> None:
        self._user_names = user_names
        self._name_map: dict[str, str] = {}

    def _canonical(self, original: str) -> str:
        if original not in self._name_map:
            self._name_map[original] = f"_id{len(self._name_map)}"
        return self._name_map[original]

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self._user_names:
            node.id = self._canonical(node.id)
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        node.arg = self._canonical(node.arg)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.name = self._canonical(node.name)
        self.generic_visit(node)
        _strip_docstring(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.name = self._canonical(node.name)
        self.generic_visit(node)
        _strip_docstring(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.name = self._canonical(node.name)
        self.generic_visit(node)
        _strip_docstring(node)
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        value = node.value
        if value is None or isinstance(value, bool):
            return node  # True/False/None affect control flow, not "content"
        if isinstance(value, int | float | complex):
            return ast.copy_location(ast.Constant(value=0), node)
        if isinstance(value, str):
            return ast.copy_location(ast.Constant(value="_LIT"), node)
        if isinstance(value, bytes):
            return ast.copy_location(ast.Constant(value=b"_LIT"), node)
        return node

    def visit_Module(self, node: ast.Module) -> ast.AST:
        self.generic_visit(node)
        _strip_docstring(node)
        return node


def normalize_ast(code: str) -> str:
    tree = ast.parse(code)
    collector = _NameCollector()
    collector.visit(tree)
    normalized = _NormalizingTransformer(collector.user_names).visit(tree)
    ast.fix_missing_locations(normalized)
    return ast.unparse(normalized)


def content_hash(code: str) -> str:
    return hashlib.sha256(normalize_ast(code).encode("utf-8")).hexdigest()


def is_duplicate(code: str, live_pool_hashes: set[str]) -> bool:
    return content_hash(code) in live_pool_hashes
