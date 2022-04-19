from collections.abc import Iterable
import pathlib
from typing import Union

import bs4

from tql import ast, compile

TESTCASE = (pathlib.Path(__file__).parent / "testcase.html").read_text()


def get_test_doc() -> bs4.BeautifulSoup:
    return bs4.BeautifulSoup(TESTCASE, "html.parser")


def stringify_results(
    res: Union[Iterable[ast.Results], ast.Results]
) -> Union[str, list]:
    if isinstance(res, (str, bs4.Tag)):
        return str(res)
    try:
        return [stringify_results(x) for x in res]
    except ValueError:
        return str(res)


def test_just_tag() -> None:
    doc = get_test_doc()
    expr = compile("title[node]")
    assert stringify_results(expr.match(doc)) == [["<title>Page Title</title>"]]


def test_just_tag_and_text() -> None:
    doc = get_test_doc()
    expr = compile("title[node,txt]")
    assert stringify_results(expr.match(doc)) == [
        ["<title>Page Title</title>", "Page Title"]
    ]


def test_simple_direct_depth() -> None:
    doc = get_test_doc()
    expr = compile("body > p[node]")
    assert stringify_results(expr.match(doc)) == [
        ['<p class="a">My first paragraph.</p>']
    ]


def test_simple_direct_depth2() -> None:
    doc = get_test_doc()
    expr = compile("div > b[node]")
    assert len(stringify_results(expr.match(doc))) == 5


def test_any_tag() -> None:
    doc = get_test_doc()
    expr = compile("head > @[node]")
    assert stringify_results(expr.match(doc)) == [["<title>Page Title</title>"]]


def test_depth_root_left() -> None:
    doc = bs4.BeautifulSoup("<p><p></p></p>", "html.parser")
    expr = compile("$ > @[node]")
    assert stringify_results(expr.match(doc)) == [["<p><p></p></p>"]]


def test_depth_root_right() -> None:
    doc = bs4.BeautifulSoup("<p><p></p></p>", "html.parser")
    expr = compile("@[node] > $")
    assert stringify_results(expr.match(doc)) == [["<p></p>"]]


def test_simple_indirect_depth() -> None:
    doc = get_test_doc()
    expr = compile("body >> p[node]")
    assert len(stringify_results(expr.match(doc))) == 3


def test_simple_indirect_depth2() -> None:
    doc = get_test_doc()
    expr = compile("div >> a[node]")
    assert len(stringify_results(expr.match(doc))) == 5


def test_longer_direct_depth() -> None:
    doc = get_test_doc()
    expr = compile("body > div > p > div > p[node]")
    assert stringify_results(expr.match(doc)) == [["<p>hai</p>"]]


def test_plus_depth() -> None:
    doc = get_test_doc()
    expr = compile("body > (div > p[node] >)+")
    assert stringify_results(expr.match(doc)) == [
        [[["<p>\n<div>\n<p>hai</p>\n</div>\n</p>"]]],
        [[["<p>\n<div>\n<p>hai</p>\n</div>\n</p>"], ["<p>hai</p>"]]],
    ]


def test_plus_depth2() -> None:
    doc = get_test_doc()
    expr = compile("body > (i >)+ > b[node]")
    assert stringify_results(expr.match(doc)) == [["<b>12345</b>"]]


def test_simple_breadth() -> None:
    doc = get_test_doc()
    expr = compile("i > {b[node]}")
    assert stringify_results(expr.match(doc)) == [["<b>12345</b>"]]


def test_simple_direct_breadth() -> None:
    doc = get_test_doc()
    expr = compile("{b[node] : c[node]}")
    assert stringify_results(expr.match(doc)) == [["<b>2</b>", "<c>3</c>"]]


def test_simple_direct_breadth2() -> None:
    doc = get_test_doc()
    expr = compile("{a[node] : b[node] : c[node]}")
    assert stringify_results(expr.match(doc)) == [["<a>1</a>", "<b>2</b>", "<c>3</c>"]]


def test_simple_direct_breadth3() -> None:
    doc = get_test_doc()
    expr = compile("{i : div[node]}")
    assert stringify_results(expr.match(doc)) == [['<div class="a long">a</div>']]


