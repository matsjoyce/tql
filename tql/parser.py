# pylint: disable=function-redefined, unused-argument, undefined-variable, used-before-assignment

from collections.abc import Mapping, Sequence
import re
from typing import Any, NoReturn

from sly import Lexer, Parser  # type: ignore[import]

from . import ast

SINGLE_STRING_ESCAPES: Mapping[str, str] = {
    "\\": "\\",
    "'": "'",
    '"': '"',
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}


def replace(match: re.Match) -> str:
    txt = match.group(1)
    if txt in SINGLE_STRING_ESCAPES:
        return SINGLE_STRING_ESCAPES[txt]
    elif txt.isdigit():
        return chr(int(txt, 8))
    elif txt.startswith("u") or txt.startswith("U"):
        return chr(int(txt[1:], 16))
    elif txt.startswith("x"):
        return bytes([int(txt[1:], 16)]).decode("latin-1")
    return "\\" + txt


def decode_string(s: str) -> str:
    return re.sub(
        r"\\(u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8}|x[0-9A-Fa-f]{2}|[0-7]{1,3}|.)", replace, s
    )


class TQLLexer(Lexer):
    _: Any
    # fmt:off
    tokens = {
        NAME, NUMBER, STRING, LBRAK, RBRAK, LPAREN, RPAREN, LCURLY, RCURLY, PLUS, STAR,  # type: ignore[name-defined]
        DOUBLEGT, GT, DOUBLEBAR, BAR, DOLLAR, DOUBLECOLON, COLON, COMMA, DOUBLEAMPERSAND, AMPERSAND, AT, DOT,  # type: ignore[name-defined]
        HASH, DOUBLETILDE, EXMARKTILDE, TILDE, QMARK, EXMARK, DOUBLEEQ, EXMARKEQ  # type: ignore[name-defined]
    }
    # fmt: on
    NAME = r"[a-zA-Z][a-zA-Z0-9-]*"

    @_(r"[0-9]+")
    def NUMBER(self, t: Any) -> Any:
        t.value = int(t.value)
        return t

    @_(r"'([^']|\\.)*'")
    def STRING(self, t: Any) -> Any:
        t.value = decode_string(t.value[1:-1])
        return t

    LBRAK = r"\["
    RBRAK = r"\]"
    LPAREN = r"\("
    RPAREN = r"\)"
    LCURLY = r"\{"
    RCURLY = r"\}"
    PLUS = r"\+"
    STAR = r"\*"
    DOUBLEGT = r">>"
    GT = r">"
    DOUBLEBAR = r"\|\|"
    BAR = r"\|"
    DOLLAR = r"\$"
    DOUBLECOLON = r"::"
    COLON = r":"
    COMMA = r","
    DOUBLEAMPERSAND = r"&&"
    AMPERSAND = r"&"
    AT = "@"
    DOT = r"\."
    HASH = r"#"
    DOUBLETILDE = r"~~"
    EXMARKTILDE = r"\!~"
    TILDE = r"~"
    QMARK = r"\?"
    EXMARKEQ = r"\!="
    EXMARK = r"\!"
    DOUBLEEQ = r"=="

    ignore_newline = r"[ \t\n]+"

    # Extra action for newlines
    def ignore_newline(self, t: Any) -> None:
        self.lineno += t.value.count("\n")

    def error(self, t: Any) -> NoReturn:
        raise RuntimeError(f"Illegal character {t.value[0]!r}")


