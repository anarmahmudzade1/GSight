"""Lightweight, language-agnostic syntax highlighter used inside chat code blocks."""

import re

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

KEYWORDS = [
    "def", "class", "return", "import", "from", "as", "if", "elif", "else",
    "for", "while", "try", "except", "finally", "with", "in", "is", "not",
    "and", "or", "None", "True", "False", "self", "async", "await", "lambda",
    "yield", "raise", "pass", "break", "continue", "function", "const", "let",
    "var", "public", "private", "static", "void", "int", "string", "bool",
    "new", "this", "export", "default",
]


def _format(color: str, bold: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    return fmt


class CodeHighlighter(QSyntaxHighlighter):
    """Regex-based highlighting (keywords, strings, numbers, comments) for a code-only document."""

    def __init__(self, document):
        super().__init__(document)
        self._rules = [
            (re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"'), _format("#98c379")),
            (re.compile(r"'[^'\\]*(?:\\.[^'\\]*)*'"), _format("#98c379")),
            (re.compile(r"\b\d+(\.\d+)?\b"), _format("#d19a66")),
            (re.compile(r"\b(" + "|".join(KEYWORDS) + r")\b"), _format("#c678dd", bold=True)),
            (re.compile(r"#.*$"), _format("#5c6370")),
            (re.compile(r"//.*$"), _format("#5c6370")),
        ]

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)
