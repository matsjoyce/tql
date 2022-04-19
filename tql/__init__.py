from . import ast, parser

_lexer = parser.TQLLexer()
_parser = parser.TQLParser()


def compile(expr: str) -> ast.Node:
    comp = ast.Document(_parser.parse(_lexer.tokenize(expr)))
    comp.validate(ast.Mode.DEPTH)
    return comp
