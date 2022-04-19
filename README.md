# tql

A tree query language for HTML - think of a combination of regular expressions and CSS selectors, applied to tree structures.

## Usage

```py
import bs4
import tql

html = bs4.BeautifulSoup("<div id='find-me' data-attr='world'>hello</div>")
qry = tql.compile("div#find-me[txt, .data-attr]")
(text, data_attr), = qry.match(html)
print(text, data_attr) # Prints "hello world"
```

## API

 - `tql.compile(expr: str) -> tql.Node` - Returns the compiled query pattern
 - `tql.Node.match(html: bs4.BeautifulSoup, **filterfuncs: Callable[[bs4.Tag], bool]) -> Iterable[tuple]` - Performs a search over the provided HTML document and returns an iterator over the results. The results are tuples, and the contents of the tuple depends on the extractors used and the structure of the pattern. Extractors usually return strings, so most results are a tuple of strings. However, using repetition operators (like `*` and `+`) will result in a nested tuple structure. `filterfuncs` are the functions used in filters using the `$f` notation, calling `qry.match(..., my_func=lambda node: ...)` will result in `$my_func` calling that lambda.

## Query syntax

Terms used:
 - "tag" - A HTML element, like a `div` or `table`; "parent", "child", "neighbour", and "attribute" have the same meanings as in HTML

### The basics

 - `@` - Matches any tag
 - `div` - Matches a `div` tag
 - `.centered` - Matches a tag with the `centered` CSS class
 - `#root` - Matches a tag with the `root` id
 - `div.centered#root` - Matched a div tag with the `centered` CSS class and the `root` id

### Extracting data

 - `div[txt]` - Extract the text from a tag
 - `div[node]` - Extract the bs4 node for that tag
 - `div[.data-attr]` - Extract the value of the `data-attr` attribute

### Searching by depth

 - `div > a` - Matches a `div` with an `a` tag as a direct child
 - `div >> a` - Matches a `div` with an `a` tag as a direct or indirect child
 - `div > table >> li > a` - Matches an `a` that s a child of a `li` which is the descendent of a `table` that is a child of a `div`

### Searching by breadth

TQL can match "sideways" as well as downwards, similar to the CSS `:first-child` selectors. However, this syntax is much more powerful.

 - `{}` - Switch mode: All queries start in depth mode, and can be switched to breadth mode using curly braces; using curly braces in breadth mode, switches back to depth mode
 - `{ div : a }` - Match a `div` with an `a` as a direct neighbour
 - `{ div :: a }` - Match a `div` with an `a` as a direct or indirect neighbour (i.e. `div` then `a` OR `div` then some other tags then `a`)
 - `{ div : { li > a } }` - Match an `a` that is the direct child of a `li` that is the direct neighbour of a `div`
 - `div { div : div : div }` - Match a `div` tag with three `div` tags as children

### First and last child

 - `$ > @[txt]` - Extract the text from the root tag
 - `div[txt] > $` - Extract the text from a `div` tag with no children
 - `head { $ : @[txt] }` - Extract the first child of a `head` tag
 - `head { @[txt] : $ }` - Extract the last child of a `head` tag

### Repetition

 - `{ $ : (a :}* : $ }` - Match a tag which has zero or more `a` tags as its only children
 - `{ $ : (a : b :)* : $ }` - Match a tag which has zero or more `a` followed by `b` tags as its only children
 - `div > (span >)* > a` - Match an `a` tag which has a `div` ancestor and all (zero or more) parents that are descendants of that `div` tag are `span`s
 - `div > (span >)+ > a` - Match an `a` tag which has a `div` ancestor and all parents that are descendants of that `div` tag are `span`s and there must be at least one span parent

### Optional tags

 - `div > span? > a` - Match an `a` tag which either has a `span` parent which has a `div` parent, or a `div` parent

### Conjunction/disjunction/exclusion

 - `.a.b` - Match a tag that has both the `a` and `b` CSS class
 - `(.a | .b)` - Match a tag with the `a` or the `b` (or both) CSS class
 - `(a | b)` - Match an `a` or `b` tag
 - `div > (span | table > tbody) > a` - Match an `a` tag that either has a `span` parent with `div` parent, or a `tbody` parent with a `table` parent with a `div` parent
 - `div!.a` - Match a `div` tag that does not has the `a` CSS class

### Filters

 - `div~(.data-x)` - Match a `div` tag with a `data-x` attribute that is non-empty
 - `div~(.data-x == 'hello')` - Match a `div` tag with a `data-x` attribute that equals `"hello"`
 - `div~(.data-x != 'hello')` - Match a `div` tag with a `data-x` attribute that does not equal `"hello"`
 - `div~(.data-x ~~ 'hello')` - Match a `div` tag with a `data-x` attribute that matches `"hello"` (this is done using a regex search)
 - `div~(.data-x !~ 'hello')` - Match a `div` tag with a `data-x` attribute that does not match `"hello"` (this is done using a regex search)
 - `div~(.data-x && .data-y)` - Match a `div` tag with a `data-x` and `data-y` attribute, both of which are non-empty
 - `div~(.data-x || .data-y)` - Match a `div` tag with either a `data-x` or `data-y` (or both) attribute that is non-empty
 - `div~(.data-x && $my_func)` - Match a `div` tag with a `data-x` attribute that is non-empty and for which the filter function `my_func` returns a truthy value


Phew, that's a lot of stuff! Check out the tests for verified examples. Also, try experimenting. Just like regular expressions, seeing the results is much more intuitive than reading descriptions of the operators.
