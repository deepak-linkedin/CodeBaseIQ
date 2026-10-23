from pathlib import Path

import tree_sitter_javascript as ts_javascript
import tree_sitter_python as ts_python
import tree_sitter_typescript as ts_typescript
from tree_sitter import Language,Parser

LANGUAGE_MODELS = {
    ".py": ts_python.language,
    ".js": ts_javascript.language,
    ".jsx": ts_javascript.language,
    ".ts": ts_typescript.language_typescript,
    ".tsx": ts_typescript.language_tsx,
}

# Syntax nodes that usually represent useful code units.
TARGET_NODE_TYPES = {
    "function_definition",
    "class_definition",
    "function_declaration",
    "class_declaration",
    "method_definition",
    "lexical_declaration",
    "variable_declaration",
    # "arrow_function",
}

def create_parser(extension: str) -> Parser:
    language_factory = LANGUAGE_MODELS.get(extension.lower())

    if language_factory is None:
        raise ValueError(f"Unsupported extension: {extension}")

    language = Language(language_factory())

    return Parser(language)

def parse_code(source: str, extension: str) -> dict:
    """
    Parse source code and return its syntax tree and source bytes.

    Tree-sitter uses byte offsets, so source slicing must use bytes.
    """
    source_bytes = source.encode("utf-8")
    parser = create_parser(extension)
    tree = parser.parse(source_bytes)

    return {
        "tree": tree,
        "source_bytes": source_bytes,
        "has_syntax_errors": tree.root_node.has_error,
    }

def extract_code_units(
    source: str,
    extension: str,
) -> list[dict]:
    """
    Extract useful syntax units with their original line numbers.
    """
    parsed = parse_code(source, extension)
    tree = parsed["tree"]
    source_bytes = parsed["source_bytes"]

    units = []

    def visit(node):
        if node.type in TARGET_NODE_TYPES:
            text = source_bytes[
                node.start_byte:node.end_byte
            ].decode("utf-8", errors="replace")

            if text.strip():
                units.append({
                    "node_type": node.type,
                    "start_line": node.start_point.row + 1,
                    "end_line": node.end_point.row + 1,
                    "code": text,
                })

        for child in node.children:
            visit(child)

    visit(tree.root_node)

    return {
        "units": units,
        "has_syntax_errors": parsed["has_syntax_errors"],
    }
