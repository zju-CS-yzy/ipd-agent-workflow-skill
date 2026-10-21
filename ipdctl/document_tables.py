"""Validate managed HTML requirement registers without executing markup."""

from __future__ import annotations

from html.parser import HTMLParser
import re


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None
        self.invalid = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "table":
            if self.table is not None:
                self.invalid = True
            self.table = {"id": attrs.get("data-ipd-table"), "headers": [], "rows": []}
            self.tables.append(self.table)
        if self.table is None or not self.table["id"]:
            return
        allowed = {"table", "thead", "tbody", "tr", "th", "td", "br", "p", "code", "strong", "em", "a"}
        if tag not in allowed or any(k.startswith("on") or k == "style" for k in attrs):
            self.invalid = True
        if tag == "a" and attrs.get("href", "").strip().lower().startswith(("javascript:", "data:", "vbscript:")):
            self.invalid = True
        if tag == "tr":
            if self.row is not None:
                self.invalid = True
            self.row = []
        elif tag in {"th", "td"}:
            if self.row is None or self.cell is not None:
                self.invalid = True
            self.cell = {"tag": tag, "column": attrs.get("data-ipd-column"),
                         "rowspan": attrs.get("rowspan", "1"),
                         "colspan": attrs.get("colspan", "1"), "text": ""}
        elif tag in {"br", "p"} and self.cell is not None:
            self.cell["text"] += " "

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if self.table is None:
            return
        if tag in {"th", "td"}:
            if self.cell is None or self.row is None:
                self.invalid = True
            else:
                self.row.append(self.cell)
            self.cell = None
        elif tag == "tr":
            if self.row is None or self.cell is not None:
                self.invalid = True
            elif self.row and all(c["tag"] == "th" for c in self.row):
                self.table["headers"].append(self.row)
            else:
                self.table["rows"].append(self.row or [])
            self.row = None
        elif tag == "table":
            if self.row is not None or self.cell is not None:
                self.invalid = True
            self.table = None


def _parse(text):
    parser = _Tables()
    parser.feed(text)
    parser.close()
    if parser.table is not None or parser.row is not None or parser.cell is not None:
        parser.invalid = True
    return parser


def _expand(rows, width):
    """Expand shared cells before validating each independently identified row."""
    pending = {}
    expanded = []
    for row in rows:
        grid = {column: cell for column, (remaining, cell) in pending.items()}
        pending = {column: (remaining - 1, cell) for column, (remaining, cell) in pending.items() if remaining > 1}
        position = 0
        for cell in row:
            while position in grid:
                position += 1
            try:
                down, across = int(cell["rowspan"]), int(cell["colspan"])
            except (TypeError, ValueError):
                raise ValueError("invalid span") from None
            if down < 1 or down > len(rows) or across < 1 or position + across > width:
                raise ValueError("span leaves table")
            for column in range(position, position + across):
                if column in grid:
                    raise ValueError("overlapping spans")
                grid[column] = cell
                if down > 1:
                    pending[column] = (down - 1, cell)
            position += across
        if set(grid) != set(range(width)):
            raise ValueError("missing or extra cells")
        expanded.append([grid[c] for c in range(width)])
    if pending:
        raise ValueError("rowspan leaves table")
    return expanded


def _parent_issues(row: list[dict], identity: int, parent: int, canonical: dict,
                   document_type: str | None) -> list[str]:
    reference = row[identity]["text"].strip()
    requirement = canonical.get(reference)
    if requirement is None:
        return ["DOCUMENT_REQUIREMENT_REFERENCE:" + reference]
    expected_kind = {"sr_spec": "SR", "ar_spec": "AR"}.get(document_type)
    if expected_kind and requirement["kind"] != expected_kind:
        return ["DOCUMENT_REQUIREMENT_KIND:" + reference]
    value = row[parent]["text"].strip()
    if requirement.get("derived") and requirement["parent"] is None:
        # A waiver in free text cannot turn a normal requirement into a
        # derived one. The registry must explicitly declare that relationship.
        if not re.fullmatch(r"derived:\s*\S.*", value, re.S) or re.search(r"[a-z0-9._-]+@[1-9][0-9]*", value):
            return ["DOCUMENT_DERIVED_REASON:" + reference]
        return []
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*@[1-9][0-9]*", value):
        return ["DOCUMENT_PARENT_FORMAT:" + reference]
    ancestor = canonical.get(value)
    if ancestor is None:
        return ["DOCUMENT_PARENT_REFERENCE:" + reference]
    if ancestor["kind"] != {"SR": "IR", "AR": "SR"}.get(requirement["kind"]):
        return ["DOCUMENT_PARENT_KIND:" + reference]
    if value != requirement["parent"]:
        return ["DOCUMENT_PARENT_MISMATCH:" + reference]
    return []


def lint_tables(text: str, source: str, requirements: list[str], *,
                canonical: dict | None = None, document_type: str | None = None) -> list[str]:
    expected = _parse(source)
    definitions = {t["id"]: t for t in expected.tables if t["id"]}
    if document_type in {"sr_spec", "ar_spec"} and not any(
        {"requirement", "parent"} <= {c["column"] for c in header}
        for definition in definitions.values() for header in definition["headers"]
    ):
        return ["DOCUMENT_PARENT_COLUMN"]
    if not definitions:
        return []
    actual = _parse(text)
    if actual.invalid:
        return ["DOCUMENT_TABLE_MARKUP"]
    found = [t for t in actual.tables if t["id"]]
    if len(found) != len(definitions) or {t["id"] for t in found} != set(definitions):
        return ["DOCUMENT_TABLES"]
    issues = []
    for table in found:
        original = definitions[table["id"]]
        if len(table["headers"]) != 1 or len(original["headers"]) != 1:
            issues.append("DOCUMENT_COLUMNS")
            continue
        header = [(c["column"], " ".join(c["text"].split())) for c in table["headers"][0]]
        expected_header = [(c["column"], " ".join(c["text"].split())) for c in original["headers"][0]]
        if header != expected_header or any(c["colspan"] != "1" or c["rowspan"] != "1" for c in table["headers"][0]):
            issues.append("DOCUMENT_COLUMNS")
            continue
        try:
            rows = _expand(table["rows"], len(header))
        except ValueError:
            issues.append("DOCUMENT_TABLE_SPANS")
            continue
        if not rows:
            issues.append("DOCUMENT_FIELDS")
        identity = next((i for i, (key, _) in enumerate(header) if key == "requirement"), None)
        parent = next((i for i, (key, _) in enumerate(header) if key == "parent"), None)
        if parent is not None and canonical is None:
            issues.append("DOCUMENT_REFERENCE_CONTEXT")
        references = []
        for row in rows:
            if any(not c["text"].strip() for c in row):
                issues.append("DOCUMENT_FIELDS")
            if any(re.fullmatch(r"(?i)(n/?a|不适用)", c["text"].strip()) for c in row):
                issues.append("DOCUMENT_NA_REASON")
            if identity is not None:
                cell = row[identity]
                if cell["rowspan"] != "1" or cell["colspan"] != "1":
                    issues.append("DOCUMENT_REQUIREMENT_ID_MERGED")
                references.append(cell["text"].strip())
                if parent is not None and canonical is not None:
                    issues.extend(_parent_issues(row, identity, parent, canonical, document_type))
        if identity is not None and (len(references) != len(set(references)) or set(references) != set(requirements)):
            issues.append("DOCUMENT_REQUIREMENT_ROWS")
    return sorted(set(issues))
