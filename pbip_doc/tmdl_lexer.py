"""
TMDL (Tabular Model Definition Language) Lexer and Block Parser.
100% Python Standard Library implementation with zero external runtime dependencies.
Provides robust indentation-aware tokenization and hierarchical block parsing.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple, Any
import re
import textwrap

STRUCTURAL_KEYWORDS = {
    # Top-level (indent 0)
    "table", "model", "database", "relationship", "expression", "culture", "role", "function", "createOrReplace",
    # Member-level (indent 1)
    "column", "measure", "partition", "hierarchy", "level", "calculationGroup", "calculationItem", "refreshPolicy",
}

BOOLEAN_FLAGS = {
    "isHidden", "isKey", "isNameInferred", "isDataTypeInferred", "isDefaultLabel",
    "isDefaultImage", "isAvailableInMdx", "discourageImplicitMeasures",
    "relyOnReferentialIntegrity", "showAsVariationsOnly",
}

KNOWN_PROPERTIES = {
    "dataType", "formatString", "displayFolder", "lineageTag", "sourceColumn",
    "summarizeBy", "dataCategory", "sortByColumn", "description", "source",
    "mode", "entityName", "expressionSource", "queryGroup", "policyType",
    "rollingWindowPeriods", "rollingWindowGranularity", "incrementalPeriods",
    "incrementalGranularity", "pollingExpression", "sourceExpression",
    "fromColumn", "toColumn", "crossFilteringBehavior", "fromCardinality",
    "toCardinality", "precedence", "extendedProperty", "annotation", "sourceProviderType",
}


@dataclass
class TMDLBlock:
    """
    Represents an indentation-scoped block in a TMDL file.
    e.g. A table, column, measure, partition, hierarchy, relationship, or expression.
    """
    keyword: str                          # e.g., 'table', 'column', 'measure', 'partition', 'hierarchy', 'relationship', 'expression', 'function'
    name: str                             # Unquoted entity name
    indent: int                           # Indent level (0, 1, 2...)
    raw_header: str                       # Full header line
    inline_value: Optional[str] = None    # Text after '=' on header line
    expression: Optional[str] = None      # Full DAX/M expression if any
    properties: Dict[str, str] = field(default_factory=dict) # Property map (e.g. formatString, dataType)
    flags: Set[str] = field(default_factory=set)             # Set of boolean flags (e.g. isHidden, isKey)
    annotations: Dict[str, str] = field(default_factory=dict)# Annotations (e.g. PBI_NavigationStepName)
    doc_comment: Optional[str] = None     # Extracted /// doc comments
    children: List['TMDLBlock'] = field(default_factory=list) # Nested sub-blocks
    line_number: int = 1


def count_indent(line: str) -> Tuple[int, str]:
    """
    Counts indentation level and returns (indent_level, stripped_line).
    Handles tab-indentation and space-indentation (4 spaces or 2 spaces).
    """
    indent = 0
    i = 0
    n = len(line)
    while i < n:
        if line[i] == '\t':
            indent += 1
            i += 1
        elif line[i:i+4] == '    ':
            indent += 1
            i += 4
        elif line[i:i+2] == '  ' and (i + 2 == n or line[i+2] != ' '):
            indent += 1
            i += 2
        elif line[i] == ' ':
            i += 1
        else:
            break
    stripped = line[i:].rstrip('\r\n')
    return indent, stripped


def unquote_tmdl_name(s: str) -> str:
    """Strips outer single or double quotes from TMDL entity names."""
    s = s.strip()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1].strip()
    return s


def clean_multiline_code(expr: Optional[str]) -> Optional[str]:
    """Strips TMDL triple backticks (``` or ```dax / ```m) and dedents."""
    if not expr:
        return expr
    s = expr.strip()
    if s.startswith("```"):
        s = re.sub(r'^```(?:(?:dax|m)\b)?[^\S\r\n]*\r?\n?', '', s, flags=re.IGNORECASE)
    if s.endswith("```"):
        s = re.sub(r'\r?\n?\s*```\s*$', '', s)
    return textwrap.dedent(s).strip()


def clean_tmdl_description(desc: Optional[str]) -> Optional[str]:
    """Cleans a TMDL description, stripping quotes, triple backticks, and extra whitespace."""
    if not desc:
        return None
    d = desc.strip()
    if d.startswith("```") and d.endswith("```"):
        d = d[3:-3].strip()
    elif (d.startswith('"') and d.endswith('"')) or (d.startswith("'") and d.endswith("'")):
        d = d[1:-1].strip()
    return d if d else None


def parse_declaration_header(stripped: str) -> Optional[Tuple[str, str, Optional[str]]]:
    """
    Parses a declaration line like:
      table Sales
      table 'Sales Territory'
      table Date = CALENDARAUTO()
      column CustomerKey
      column 'Price Margin' = [Price] - [Cost]
      measure 'Total Sales' = SUM(Sales[Amount])
      measure 'Total Sales' =
      partition Sales-123 = m
      relationship 12345
      expression Query1 =
      function SafeDivide = ```dax ...
    Returns (keyword, name, inline_value) or None if not a declaration.
    """
    tokens = stripped.split(maxsplit=1)
    if not tokens:
        return None
    kw = tokens[0]
    if kw not in STRUCTURAL_KEYWORDS:
        if kw.lower() == "calculationgroup":
            kw = "calculationGroup"
        elif kw.lower() == "calculationitem":
            kw = "calculationItem"
        elif kw.lower() == "refreshpolicy":
            kw = "refreshPolicy"
        else:
            return None

    rest = tokens[1] if len(tokens) > 1 else ""
    rest = rest.strip()
    if not rest:
        return (kw, "", None)

    if kw == "refreshPolicy":
        if rest.startswith("="):
            return (kw, "refreshPolicy", rest[1:].strip())
        return (kw, "refreshPolicy", None)

    if rest.startswith("'"):
        end_q = rest.find("'", 1)
        if end_q != -1:
            name = rest[1:end_q]
            after = rest[end_q+1:].strip()
            inline_val = None
            if after.startswith("="):
                inline_val = after[1:].strip()
            return (kw, name, inline_val)
    elif rest.startswith('"'):
        end_q = rest.find('"', 1)
        if end_q != -1:
            name = rest[1:end_q]
            after = rest[end_q+1:].strip()
            inline_val = None
            if after.startswith("="):
                inline_val = after[1:].strip()
            return (kw, name, inline_val)

    if "=" in rest:
        parts = rest.split("=", 1)
        name = parts[0].strip()
        inline_val = parts[1].strip()
        return (kw, name, inline_val)
    else:
        return (kw, rest.strip(), None)


def parse_tmdl(content: str) -> List[TMDLBlock]:
    """
    Parses full TMDL content into a list of root TMDLBlock nodes.
    Maintains an indentation-driven state machine:
    - Verbatim code capture inside backtick blocks (``` ... ```)
    - Indentation boundary tracking for unbackticked multiline DAX and M expressions
    - Clean property/flag isolation without regex fragility
    """
    lines = content.splitlines()
    roots: List[TMDLBlock] = []
    stack: List[TMDLBlock] = []

    state = "NORMAL"  # "NORMAL", "BACKTICK_BLOCK", "INDENT_EXPR_BLOCK"
    expr_buffer: List[str] = []
    expr_target_block: Optional[TMDLBlock] = None
    expr_is_property: bool = False
    expr_prop_name: Optional[str] = None
    pending_doc_lines: List[str] = []

    def get_parent(indent: int) -> Optional[TMDLBlock]:
        while stack and stack[-1].indent >= indent:
            stack.pop()
        return stack[-1] if stack else None

    def flush_expression():
        nonlocal state, expr_buffer, expr_target_block, expr_is_property, expr_prop_name
        if expr_target_block and expr_buffer:
            full_code = "\n".join(expr_buffer)
            cleaned = clean_multiline_code(full_code)
            if expr_is_property and expr_prop_name:
                expr_target_block.properties[expr_prop_name] = cleaned or ""
            else:
                expr_target_block.expression = cleaned
        state = "NORMAL"
        expr_buffer = []
        expr_target_block = None
        expr_is_property = False
        expr_prop_name = None

    idx = 0
    n = len(lines)
    while idx < n:
        raw_line = lines[idx]
        indent, stripped = count_indent(raw_line)

        # 1. Inside Backtick block
        if state == "BACKTICK_BLOCK":
            if stripped.endswith("```") and stripped != "```dax" and stripped != "```m":
                line_before = raw_line.rstrip()
                if line_before.endswith("```"):
                    line_before = line_before[:-3]
                if line_before.strip():
                    expr_buffer.append(line_before)
                flush_expression()
            else:
                expr_buffer.append(raw_line)
            idx += 1
            continue

        # 2. Inside Indented expression block
        if state == "INDENT_EXPR_BLOCK":
            if stripped == "":
                expr_buffer.append("")
                idx += 1
                continue

            target = expr_target_block
            assert target is not None
            ends_expression = False

            if indent <= target.indent:
                ends_expression = True
            elif indent <= target.indent + 1:
                tokens = stripped.split(maxsplit=1)
                first_tok = tokens[0] if tokens else ""
                prop_key = first_tok.rstrip(":")
                if first_tok.endswith(":") and (prop_key in KNOWN_PROPERTIES or prop_key.startswith("PBI_")):
                    ends_expression = True
                elif first_tok in BOOLEAN_FLAGS:
                    ends_expression = True
                elif first_tok in STRUCTURAL_KEYWORDS or stripped.startswith("///"):
                    ends_expression = True
                elif stripped.startswith("annotation ") or stripped.startswith("extendedProperty "):
                    ends_expression = True

            if ends_expression:
                flush_expression()
                continue
            else:
                expr_buffer.append(raw_line)
                idx += 1
                continue

        # 3. NORMAL State
        if stripped == "":
            idx += 1
            continue

        if stripped.startswith("///"):
            doc_c = stripped[3:]
            if doc_c.startswith(" "):
                doc_c = doc_c[1:]
            pending_doc_lines.append(doc_c)
            idx += 1
            continue

        doc_comment = "\n".join(pending_doc_lines).strip() if pending_doc_lines else None
        pending_doc_lines = []

        decl = parse_declaration_header(stripped)
        if decl:
            kw, name, inline_val = decl
            block = TMDLBlock(
                keyword=kw,
                name=name,
                indent=indent,
                raw_header=stripped,
                inline_value=inline_val,
                doc_comment=doc_comment,
                line_number=idx + 1,
            )
            parent = get_parent(indent)
            if parent:
                parent.children.append(block)
            else:
                roots.append(block)
            stack.append(block)

            if inline_val is not None:
                if inline_val.startswith("```"):
                    if len(inline_val) > 3 and "```" in inline_val[3:]:
                        block.expression = clean_multiline_code(inline_val)
                    else:
                        state = "BACKTICK_BLOCK"
                        expr_target_block = block
                        expr_buffer = [inline_val]
                elif inline_val == "":
                    state = "INDENT_EXPR_BLOCK"
                    expr_target_block = block
                    expr_buffer = []
                else:
                    block.expression = inline_val.strip()
                    next_idx = idx + 1
                    while next_idx < n and lines[next_idx].strip() == "":
                        next_idx += 1
                    if next_idx < n:
                        next_indent, next_strip = count_indent(lines[next_idx])
                        if next_indent > indent + 1:
                            state = "INDENT_EXPR_BLOCK"
                            expr_target_block = block
                            expr_buffer = [inline_val]

            idx += 1
            continue

        current_parent = get_parent(indent)
        if not current_parent and stack:
            current_parent = stack[-1]

        if current_parent:
            if stripped in BOOLEAN_FLAGS:
                current_parent.flags.add(stripped)
                idx += 1
                continue

            if stripped.startswith("annotation "):
                ann_part = stripped[len("annotation "):].strip()
                if "=" in ann_part:
                    k, v = ann_part.split("=", 1)
                    current_parent.annotations[k.strip()] = v.strip()
                else:
                    current_parent.annotations[ann_part] = "true"
                idx += 1
                continue

            if stripped.startswith("extendedProperty "):
                prop_part = stripped[len("extendedProperty "):].strip()
                if "=" in prop_part:
                    k, v = prop_part.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if v == "" or v.startswith("{"):
                        state = "INDENT_EXPR_BLOCK"
                        expr_target_block = current_parent
                        expr_is_property = True
                        expr_prop_name = k
                        expr_buffer = [v] if v else []
                    else:
                        current_parent.properties[k] = v
                idx += 1
                continue

            if stripped == "source":
                block = TMDLBlock(
                    keyword="source",
                    name="source",
                    indent=indent,
                    raw_header=stripped,
                    line_number=idx + 1,
                )
                parent = get_parent(indent)
                if parent:
                    parent.children.append(block)
                else:
                    roots.append(block)
                stack.append(block)
                idx += 1
                continue

            if stripped.startswith("source ="):
                val = stripped.split("=", 1)[1].strip()
                if val.startswith("```"):
                    state = "BACKTICK_BLOCK"
                    expr_target_block = current_parent
                    expr_is_property = True
                    expr_prop_name = "source"
                    expr_buffer = [val]
                elif val == "":
                    state = "INDENT_EXPR_BLOCK"
                    expr_target_block = current_parent
                    expr_is_property = True
                    expr_prop_name = "source"
                    expr_buffer = []
                else:
                    current_parent.properties["source"] = val
                    next_idx = idx + 1
                    while next_idx < n and lines[next_idx].strip() == "":
                        next_idx += 1
                    if next_idx < n:
                        next_indent, _ = count_indent(lines[next_idx])
                        if next_indent > indent:
                            state = "INDENT_EXPR_BLOCK"
                            expr_target_block = current_parent
                            expr_is_property = True
                            expr_prop_name = "source"
                            expr_buffer = [val]
                idx += 1
                continue

            if ":" in stripped:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip()
                if v.startswith("```"):
                    state = "BACKTICK_BLOCK"
                    expr_target_block = current_parent
                    expr_is_property = True
                    expr_prop_name = k
                    expr_buffer = [v]
                else:
                    current_parent.properties[k] = v
                idx += 1
                continue

            if "=" in stripped:
                k, v = stripped.split("=", 1)
                current_parent.properties[k.strip()] = v.strip()
                idx += 1
                continue

        idx += 1

    flush_expression()
    return roots


def find_blocks(blocks: List[TMDLBlock], keyword: str, recursive: bool = False) -> List[TMDLBlock]:
    """Finds all blocks with the matching keyword."""
    res: List[TMDLBlock] = []
    for b in blocks:
        if b.keyword == keyword:
            res.append(b)
        if recursive and b.children:
            res.extend(find_blocks(b.children, keyword, recursive=True))
    return res


def find_first_block(blocks: List[TMDLBlock], keyword: str, recursive: bool = True) -> Optional[TMDLBlock]:
    """Finds the first block matching keyword (breadth-first or depth-first)."""
    for b in blocks:
        if b.keyword == keyword:
            return b
    if recursive:
        for b in blocks:
            found = find_first_block(b.children, keyword, recursive=True)
            if found:
                return found
    return None