class TQLParser(Parser):
    _: Any
    # debugfile = "parser.out"
    tokens = TQLLexer.tokens
    precedence = (
        ("right", EXMARK),  # type: ignore[name-defined]
        ("left", TAGS),  # type: ignore[name-defined]
        ("left", BREADTH_OP, DEPTH_OP),  # type: ignore[name-defined]
        ("left", BAR),  # type: ignore[name-defined]
        ("left", DOUBLEBAR),  # type: ignore[name-defined]
        ("left", DOUBLEAMPERSAND),  # type: ignore[name-defined]
        ("nonassoc", DOUBLEEQ, EXMARKEQ),  # type: ignore[name-defined]
        ("left", QMARK),  # type: ignore[name-defined]
    )

    start = "outerexpr"

    # Tag expressions

    @_("NAME")
    def tag(self, p: Any) -> ast.Tag:
        return ast.NameTag(p.NAME)

    @_("AT")
    def tag(self, p: Any) -> ast.Tag:
        return ast.NameTag(None)

    @_("DOT NAME")
    def tag(self, p: Any) -> ast.Tag:
        return ast.ClassTag(p.NAME)

    @_("HASH NAME")
    def tag(self, p: Any) -> ast.Tag:
        return ast.IdTag(p.NAME)

    @_("EXMARK tag %prec EXMARK")
    def tag(self, p: Any) -> ast.Tag:
        return ast.NotTag(p.tag)

    @_("tag")
    def outertag(self, p: Any) -> ast.Tag:
        return p.tag

    @_("outertag outertag %prec TAGS")
    def outertag(self, p: Any) -> ast.Tag:
        return ast.BothTag(p.outertag0, p.outertag1)

    @_("LPAREN outertag RPAREN %prec TAGS")
    def tag(self, p: Any) -> ast.Tag:
        return p.outertag

    @_("outertag %prec TAGS")
    def expr(self, p: Any) -> ast.Tag:
        return p.outertag

    # Extractor/filter/breadth expressions

    @_("expr LBRAK extractors RBRAK")
    def expr(self, p: Any) -> ast.Node:
        return ast.Extractors(p.expr, p.extractors)

    @_("expr TILDE LPAREN filter RPAREN")
    def expr(self, p: Any) -> ast.Node:
        return ast.Filter(p.expr, p.filter)

    @_("expr LCURLY outerexpr RCURLY")
    def expr(self, p: Any) -> ast.Node:
        return ast.ModeSwitch(p.expr, p.outerexpr)

    @_("LCURLY outerexpr RCURLY")
    def expr(self, p: Any) -> ast.Node:
        return ast.ModeSwitch(ast.NameTag(None), p.outerexpr)

    # Extractor expressions

    @_("NAME")
    def extractor(self, p: Any) -> ast.Extractor:
        return ast.Extractor(p.NAME)

    @_("DOT NAME")
    def extractor(self, p: Any) -> ast.Extractor:
        return ast.Extractor("." + p.NAME)

    @_("extractor")
    def extractors(self, p: Any) -> Sequence[ast.Extractor]:
        return [p.extractor]

    @_("extractors COMMA extractor")
    def extractors(self, p: Any) -> Sequence[ast.Extractor]:
        return p.extractors + [p.extractor]

    # Filter expressions

    @_("extractor")
    def filter(self, p: Any) -> ast.FilterExpr:
        return ast.ExtractorFilter(p.extractor)

    @_(
        "filter DOUBLEAMPERSAND filter",
        "filter DOUBLEBAR filter",
        "filter DOUBLEEQ filter",
        "filter EXMARKEQ filter",
        "filter DOUBLETILDE filter",
        "filter EXMARKTILDE filter",
    )
    def filter(self, p: Any) -> ast.FilterExpr:
        return ast.OpFilter(p.filter0, p[1], p.filter1)

    @_("STRING")
    def filter(self, p: Any) -> ast.FilterExpr:
        return ast.LiteralFilter(p.STRING)

    @_("NUMBER")
    def filter(self, p: Any) -> ast.FilterExpr:
        return ast.LiteralFilter(p.NUMBER)

    @_("LPAREN filter RPAREN")
    def filter(self, p: Any) -> ast.FilterExpr:
        return p.filter

    @_("DOLLAR NAME")
    def filter(self, p: Any) -> ast.FilterExpr:
        return ast.FuncFilter(p.NAME)

    # Special symbols

    @_("DOLLAR")
    def expr(self, p: Any) -> ast.Node:
        return ast.End()

    # Outer expressions

    @_("GT", "DOUBLEGT")
    def depth_op(self, p: Any) -> str:
        return p[0]

    @_("COLON", "DOUBLECOLON")
    def breadth_op(self, p: Any) -> str:
        return p[0]

    @_("PLUS", "STAR")
    def rep_op(self, p: Any) -> str:
        return p[0]

    @_("depth_op", "breadth_op")
    def trav_op(self, p: Any) -> str:
        return p[0]

    @_("expr")
    def outerexpr(self, p: Any) -> ast.Node:
        return p.expr

    @_("outerexpr BAR outerexpr")
    def outerexpr(self, p: Any) -> ast.Node:
        return ast.BinOp(p.outerexpr0, "|", p.outerexpr1)

    @_("outerexpr QMARK")
    def outerexpr(self, p: Any) -> ast.Node:
        return ast.MonOp(p.outerexpr, "?")

    @_("outerexpr breadth_op outerexpr %prec BREADTH_OP")
    def outerexpr(self, p: Any) -> ast.Node:
        return ast.TravOp(p.outerexpr0, p.breadth_op, p.outerexpr1)

    @_("outerexpr depth_op outerexpr %prec DEPTH_OP")
    def outerexpr(self, p: Any) -> ast.Node:
        return ast.TravOp(p.outerexpr0, p.depth_op, p.outerexpr1)

    @_("outerexpr trav_op rep_op")
    def expr(self, p: Any) -> ast.Node:
        return ast.RepOp(p.outerexpr, p.trav_op, p.rep_op)

    @_("LPAREN outerexpr trav_op RPAREN rep_op")
    def expr(self, p: Any) -> ast.Node:
        return ast.RepOp(p.outerexpr, p.trav_op, p.rep_op)

    @_("LPAREN outerexpr RPAREN")
    def expr(self, p: Any) -> ast.Node:
        return p.outerexpr

    def error(self, token: Any) -> NoReturn:
        print(self.__dict__)
        raise RuntimeError(f"Invalid syntax {token}")
