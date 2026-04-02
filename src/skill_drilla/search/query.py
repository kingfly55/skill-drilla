"""Query parsing and matching for interactive corpus search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

_BOOLEAN_OPERATORS = {"AND", "OR"}


class QuerySyntaxError(ValueError):
    """Raised when a search query uses unsupported or invalid syntax."""


@dataclass(frozen=True)
class QueryTerm:
    value: str
    is_phrase: bool = False

    def to_dict(self) -> dict[str, object]:
        return {"value": self.value, "is_phrase": self.is_phrase}


@dataclass(frozen=True)
class ParsedQuery:
    original: str
    operator: str
    terms: tuple[QueryTerm, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "original": self.original,
            "operator": self.operator,
            "terms": [term.to_dict() for term in self.terms],
        }

    def matches(self, text: str | None) -> bool:
        haystack = (text or "").casefold()
        if not self.terms:
            return False
        checks = tuple(term.value.casefold() in haystack for term in self.terms)
        if self.operator == "AND":
            return all(checks)
        return any(checks)


@dataclass(frozen=True)
class SearchFilters:
    project_slugs: tuple[str, ...] = ()
    session_ids: tuple[str, ...] = ()
    semantic_classes: tuple[str, ...] = ()
    include_subagents: bool | None = None
    limit: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "project_slugs": list(self.project_slugs),
            "session_ids": list(self.session_ids),
            "semantic_classes": list(self.semantic_classes),
            "include_subagents": self.include_subagents,
            "limit": self.limit,
        }

    def matches(self, evidence: dict[str, object]) -> bool:
        if self.project_slugs and evidence.get("project_slug") not in self.project_slugs:
            return False
        if self.session_ids and evidence.get("session_id") not in self.session_ids:
            return False
        if self.semantic_classes and evidence.get("semantic_class") not in self.semantic_classes:
            return False
        if self.include_subagents is False and evidence.get("session_role") == "subagent":
            return False
        return True


def parse_query(raw_query: str) -> ParsedQuery:
    query = raw_query.strip()
    if not query:
        raise QuerySyntaxError("query must not be empty")

    tokens = _tokenize(query)
    operators = {token for token in tokens if token in _BOOLEAN_OPERATORS}
    if len(operators) > 1:
        raise QuerySyntaxError("mixed boolean operators are not supported")

    operator = next(iter(operators), "OR")
    if any(token in _BOOLEAN_OPERATORS for token in (tokens[0], tokens[-1])):
        raise QuerySyntaxError("query cannot start or end with a boolean operator")

    terms: list[QueryTerm] = []
    expect_term = True
    for token in tokens:
        if token in _BOOLEAN_OPERATORS:
            if expect_term:
                raise QuerySyntaxError("boolean operators must separate terms")
            expect_term = True
            continue
        if not expect_term:
            if operator == "OR" and len(operators) == 0:
                pass
            else:
                raise QuerySyntaxError("terms must be separated by the configured operator")
        is_phrase = token.startswith('"') and token.endswith('"')
        value = token[1:-1] if is_phrase else token
        if not value.strip():
            raise QuerySyntaxError("empty phrases are not supported")
        terms.append(QueryTerm(value=value, is_phrase=is_phrase))
        expect_term = False

    if expect_term:
        raise QuerySyntaxError("query cannot end with a boolean operator")

    if len(operators) == 0 and len(terms) > 1:
        operator = "OR"

    return ParsedQuery(original=raw_query, operator=operator, terms=tuple(terms))


def _tokenize(query: str) -> tuple[str, ...]:
    tokens: list[str] = []
    current: list[str] = []
    in_quote = False

    for char in query:
        if char == '"':
            current.append(char)
            in_quote = not in_quote
            if not in_quote:
                tokens.append("".join(current))
                current = []
            continue
        if char.isspace() and not in_quote:
            if current:
                tokens.append("".join(current))
                current = []
            continue
        current.append(char)

    if in_quote:
        raise QuerySyntaxError("unterminated quoted phrase")
    if current:
        tokens.append("".join(current))
    return tuple(_normalize_token(token) for token in tokens if token)


def _normalize_token(token: str) -> str:
    if token.startswith('"') and token.endswith('"'):
        return token
    upper = token.upper()
    if upper in _BOOLEAN_OPERATORS:
        return upper
    return token


def parse_csv_filters(values: Iterable[str] | None) -> tuple[str, ...]:
    items: list[str] = []
    for raw_value in values or ():
        for piece in raw_value.split(','):
            value = piece.strip()
            if value:
                items.append(value)
    return tuple(items)
