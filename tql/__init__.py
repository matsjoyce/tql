from . import parser, ast

_lexer = parser.TQLLexer()
_parser = parser.TQLParser()


def compile(expr):
    comp = ast.Document(_parser.parse(_lexer.tokenize(expr)))
    comp.validate(ast.Mode.depth)
    return comp