def test_simple_direct_breadth4() -> None:
    doc = get_test_doc()
    expr = compile(".long {a[node]}")
    assert stringify_results(expr.match(doc)) == [["<a>1</a>"]]


def test_simple_indirect_breadth() -> None:
    doc = get_test_doc()
    expr = compile("{a[node] :: c[node]}")
    assert stringify_results(expr.match(doc)) == [
        ["<a>1</a>", "<c>3</c>"],
        ["<a>10</a>", "<c>11</c>"],
    ]


def test_simple_indirect_breadth2() -> None:
    doc = get_test_doc()
    expr = compile("{i :: div[node]}")
    assert len(stringify_results(expr.match(doc))) == 5


def test_star_breadth() -> None:
    doc = get_test_doc()
    expr = compile("{a : (b :)* : c[node]}")
    assert stringify_results(expr.match(doc)) == [["<c>3</c>"], ["<c>11</c>"]]


def test_star_breadth2() -> None:
    doc = get_test_doc()
    expr = compile("{i : ((div : div) :)* : div[txt]}")
    assert stringify_results(expr.match(doc)) == [
        ["a"],
        ["\n4pre\n4\n5\n6\n7\n8\n9\n"],
        ["b"],
    ]


def test_star_breadth3() -> None:
    doc = get_test_doc()
    expr = compile("{a : (b[node] :)* : c}")
    assert stringify_results(expr.match(doc)) == [[[["<b>2</b>"]]], [[]]]


def test_star_breadth4() -> None:
    doc = get_test_doc()
    expr = compile("{a : ((b:)* :)* : c[node]}")
    assert stringify_results(expr.match(doc)) == [["<c>3</c>"], ["<c>11</c>"]]


def test_plus_breadth() -> None:
    doc = get_test_doc()
    expr = compile("{a : (b :)+ : c[node]}")
    assert stringify_results(expr.match(doc)) == [["<c>3</c>"]]


def test_breadth_root_left() -> None:
    doc = get_test_doc()
    expr = compile("{$ : a[node]}")
    assert stringify_results(expr.match(doc)) == [["<a>1</a>"], ["<a>10</a>"]]


def test_breadth_root_right() -> None:
    doc = get_test_doc()
    expr = compile("{b[node] : $}")
    assert stringify_results(expr.match(doc)) == [["<b>12345</b>"], ["<b>9</b>"]]


def test_breadth_root_right2() -> None:
    doc = get_test_doc()
    expr = compile("{@ : b[node] : $}")
    assert stringify_results(expr.match(doc)) == [["<b>9</b>"]]


def test_depth_then_breadth() -> None:
    doc = get_test_doc()
    expr = compile("html > body > div {$ : a : b[node] : c : $}")
    assert stringify_results(expr.match(doc)) == [["<b>2</b>"]]


def test_breadth_then_depth() -> None:
    doc = get_test_doc()
    expr = compile("{div : {i > (i >)* > b[node]} : div}")
    assert stringify_results(expr.match(doc)) == [["<b>12345</b>"]]


def test_tag_or() -> None:
    doc = get_test_doc()
    expr = compile(".long > (a | c)[node]")
    assert stringify_results(expr.match(doc)) == [["<a>1</a>"], ["<c>3</c>"]]


def test_tag_opt() -> None:
    doc = get_test_doc()
    expr = compile("(ul > li?)[txt]")
    assert stringify_results(expr.match(doc)) == [
        ["\na1\nb2\nc3\n"],
        ["a1"],
        ["b2"],
        ["c3"],
    ]


def test_tag_opt2() -> None:
    doc = get_test_doc()
    expr = compile("body > div? > p[txt]")
    assert stringify_results(expr.match(doc)) == [
        ["My first paragraph."],
        ["\n\nhai\n\n"],
    ]


def test_filter_id() -> None:
    doc = get_test_doc()
    expr = compile("#h[node]")
    assert stringify_results(expr.match(doc)) == [['<h1 id="h">My First Heading</h1>']]


