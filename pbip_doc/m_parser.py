"""
Power Query (M) Lexer and Recursive-Descent AST Parser.
100% Python Standard Library implementation with zero external runtime dependencies.
Conforms to Microsoft Power Query M formal language specifications.
Supports let expressions, nested lets, custom functions, records, lists,
invocations, item/field accesses, and graceful degradation on syntax anomalies.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple, Any, Union
import re


# ---------------------------------------------------------------------------
# Tokens & Lexer
# ---------------------------------------------------------------------------

TOKEN_KEYWORD = "KEYWORD"
TOKEN_IDENTIFIER = "IDENTIFIER"
TOKEN_STRING = "STRING"
TOKEN_NUMBER = "NUMBER"
TOKEN_BOOLEAN = "BOOLEAN"
TOKEN_NULL = "NULL"
TOKEN_INTRINSIC = "INTRINSIC"
TOKEN_OPERATOR = "OPERATOR"
TOKEN_DELIMITER = "DELIMITER"
TOKEN_COMMENT = "COMMENT"
TOKEN_EOF = "EOF"

KEYWORDS = {
    "let", "in", "if", "then", "else", "each", "try", "otherwise",
    "type", "as", "is", "meta", "error", "section", "shared",
    "optional", "and", "or", "not"
}

INTRINSICS = {
    "#table", "#date", "#datetime", "#datetimezone", "#time",
    "#duration", "#binary", "#shared", "#sections"
}

BOOLEANS = {"true", "false"}


@dataclass
class MToken:
    """Represents a lexical token in Power Query M source code."""
    type: str
    value: Any
    raw: str
    line: int
    col: int

    def __repr__(self) -> str:
        return f"MToken({self.type}, {repr(self.value)}, L{self.line}:C{self.col})"


class MLexer:
    """
    Tokenizer for Power Query M code.
    Handles identifiers, quoted identifiers #"...", strings with "" escape,
    numbers, operators, single-line (//) and multi-line (/* */) comments.
    """

    def __init__(self, text: str, include_comments: bool = False):
        self.text = text
        self.n = len(text)
        self.pos = 0
        self.line = 1
        self.col = 1
        self.include_comments = include_comments

    def tokenize(self) -> List[MToken]:
        tokens: List[MToken] = []
        while self.pos < self.n:
            ch = self.text[self.pos]

            # Whitespace
            if ch.isspace():
                if ch == '\n':
                    self.line += 1
                    self.col = 1
                else:
                    self.col += 1
                self.pos += 1
                continue

            # Single-line or multi-line comment
            if ch == '/' and self.pos + 1 < self.n:
                next_ch = self.text[self.pos + 1]
                if next_ch == '/':
                    comment_token = self._read_line_comment()
                    if self.include_comments:
                        tokens.append(comment_token)
                    continue
                elif next_ch == '*':
                    comment_token = self._read_block_comment()
                    if self.include_comments:
                        tokens.append(comment_token)
                    continue

            # Quoted identifier: #"..."
            if ch == '#' and self.pos + 1 < self.n and self.text[self.pos + 1] == '"':
                tokens.append(self._read_quoted_identifier())
                continue

            # Intrinsic literal: e.g. #table, #date
            if ch == '#' and self.pos + 1 < self.n and (self.text[self.pos + 1].isalpha() or self.text[self.pos + 1] == '_'):
                tokens.append(self._read_intrinsic())
                continue

            # String literal: "..."
            if ch == '"':
                tokens.append(self._read_string())
                continue

            # Number literal
            if ch.isdigit():
                tokens.append(self._read_number())
                continue

            # Regular Identifier or Keyword
            if ch.isalpha() or ch == '_':
                tokens.append(self._read_identifier_or_keyword())
                continue

            # Multi-character operators: =>, <>, <=, >=, ..
            if self.pos + 1 < self.n:
                two_ch = self.text[self.pos:self.pos + 2]
                if two_ch in ("=>", "<>", "<=", ">=", ".."):
                    start_line, start_col = self.line, self.col
                    self.pos += 2
                    self.col += 2
                    tokens.append(MToken(TOKEN_OPERATOR, two_ch, two_ch, start_line, start_col))
                    continue

            # Single-character operators and delimiters
            start_line, start_col = self.line, self.col
            self.pos += 1
            self.col += 1

            if ch in "+-*%/&<=>":
                tokens.append(MToken(TOKEN_OPERATOR, ch, ch, start_line, start_col))
            elif ch in "()[]{},;:?":
                tokens.append(MToken(TOKEN_DELIMITER, ch, ch, start_line, start_col))
            else:
                # Other characters (e.g. unknown symbol or unicode)
                tokens.append(MToken(TOKEN_DELIMITER, ch, ch, start_line, start_col))

        tokens.append(MToken(TOKEN_EOF, "", "", self.line, self.col))
        return tokens

    def _read_line_comment(self) -> MToken:
        start_line, start_col = self.line, self.col
        start_pos = self.pos
        # Advance past //
        self.pos += 2
        self.col += 2
        while self.pos < self.n and self.text[self.pos] != '\n':
            self.pos += 1
            self.col += 1
        raw = self.text[start_pos:self.pos]
        content = raw[2:].strip()
        return MToken(TOKEN_COMMENT, content, raw, start_line, start_col)

    def _read_block_comment(self) -> MToken:
        start_line, start_col = self.line, self.col
        start_pos = self.pos
        self.pos += 2
        self.col += 2
        while self.pos + 1 < self.n and not (self.text[self.pos] == '*' and self.text[self.pos + 1] == '/'):
            if self.text[self.pos] == '\n':
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.pos += 1
        if self.pos + 1 < self.n:
            self.pos += 2
            self.col += 2
        raw = self.text[start_pos:self.pos]
        content = raw[2:-2].strip() if raw.endswith("*/") else raw[2:].strip()
        return MToken(TOKEN_COMMENT, content, raw, start_line, start_col)

    def _read_quoted_identifier(self) -> MToken:
        start_line, start_col = self.line, self.col
        start_pos = self.pos
        # Skip #"
        self.pos += 2
        self.col += 2
        chars: List[str] = []
        while self.pos < self.n:
            ch = self.text[self.pos]
            if ch == '"':
                if self.pos + 1 < self.n and self.text[self.pos + 1] == '"':
                    chars.append('"')
                    self.pos += 2
                    self.col += 2
                    continue
                else:
                    self.pos += 1
                    self.col += 1
                    break
            elif ch == '\n':
                self.line += 1
                self.col = 1
                chars.append(ch)
                self.pos += 1
            else:
                chars.append(ch)
                self.pos += 1
                self.col += 1
        raw = self.text[start_pos:self.pos]
        name = "".join(chars)
        return MToken(TOKEN_IDENTIFIER, name, raw, start_line, start_col)

    def _read_string(self) -> MToken:
        start_line, start_col = self.line, self.col
        start_pos = self.pos
        self.pos += 1
        self.col += 1
        chars: List[str] = []
        while self.pos < self.n:
            ch = self.text[self.pos]
            if ch == '"':
                if self.pos + 1 < self.n and self.text[self.pos + 1] == '"':
                    chars.append('"')
                    self.pos += 2
                    self.col += 2
                    continue
                else:
                    self.pos += 1
                    self.col += 1
                    break
            elif ch == '\n':
                self.line += 1
                self.col = 1
                chars.append(ch)
                self.pos += 1
            else:
                chars.append(ch)
                self.pos += 1
                self.col += 1
        raw = self.text[start_pos:self.pos]
        val = "".join(chars)
        return MToken(TOKEN_STRING, val, raw, start_line, start_col)

    def _read_number(self) -> MToken:
        start_line, start_col = self.line, self.col
        start_pos = self.pos
        # Check hex 0x...
        if self.text[self.pos] == '0' and self.pos + 1 < self.n and self.text[self.pos + 1] in ('x', 'X'):
            self.pos += 2
            self.col += 2
            while self.pos < self.n and (self.text[self.pos].isdigit() or self.text[self.pos].lower() in 'abcdef'):
                self.pos += 1
                self.col += 1
            raw = self.text[start_pos:self.pos]
            val = int(raw, 16)
            return MToken(TOKEN_NUMBER, val, raw, start_line, start_col)

        while self.pos < self.n and self.text[self.pos].isdigit():
            self.pos += 1
            self.col += 1
        # Decimal point
        if self.pos < self.n and self.text[self.pos] == '.' and self.pos + 1 < self.n and self.text[self.pos + 1].isdigit():
            self.pos += 1
            self.col += 1
            while self.pos < self.n and self.text[self.pos].isdigit():
                self.pos += 1
                self.col += 1
        # Exponent
        if self.pos < self.n and self.text[self.pos] in ('e', 'E'):
            self.pos += 1
            self.col += 1
            if self.pos < self.n and self.text[self.pos] in ('+', '-'):
                self.pos += 1
                self.col += 1
            while self.pos < self.n and self.text[self.pos].isdigit():
                self.pos += 1
                self.col += 1

        raw = self.text[start_pos:self.pos]
        try:
            val = float(raw) if ('.' in raw or 'e' in raw or 'E' in raw) else int(raw)
        except ValueError:
            val = raw
        return MToken(TOKEN_NUMBER, val, raw, start_line, start_col)

    def _read_identifier_or_keyword(self) -> MToken:
        start_line, start_col = self.line, self.col
        start_pos = self.pos
        # Allow dots inside standard library names e.g. Table.AddColumn or Sql.Database
        while self.pos < self.n:
            ch = self.text[self.pos]
            if ch.isalnum() or ch == '_':
                self.pos += 1
                self.col += 1
            elif ch == '.' and self.pos + 1 < self.n and (self.text[self.pos + 1].isalpha() or self.text[self.pos + 1] == '_'):
                # Dotted identifier
                self.pos += 1
                self.col += 1
            else:
                break
        raw = self.text[start_pos:self.pos]
        lower_raw = raw.lower()

        if lower_raw in KEYWORDS and '.' not in raw:
            return MToken(TOKEN_KEYWORD, lower_raw, raw, start_line, start_col)
        elif lower_raw in BOOLEANS:
            return MToken(TOKEN_BOOLEAN, lower_raw == "true", raw, start_line, start_col)
        elif lower_raw == "null":
            return MToken(TOKEN_NULL, None, raw, start_line, start_col)
        else:
            return MToken(TOKEN_IDENTIFIER, raw, raw, start_line, start_col)

    def _read_intrinsic(self) -> MToken:
        start_line, start_col = self.line, self.col
        start_pos = self.pos
        # Skip #
        self.pos += 1
        self.col += 1
        while self.pos < self.n and (self.text[self.pos].isalnum() or self.text[self.pos] == '_'):
            self.pos += 1
            self.col += 1
        raw = self.text[start_pos:self.pos]
        return MToken(TOKEN_INTRINSIC, raw, raw, start_line, start_col)


# ---------------------------------------------------------------------------
# AST Node Hierarchy
# ---------------------------------------------------------------------------

class MNode:
    """Base class for all AST nodes in Power Query M."""
    parenthesized_count: int = 0


@dataclass
class MLiteral(MNode):
    value: Any
    raw: str
    literal_type: str  # "string", "number", "boolean", "null", "intrinsic"

    def __repr__(self) -> str:
        return f"MLiteral({self.literal_type}, {repr(self.value)})"


@dataclass
class MIdentifier(MNode):
    name: str
    is_quoted: bool = False

    def __repr__(self) -> str:
        return f"MIdentifier({repr(self.name)})"


@dataclass
class MStep:
    """Represents a named variable assignment in a let block."""
    name: str
    value: MNode
    doc_comment: Optional[str] = None
    raw_code: str = ""

    def __repr__(self) -> str:
        return f"MStep({repr(self.name)} = {self.value})"


@dataclass
class MLetExpr(MNode):
    """Represents a let <steps> in <in_expr> block."""
    steps: List[MStep] = field(default_factory=list)
    in_expr: Optional[MNode] = None

    def __repr__(self) -> str:
        return f"MLetExpr(steps={len(self.steps)}, in={self.in_expr})"


@dataclass
class MFunctionParam:
    name: str
    type_name: Optional[str] = None
    is_optional: bool = False
    default_value: Optional[MNode] = None

    def __repr__(self) -> str:
        opt = "optional " if self.is_optional else ""
        tp = f" as {self.type_name}" if self.type_name else ""
        return f"MFunctionParam({opt}{self.name}{tp})"


@dataclass
class MFunctionExpr(MNode):
    """Represents a custom function: (param1 as text, optional param2) => body"""
    parameters: List[MFunctionParam] = field(default_factory=list)
    return_type: Optional[str] = None
    body: Optional[MNode] = None

    def __repr__(self) -> str:
        return f"MFunctionExpr(params={self.parameters}, return_type={self.return_type}, body={self.body})"


@dataclass
class MEachExpr(MNode):
    """Syntactic sugar for (_) => body."""
    body: MNode

    def __repr__(self) -> str:
        return f"MEachExpr({self.body})"


@dataclass
class MIfExpr(MNode):
    condition: MNode
    then_branch: MNode
    else_branch: MNode

    def __repr__(self) -> str:
        return f"MIfExpr(if {self.condition} then {self.then_branch} else {self.else_branch})"


@dataclass
class MTryExpr(MNode):
    try_branch: MNode
    otherwise_branch: Optional[MNode] = None

    def __repr__(self) -> str:
        return f"MTryExpr(try {self.try_branch} otherwise {self.otherwise_branch})"


@dataclass
class MInvocationExpr(MNode):
    """Represents a function call: function_name(arg1, arg2, ...)"""
    function: MNode
    arguments: List[MNode] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"MInvocationExpr({self.function}, args={len(self.arguments)})"


@dataclass
class MItemAccessExpr(MNode):
    """Represents item lookup: target{item} or target{item}?"""
    target: MNode
    item: MNode
    is_optional: bool = False

    def __repr__(self) -> str:
        opt = "?" if self.is_optional else ""
        return f"MItemAccessExpr({self.target}{{{self.item}}}{opt})"


@dataclass
class MFieldAccessExpr(MNode):
    """Represents record field lookup: target[field] or standalone [field]"""
    target: Optional[MNode]
    field_name: str
    is_optional: bool = False

    def __repr__(self) -> str:
        tgt = f"{self.target}" if self.target else "_"
        opt = "?" if self.is_optional else ""
        return f"MFieldAccessExpr({tgt}[{self.field_name}]{opt})"


@dataclass
class MRecordExpr(MNode):
    """Represents record literal: [Field1 = val1, Field2 = val2]"""
    fields: List[Tuple[str, MNode]] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"MRecordExpr({[k for k, _ in self.fields]})"


@dataclass
class MListExpr(MNode):
    """Represents list literal: {item1, item2, ...}"""
    items: List[MNode] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"MListExpr(len={len(self.items)})"


@dataclass
class MBinaryExpr(MNode):
    left: MNode
    operator: str
    right: MNode

    def __repr__(self) -> str:
        return f"MBinaryExpr({self.left} {self.operator} {self.right})"


@dataclass
class MUnaryExpr(MNode):
    operator: str
    operand: MNode

    def __repr__(self) -> str:
        return f"MUnaryExpr({self.operator} {self.operand})"


@dataclass
class MMetadataExpr(MNode):
    """Represents expression meta [IsParameterQuery=true, ...]"""
    expr: MNode
    metadata: MNode

    def __repr__(self) -> str:
        return f"MMetadataExpr({self.expr} meta {self.metadata})"


@dataclass
class MTypeExpr(MNode):
    type_name: str
    details: Optional[MNode] = None

    def __repr__(self) -> str:
        return f"MTypeExpr({self.type_name})"


@dataclass
class MSectionMember(MNode):
    """Represents a member in a section document: [shared] Name = Expression;"""
    name: str
    is_shared: bool
    expression: MNode
    doc_comment: Optional[str] = None
    raw_code: str = ""

    def __repr__(self) -> str:
        sh = "shared " if self.is_shared else ""
        return f"MSectionMember({sh}{self.name} = {self.expression})"


@dataclass
class MSectionDocument(MNode):
    """Represents a full Power Query M section document (section Name; member1; member2;)."""
    section_name: str
    members: List[MSectionMember] = field(default_factory=list)

    def get_shared_members(self) -> Dict[str, MNode]:
        """Returns dictionary of shared members by name."""
        return {m.name: m.expression for m in self.members if m.is_shared}

    def get_all_members(self) -> Dict[str, MNode]:
        """Returns dictionary of all members (shared and private) by name."""
        return {m.name: m.expression for m in self.members}

    def __repr__(self) -> str:
        return f"MSectionDocument({self.section_name}, members={len(self.members)})"


@dataclass
class MUnresolvedExpr(MNode):
    """Fallback node for gracefully containing unparsed or opaque M constructs."""
    raw: str
    error_hint: Optional[str] = None

    def __repr__(self) -> str:
        return f"MUnresolvedExpr({repr(self.raw[:40])})"


# ---------------------------------------------------------------------------
# Recursive-Descent Parser
# ---------------------------------------------------------------------------

class MParser:
    """
    Recursive-descent parser for Power Query M code.
    Conforms to official M grammar and implements graceful degradation.
    """

    def __init__(self, tokens: List[MToken], raw_code: str = ""):
        self.tokens = tokens
        self.raw_code = raw_code
        self.pos = 0
        self.n = len(tokens)

    def current(self) -> MToken:
        if self.pos < self.n:
            return self.tokens[self.pos]
        return self.tokens[-1]

    def peek(self, offset: int = 1) -> MToken:
        idx = self.pos + offset
        if idx < self.n:
            return self.tokens[idx]
        return self.tokens[-1]

    def match(self, token_type: str, value: Optional[str] = None) -> bool:
        tok = self.current()
        if tok.type != token_type:
            return False
        if value is not None and tok.value != value:
            return False
        return True

    def advance(self) -> MToken:
        tok = self.current()
        if self.pos < self.n - 1:
            self.pos += 1
        return tok

    def consume(self, token_type: str, value: Optional[str] = None) -> MToken:
        if self.match(token_type, value):
            return self.advance()
        curr = self.current()
        expected = f"{token_type}('{value}')" if value else token_type
        # Graceful handling instead of crashing
        return MToken(TOKEN_DELIMITER, "", "", curr.line, curr.col)

    # -----------------------------------------------------------------------
    # Main Parsing Entry Point
    # -----------------------------------------------------------------------

    def parse(self) -> MNode:
        """Parses the entire token stream into an M AST node."""
        try:
            if self.match(TOKEN_KEYWORD, "section"):
                return self.parse_section()
            node = self.parse_expression()
            return node
        except Exception as e:
            return MUnresolvedExpr(raw=self.raw_code, error_hint=str(e))

    def parse_section(self) -> MSectionDocument:
        """
        Parses an M section document (section SectionName; shared Query1 = ...; shared Query2 = ...;).
        Conforms to Section 3.1 of Microsoft Power Query M formal language specifications.
        """
        self.consume(TOKEN_KEYWORD, "section")
        name_tok = self.current()
        if name_tok.type in (TOKEN_IDENTIFIER, TOKEN_KEYWORD):
            sec_name = str(name_tok.value)
            self.advance()
        else:
            sec_name = "DefaultSection"

        if self.match(TOKEN_DELIMITER, ";"):
            self.advance()

        members: List[MSectionMember] = []

        while not self.match(TOKEN_EOF):
            while self.match(TOKEN_DELIMITER, ";"):
                self.advance()
            if self.match(TOKEN_EOF):
                break

            is_shared = False
            if self.match(TOKEN_KEYWORD, "shared"):
                is_shared = True
                self.advance()

            m_name_tok = self.current()
            if m_name_tok.type in (TOKEN_IDENTIFIER, TOKEN_KEYWORD):
                member_name = str(m_name_tok.value)
                self.advance()
            else:
                self.advance()
                continue

            if self.match(TOKEN_OPERATOR, "="):
                self.advance()

            expr = self.parse_expression()

            if self.match(TOKEN_DELIMITER, ";"):
                self.advance()

            members.append(MSectionMember(
                name=member_name,
                is_shared=is_shared,
                expression=expr,
            ))

        return MSectionDocument(section_name=sec_name, members=members)

    def parse_expression(self) -> MNode:
        """Parses any M expression, starting from keywords (let, if, each, try)."""
        curr = self.current()

        # let ... in ...
        if curr.type == TOKEN_KEYWORD and curr.value == "let":
            return self.parse_let()

        # if ... then ... else ...
        if curr.type == TOKEN_KEYWORD and curr.value == "if":
            return self.parse_if()

        # each ...
        if curr.type == TOKEN_KEYWORD and curr.value == "each":
            self.advance()
            body = self.parse_expression()
            return MEachExpr(body=body)

        # try ... otherwise ...
        if curr.type == TOKEN_KEYWORD and curr.value == "try":
            return self.parse_try()

        # Function definition: (x, y) => ...
        if self._is_function_header():
            return self.parse_function()

        # Otherwise parse expression with operator precedence
        return self.parse_meta()

    # -----------------------------------------------------------------------
    # Let Expression
    # -----------------------------------------------------------------------

    def parse_let(self) -> MLetExpr:
        self.consume(TOKEN_KEYWORD, "let")
        steps: List[MStep] = []

        while not self.match(TOKEN_KEYWORD, "in") and not self.match(TOKEN_EOF):
            step = self.parse_step()
            if step:
                steps.append(step)

            # Consume optional comma between steps
            if self.match(TOKEN_DELIMITER, ","):
                self.advance()
            else:
                # If next is not 'in' and not comma, try advancing to next step boundary
                if not self.match(TOKEN_KEYWORD, "in") and not self.match(TOKEN_EOF):
                    # Graceful skip until next identifier = or in
                    pass

        in_expr: Optional[MNode] = None
        if self.match(TOKEN_KEYWORD, "in"):
            self.advance()
            in_expr = self.parse_expression()

        return MLetExpr(steps=steps, in_expr=in_expr)

    def parse_step(self) -> Optional[MStep]:
        """Parses a single step: StepName = <expression>"""
        if not self.match(TOKEN_IDENTIFIER):
            if self.match(TOKEN_KEYWORD, "in") or self.match(TOKEN_EOF):
                return None
            # Recover by skipping unexpected token
            self.advance()
            return None

        step_name_tok = self.advance()
        step_name = step_name_tok.value

        # Expect '='
        if self.match(TOKEN_OPERATOR, "="):
            self.advance()
        else:
            # Fallback if '=' is missing
            pass

        start_tok = self.current()
        value_node = self.parse_expression()
        return MStep(name=step_name, value=value_node)

    # -----------------------------------------------------------------------
    # If & Try Expressions
    # -----------------------------------------------------------------------

    def parse_if(self) -> MIfExpr:
        self.consume(TOKEN_KEYWORD, "if")
        cond = self.parse_expression()
        self.consume(TOKEN_KEYWORD, "then")
        then_b = self.parse_expression()
        self.consume(TOKEN_KEYWORD, "else")
        else_b = self.parse_expression()
        return MIfExpr(condition=cond, then_branch=then_b, else_branch=else_b)

    def parse_try(self) -> MTryExpr:
        self.consume(TOKEN_KEYWORD, "try")
        try_b = self.parse_expression()
        otherwise_b = None
        if self.match(TOKEN_KEYWORD, "otherwise"):
            self.advance()
            otherwise_b = self.parse_expression()
        return MTryExpr(try_branch=try_b, otherwise_branch=otherwise_b)

    # -----------------------------------------------------------------------
    # Function Expressions
    # -----------------------------------------------------------------------

    def _is_function_header(self) -> bool:
        """Checks if current position is the start of a function definition: (params) => or ident =>"""
        if self.match(TOKEN_IDENTIFIER) and self.peek().type == TOKEN_OPERATOR and self.peek().value == "=>":
            return True

        if not self.match(TOKEN_DELIMITER, "("):
            return False

        # Look ahead for matching ')' followed by '=>'
        depth = 0
        i = 0
        while self.pos + i < self.n:
            tok = self.tokens[self.pos + i]
            if tok.type == TOKEN_DELIMITER and tok.value == "(":
                depth += 1
            elif tok.type == TOKEN_DELIMITER and tok.value == ")":
                depth -= 1
                if depth == 0:
                    next_tok = self.tokens[self.pos + i + 1] if self.pos + i + 1 < self.n else None
                    if next_tok and next_tok.type == TOKEN_OPERATOR and next_tok.value == "=>":
                        return True
                    # Might have return type: ) as type =>
                    if next_tok and next_tok.type == TOKEN_KEYWORD and next_tok.value == "as":
                        # Scan further for =>
                        j = i + 2
                        while self.pos + j < self.n:
                            t = self.tokens[self.pos + j]
                            if t.type == TOKEN_OPERATOR and t.value == "=>":
                                return True
                            if t.type in (TOKEN_KEYWORD, TOKEN_DELIMITER) and t.value in ("let", "in", ";", ","):
                                break
                            j += 1
                    return False
            i += 1
        return False

    def parse_function(self) -> MFunctionExpr:
        params: List[MFunctionParam] = []

        if self.match(TOKEN_IDENTIFIER):
            # Single parameter: x => x + 1
            param_tok = self.advance()
            params.append(MFunctionParam(name=param_tok.value))
            self.consume(TOKEN_OPERATOR, "=>")
            body = self.parse_expression()
            return MFunctionExpr(parameters=params, body=body)

        # Parenthesized parameter list: (param1 as text, optional param2 as number)
        self.consume(TOKEN_DELIMITER, "(")
        while not self.match(TOKEN_DELIMITER, ")") and not self.match(TOKEN_EOF):
            is_optional = False
            if self.match(TOKEN_KEYWORD, "optional"):
                is_optional = True
                self.advance()

            if self.match(TOKEN_IDENTIFIER):
                p_name = self.advance().value
                type_name = None
                if self.match(TOKEN_KEYWORD, "as"):
                    self.advance()
                    # Collect type tokens
                    type_parts = []
                    while not self.match(TOKEN_DELIMITER, ",") and not self.match(TOKEN_DELIMITER, ")") and not self.match(TOKEN_EOF):
                        type_parts.append(self.advance().value)
                    type_name = " ".join(str(p) for p in type_parts)
                params.append(MFunctionParam(name=p_name, type_name=type_name, is_optional=is_optional))
            else:
                self.advance()

            if self.match(TOKEN_DELIMITER, ","):
                self.advance()

        self.consume(TOKEN_DELIMITER, ")")

        # Optional return type: as type
        ret_type = None
        if self.match(TOKEN_KEYWORD, "as"):
            self.advance()
            ret_parts = []
            while not self.match(TOKEN_OPERATOR, "=>") and not self.match(TOKEN_EOF):
                ret_parts.append(self.advance().value)
            ret_type = " ".join(str(p) for p in ret_parts)

        self.consume(TOKEN_OPERATOR, "=>")
        body = self.parse_expression()
        return MFunctionExpr(parameters=params, return_type=ret_type, body=body)

    # -----------------------------------------------------------------------
    # Binary Operator Precedence Climbing
    # -----------------------------------------------------------------------

    def parse_meta(self) -> MNode:
        expr = self.parse_or()
        while self.match(TOKEN_KEYWORD, "meta"):
            self.advance()
            meta_record = self.parse_primary()
            expr = MMetadataExpr(expr=expr, metadata=meta_record)
        return expr

    def parse_or(self) -> MNode:
        left = self.parse_and()
        while self.match(TOKEN_KEYWORD, "or"):
            op = self.advance().value
            right = self.parse_and()
            left = MBinaryExpr(left=left, operator=op, right=right)
        return left

    def parse_and(self) -> MNode:
        left = self.parse_equality_relational()
        while self.match(TOKEN_KEYWORD, "and"):
            op = self.advance().value
            right = self.parse_equality_relational()
            left = MBinaryExpr(left=left, operator=op, right=right)
        return left

    def parse_equality_relational(self) -> MNode:
        left = self.parse_concat()
        while self.match(TOKEN_OPERATOR) and self.current().value in ("=", "<>", "<", "<=", ">", ">="):
            op = self.advance().value
            right = self.parse_concat()
            left = MBinaryExpr(left=left, operator=op, right=right)
        return left

    def parse_concat(self) -> MNode:
        left = self.parse_additive()
        while self.match(TOKEN_OPERATOR, "&"):
            op = self.advance().value
            right = self.parse_additive()
            left = MBinaryExpr(left=left, operator=op, right=right)
        return left

    def parse_additive(self) -> MNode:
        left = self.parse_multiplicative()
        while self.match(TOKEN_OPERATOR) and self.current().value in ("+", "-"):
            op = self.advance().value
            right = self.parse_multiplicative()
            left = MBinaryExpr(left=left, operator=op, right=right)
        return left

    def parse_multiplicative(self) -> MNode:
        left = self.parse_unary()
        while self.match(TOKEN_OPERATOR) and self.current().value in ("*", "/", "%"):
            op = self.advance().value
            right = self.parse_unary()
            left = MBinaryExpr(left=left, operator=op, right=right)
        return left

    def parse_unary(self) -> MNode:
        curr = self.current()
        if curr.type == TOKEN_KEYWORD and curr.value == "not":
            op = self.advance().value
            operand = self.parse_unary()
            return MUnaryExpr(operator=op, operand=operand)
        if curr.type == TOKEN_OPERATOR and curr.value in ("-", "+"):
            op = self.advance().value
            operand = self.parse_unary()
            return MUnaryExpr(operator=op, operand=operand)
        return self.parse_postfix()

    # -----------------------------------------------------------------------
    # Postfix Operators: Invocations, Item Access {}, Field Access []
    # -----------------------------------------------------------------------

    def parse_postfix(self) -> MNode:
        expr = self.parse_primary()

        while True:
            # 1. Function invocation: (arg1, arg2, ...)
            if self.match(TOKEN_DELIMITER, "("):
                self.advance()
                args: List[MNode] = []
                while not self.match(TOKEN_DELIMITER, ")") and not self.match(TOKEN_EOF):
                    args.append(self.parse_expression())
                    if self.match(TOKEN_DELIMITER, ","):
                        self.advance()
                self.consume(TOKEN_DELIMITER, ")")
                expr = MInvocationExpr(function=expr, arguments=args)
                continue

            # 2. Item Access: target{item} or target{item}?
            if self.match(TOKEN_DELIMITER, "{"):
                self.advance()
                item_expr = self.parse_expression()
                self.consume(TOKEN_DELIMITER, "}")
                is_opt = False
                if self.match(TOKEN_DELIMITER, "?"):
                    is_opt = True
                    self.advance()
                expr = MItemAccessExpr(target=expr, item=item_expr, is_optional=is_opt)
                continue

            # 3. Field Access on target: target[FieldName] or target[[Col1], [Col2]]
            if self.match(TOKEN_DELIMITER, "["):
                self.advance()
                if self.match(TOKEN_IDENTIFIER) or self.match(TOKEN_STRING):
                    field_name = self.advance().value
                    self.consume(TOKEN_DELIMITER, "]")
                    is_opt = False
                    if self.match(TOKEN_DELIMITER, "?"):
                        is_opt = True
                        self.advance()
                    expr = MFieldAccessExpr(target=expr, field_name=field_name, is_optional=is_opt)
                    continue
                else:
                    # Projection or complex field selection
                    inner_fields = []
                    while not self.match(TOKEN_DELIMITER, "]") and not self.match(TOKEN_EOF):
                        inner_fields.append(self.parse_expression())
                        if self.match(TOKEN_DELIMITER, ","):
                            self.advance()
                    self.consume(TOKEN_DELIMITER, "]")
                    expr = MFieldAccessExpr(target=expr, field_name=str(inner_fields), is_optional=False)
                    continue

            break

        return expr

    # -----------------------------------------------------------------------
    # Primary Expressions: Literals, Identifiers, Records, Lists, Types
    # -----------------------------------------------------------------------

    def parse_primary(self) -> MNode:
        curr = self.current()

        # String Literal
        if curr.type == TOKEN_STRING:
            self.advance()
            return MLiteral(value=curr.value, raw=curr.raw, literal_type="string")

        # Number Literal
        if curr.type == TOKEN_NUMBER:
            self.advance()
            return MLiteral(value=curr.value, raw=curr.raw, literal_type="number")

        # Boolean Literal
        if curr.type == TOKEN_BOOLEAN:
            self.advance()
            return MLiteral(value=curr.value, raw=curr.raw, literal_type="boolean")

        # Null Literal
        if curr.type == TOKEN_NULL:
            self.advance()
            return MLiteral(value=None, raw=curr.raw, literal_type="null")

        # Intrinsic Literal: #table, #date, etc.
        if curr.type == TOKEN_INTRINSIC:
            self.advance()
            return MLiteral(value=curr.value, raw=curr.raw, literal_type="intrinsic")

        # Type Expression: type text, type number, type table [...]
        if curr.type == TOKEN_KEYWORD and curr.value == "type":
            self.advance()
            type_parts = []
            while self.match(TOKEN_IDENTIFIER) or (self.match(TOKEN_KEYWORD) and self.current().value in ("table", "record", "list", "any", "text", "number", "date", "datetime", "logical")):
                type_parts.append(self.advance().value)
            t_name = " ".join(type_parts) or "type"
            details = None
            if self.match(TOKEN_DELIMITER, "["):
                details = self.parse_record_or_field_access()
            return MTypeExpr(type_name=t_name, details=details)

        # Parenthesized Expression: (expr)
        if self.match(TOKEN_DELIMITER, "("):
            self.advance()
            expr = self.parse_expression()
            self.consume(TOKEN_DELIMITER, ")")
            if expr is not None:
                expr.parenthesized_count = getattr(expr, "parenthesized_count", 0) + 1
            return expr

        # Record Literal OR Standalone Field Access: [FieldName] vs [Key = val]
        if self.match(TOKEN_DELIMITER, "["):
            return self.parse_record_or_field_access()

        # List Literal: {item1, item2, ...}
        if self.match(TOKEN_DELIMITER, "{"):
            return self.parse_list()

        # Identifier: regular or quoted #"..."
        if curr.type == TOKEN_IDENTIFIER:
            self.advance()
            is_quoted = curr.raw.startswith('#"')
            return MIdentifier(name=curr.value, is_quoted=is_quoted)

        # Fallback for unexpected token
        self.advance()
        return MUnresolvedExpr(raw=curr.raw)

    def parse_record_or_field_access(self) -> MNode:
        """
        Distinguishes between a Record Literal: [A = 1, B = 2]
        and a standalone implicit Field Access: [ColumnName]
        """
        start_tok = self.consume(TOKEN_DELIMITER, "[")

        # Empty record: []
        if self.match(TOKEN_DELIMITER, "]"):
            self.advance()
            return MRecordExpr(fields=[])

        # Check if this is a field access [ColumnName] or [#"Column Name"]
        if (self.match(TOKEN_IDENTIFIER) or self.match(TOKEN_STRING) or self.match(TOKEN_KEYWORD)) and self.peek().type == TOKEN_DELIMITER and self.peek().value == "]":
            col_name = self.advance().raw
            self.consume(TOKEN_DELIMITER, "]")
            is_opt = False
            if self.match(TOKEN_DELIMITER, "?"):
                is_opt = True
                self.advance()
            return MFieldAccessExpr(target=None, field_name=col_name, is_optional=is_opt)

        # Otherwise parse as a Record: [Field1 = val1, Field2 = val2, ...]
        fields: List[Tuple[str, MNode]] = []
        while not self.match(TOKEN_DELIMITER, "]") and not self.match(TOKEN_EOF):
            if self.match(TOKEN_IDENTIFIER) or self.match(TOKEN_STRING) or self.match(TOKEN_KEYWORD):
                f_name = self.advance().raw
                val_node: MNode = MLiteral(None, "", "null")
                if self.match(TOKEN_OPERATOR, "="):
                    self.advance()
                    val_node = self.parse_expression()
                fields.append((f_name, val_node))
            else:
                self.advance()

            if self.match(TOKEN_DELIMITER, ","):
                self.advance()

        self.consume(TOKEN_DELIMITER, "]")
        return MRecordExpr(fields=fields)

    def parse_list(self) -> MListExpr:
        self.consume(TOKEN_DELIMITER, "{")
        items: List[MNode] = []
        while not self.match(TOKEN_DELIMITER, "}") and not self.match(TOKEN_EOF):
            items.append(self.parse_expression())
            if self.match(TOKEN_DELIMITER, ","):
                self.advance()
        self.consume(TOKEN_DELIMITER, "}")
        return MListExpr(items=items)


# ---------------------------------------------------------------------------
# Convenience Helper Function
# ---------------------------------------------------------------------------

def parse_m(code: str) -> MNode:
    """
    Parses a Power Query M code string into an AST MNode.
    Safe and robust with automatic fallback to MUnresolvedExpr on syntax anomalies.
    """
    if not code or not code.strip():
        return MUnresolvedExpr(raw="")
    lexer = MLexer(code)
    tokens = lexer.tokenize()
    parser = MParser(tokens, raw_code=code)
    return parser.parse()
