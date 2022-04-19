import pytest

from tql import compile


@pytest.mark.parametrize("pattern", [
    "a > b",
    "a > b > c",
    "(a >)* > b",
    "a>*>b",
    "(a >>)* > b",
    "a>>*>b",
    "a.b#c",
    "a > b > {c : d}",
    "#c > d",
    "{{a > b > c}}",
    "{a : {b > c} : d}",
    "a > b >> c > d",
    "{a :: b : c}",
    "{a :: b:* : c}",
    "{a :: b::* : c}",
    "div.a.b.c.d",
    ".a",
    "#x2633",
    "$",
    "$ > a",
    "a > $",
    "{$: a}",
    "{a : $}",
    "{$ : $}",
    "a~(txt)",
    "a > b {@[txt]}",
    "x[node, txt]",
    "z[.data-x]",
    "a~(txt || .data)",
    "a~(txt && .data)",
    "a~(txt && .data || .x)",
    "a~($f1)",
    "a~($f1 || $f2 && $f3)",
    "div | a",
    "div | a > x > b | i",
    "(a > b) | (c > d) > x",
    "a?",
    "a > b? > c",
    "a | b?",
    "!.a",
    "div.a!.b",
    "div.a!(#c.b)",
    "div~(.a == 1)",
    "div~(.a == '1')",
    "div~(.a == '2' && .b == '5' || c != 'e')",
    r"div~(txt == '\na\nb\nc\n')",
    r"div~(txt == '\x20\u0020\0\z')",
    r"div~(.a ~~ '\d')",
])
def test_compiles(pattern):
    str(compile(pattern))


@pytest.mark.parametrize("pattern", [
    "a b",
    "(a > b) #c",
    "a : b : c",
    "{a > b > c}",
    "{a >> b}",
    "a :: b",
    "a ` b",
    ".a#c#d",
    "(a:)*",
    "{b>>*}",
    "a>~(x)",
    "a~()",
    "x[]",
    "a~(.)",
    "a~(x|)",
    "a~(x|z)",
    "a~(b&)",
    "a~(b&k)",
    "a |",
    "a ? b",
    "div[z]"
])
def test_not_compiles(pattern):
    with pytest.raises(RuntimeError):
        compile(pattern)