def test_filter_class() -> None:
    doc = get_test_doc()
    expr = compile(".a[node]")
    assert stringify_results(expr.match(doc)) == [
        ['<p class="a">My first paragraph.</p>'],
        ['<div class="a long">a</div>'],
    ]


def test_extractor_attr() -> None:
    doc = get_test_doc()
    expr = compile("li[.data-x]")
    assert stringify_results(expr.match(doc)) == [["1"], ["2"], ["3"]]


def test_filter_attr() -> None:
    doc = get_test_doc()
    expr = compile("@~(.data-x)[node]")
    assert stringify_results(expr.match(doc)) == [
        ['<li data-x="1">a1</li>'],
        ['<li data-x="2" data-y="hai">b2</li>'],
        ['<li data-x="3">c3</li>'],
    ]


def test_filter_not() -> None:
    doc = get_test_doc()
    expr = compile(".a!.long[node]")
    assert stringify_results(expr.match(doc)) == [
        ['<p class="a">My first paragraph.</p>']
    ]


def test_filter_not2() -> None:
    doc = get_test_doc()
    expr = compile("div.long!.a > !a!b[node]")
    assert stringify_results(expr.match(doc)) == [["<c>3</c>"]]


def test_filter_and() -> None:
    doc = get_test_doc()
    expr = compile("@~(.data-x && .data-y)[node]")
    assert stringify_results(expr.match(doc)) == [
        ['<li data-x="2" data-y="hai">b2</li>']
    ]


def test_filter_or() -> None:
    doc = get_test_doc()
    expr = compile("@~(.data-y || .id)[node]")
    assert stringify_results(expr.match(doc)) == [
        ['<h1 id="h">My First Heading</h1>'],
        ['<li data-x="2" data-y="hai">b2</li>'],
    ]


def test_filter_func() -> None:
    doc = get_test_doc()
    expr = compile("@~($f)[node]")
    res = expr.match(
        doc, f=lambda node: node.get("data-y") is not None or node.get("id") is not None
    )
    assert stringify_results(res) == [
        ['<h1 id="h">My First Heading</h1>'],
        ['<li data-x="2" data-y="hai">b2</li>'],
    ]


def test_filter_and_or() -> None:
    doc = get_test_doc()
    expr = compile("@~(.data-x && .data-y || .id)[node]")
    assert stringify_results(expr.match(doc)) == [
        ['<h1 id="h">My First Heading</h1>'],
        ['<li data-x="2" data-y="hai">b2</li>'],
    ]


def test_filter_or_and() -> None:
    doc = get_test_doc()
    expr = compile("@~(.data-x || .data-y && .id)[node]")
    assert stringify_results(expr.match(doc)) == [
        ['<li data-x="1">a1</li>'],
        ['<li data-x="2" data-y="hai">b2</li>'],
        ['<li data-x="3">c3</li>'],
    ]


def test_filter_or_and_paren() -> None:
    doc = get_test_doc()
    expr = compile("@~((.data-x || .id) && $f)[node]")
    res = expr.match(doc, f=lambda node: "a" in node.text)
    assert stringify_results(res) == [
        ['<h1 id="h">My First Heading</h1>'],
        ['<li data-x="1">a1</li>'],
    ]


def test_filter_eq() -> None:
    doc = get_test_doc()
    expr = compile(r"@~(txt == '4pre')[node]")
    assert stringify_results(expr.match(doc)) == [["<b>4pre</b>"]]


def test_filter_neq() -> None:
    doc = get_test_doc()
    expr = compile(r"c~(txt != '3')[node]")
    assert stringify_results(expr.match(doc)) == [["<c>11</c>"]]


def test_filter_regex() -> None:
    doc = get_test_doc()
    expr = compile(r"@~(txt ~~ '\d\d')[node] > $")
    assert stringify_results(expr.match(doc)) == [
        ["<b>12345</b>"],
        ["<a>10</a>"],
        ["<c>11</c>"],
    ]


def test_filter_nregex() -> None:
    doc = get_test_doc()
    expr = compile(r"c~(txt !~ '\d\d')[node]")
    assert stringify_results(expr.match(doc)) == [["<c>3</c>"]]
