import dataclasses
import abc
import bs4
import typing
import enum
import collections
import re


class Mode(enum.Enum):
    depth = 0
    breadth = 1

    @property
    def opposite(self):
        if self is self.depth:
            return self.breadth
        return self.depth


class TravSide(enum.Enum):
    left = 0
    right = 1


@dataclasses.dataclass
class GlobalData:
    filter_funcs: dict


class Match:
    def __init__(self, current, next, exts, trav_side, globaldata):
        self.current = current
        self.next = next
        self.exts = exts
        self.trav_side = trav_side
        self.globaldata = globaldata

    def progress(self, current, next, ext=(), trav_side=None):
        return type(self)(current, next, self.exts[:-1] + (self.exts[-1] + ext,) if ext else self.exts, trav_side or self.trav_side, self.globaldata)

    def subgroup(self, ignore=False):
        if ignore:
            return self
        return type(self)(self.current, self.next, self.exts + ((),), self.trav_side, self.globaldata)

    def degroup(self, ignore=False):
        if ignore:
            return self
        return type(self)(self.current, self.next, self.exts[:-2] + (self.exts[-2] + (self.exts[-1],),), self.trav_side, self.globaldata)

    def side(self, trav_side):
        return type(self)(self.current, self.next, self.exts, trav_side, self.globaldata)

    def __repr__(self):  # pragma: no cover
        return f"Match(current={repr(self.current)[:100]}, next={self.next!r}, exts={self.exts}, trav_side={self.trav_side})"

    def __eq__(self, other):
        return type(self) is type(other) and self.current is other.current and self.next is other.next and self.trav_side is other.trav_side and self.exts == other.exts

    def __hash__(self):
        return hash((type(self), self.current, self.next, self.exts, self.trav_side))


class Node(abc.ABC):
    def __str__(self):
        return "\n".join(self.pprint())

    def pprint(self, level=0):
        return ["    " * level + repr(self)] + [line for child in self.children for line in child.pprint(level=level + 1)]

    @property
    def children(self):
        return []

    def validate(self, mode):
        for child in self.children:
            child.validate(mode)
        self.mode = mode

    @property
    def has_extractors(self):
        return any(child.has_extractors for child in self.children)

    @abc.abstractmethod
    def full_match(self, match: Match) -> typing.List[Match]:  # pragma: no cover
        pass

    def start_match(self, node: bs4.Tag, **filterfuncs):
        seen = set()
        for match in self.full_match(Match(None, node, ((),), None, GlobalData(filterfuncs))):
            if match.exts[0] not in seen:
                seen.add(match.exts[0])
                yield match.exts[0]

    def match(self, node: bs4.Tag, **filterfuncs):
        for match in self.start_match(node, **filterfuncs):
            yield self.resolve_match(match)

    def resolve_match(self, obj):
        if type(obj) is ExtractorMatch:
            return obj.result()
        else:
            return tuple(self.resolve_match(so) for so in obj)


class Tag(Node):
    name: str
    classes: list
    id: str

    def full_match(self, match):
        if match.next is None or not self.tag_match(match.next):
            return
        if self.mode is Mode.depth:
            has_child = False
            for n in match.next.children:
                if isinstance(n, bs4.Tag):
                    has_child = True
                    yield match.progress(match.next, n)
            if not has_child:
                yield match.progress(match.next, None)
        else:
            for n in match.next.next_siblings:
                if isinstance(n, bs4.Tag):
                    yield match.progress(match.next, n)
                    return
            yield match.progress(match.next, None)

    @abc.abstractmethod
    def tag_match(self, node):  # pragma: no cover
        pass

    @property
    def has_name(self):
        return any(c.has_name for c in self.children)

    @property
    def has_id(self):
        return any(c.has_id for c in self.children)

    def validate(self, mode):
        super().validate(mode)
        for child in self.children:
            if not isinstance(child, Tag):  # pragma: no cover
                raise RuntimeError("Non-tag inside tag!")


@dataclasses.dataclass
class NameTag(Tag):
    name: str

    def tag_match(self, node):
        return not self.name or node.name == self.name

    @property
    def has_name(self):
        return self.name is not None


@dataclasses.dataclass
class ClassTag(Tag):
    klass: str

    def tag_match(self, node):
        return self.klass in node.get("class", [])


@dataclasses.dataclass
class IdTag(Tag):
    id: list

    def tag_match(self, node):
        return self.id == node.get("id")

    @property
    def has_id(self):
        return True


@dataclasses.dataclass
class BothTag(Tag):
    left: Tag
    right: Tag

    @property
    def children(self):
        return [self.left, self.right]

    def tag_match(self, node):
        return self.left.tag_match(node) and self.right.tag_match(node)

    def validate(self, mode):
        super().validate(mode)

        if self.right.has_name:
            raise RuntimeError("Tag name should be on the left")
        if self.left.has_id and self.right.has_id:
            raise RuntimeError("Cannot have two or more ids")


@dataclasses.dataclass
class NotTag(Tag):
    expr: Tag

    @property
    def children(self):
        return [self.expr]

    @property
    def has_name(self):
        return False

    @property
    def has_id(self):
        return False

    def tag_match(self, node):
        return not self.expr.tag_match(node)


@dataclasses.dataclass
class Extractors(Node):
    expr: Node
    extractors: list

    @property
    def children(self):
        return [self.expr]

    def validate(self, mode):
        super().validate(mode)
        for extractor in self.extractors:
            extractor.validate()

    def full_match(self, match):
        for smatch in self.expr.full_match(match):
            yield smatch.progress(smatch.current, smatch.next, tuple(ExtractorMatch(smatch.current, ext) for ext in self.extractors))

    @property
    def has_extractors(self):
        return bool(self.extractors) or super().has_extractors


class ExtractorMatch:
    def __init__(self, node, extractor):
        self.node = node
        self.extractor = extractor

    def result(self):
        return self.extractor.extract(self.node)

    def __eq__(self, other):
        return type(self) is type(other) and self.node is other.node and self.extractor is other.extractor

    def __hash__(self):
        return hash((type(self), self.node, id(self.extractor)))


@dataclasses.dataclass
class Extractor:
    type: str

    def validate(self):
        if self.type.startswith(".") or self.type in ("node", "txt"):
            return
        raise RuntimeError(f"{self.type} is not a valid extractor")

    def extract(self, node):
        if self.type == "node":
            return node
        elif self.type == "txt":
            return node.text
        elif self.type.startswith("."):
            return node.get(self.type[1:])
        else:  # pragma: no cover
            raise RuntimeError(f"Unknown extractor {self.type}")


@dataclasses.dataclass
class Filter(Node):
    expr: Node
    filter: object

    @property
    def children(self):
        return [self.expr]

    def full_match(self, match):
        for smatch in self.expr.full_match(match):
            if self.filter.value(smatch.current, smatch.globaldata):
                yield smatch


class FilterExpr(abc.ABC):
    @abc.abstractmethod
    def value(self, node, globaldata):  # pragma: no cover
        pass


@dataclasses.dataclass
class ExtractorFilter(FilterExpr):
    extractor: Extractor

    def value(self, node, globaldata):
        return self.extractor.extract(node)


@dataclasses.dataclass
class OpFilter(FilterExpr):
    left: FilterExpr
    op: str
    right: FilterExpr

    def value(self, node, globaldata):
        if self.op == "&&":
            return self.left.value(node, globaldata) and self.right.value(node, globaldata)
        elif self.op == "||":
            return self.left.value(node, globaldata) or self.right.value(node, globaldata)
        elif self.op == "==":
            return self.left.value(node, globaldata) == self.right.value(node, globaldata)
        elif self.op == "!=":
            return self.left.value(node, globaldata) != self.right.value(node, globaldata)
        elif self.op == "~~":
            r = re.compile(self.right.value(node, globaldata))
            return r.search(self.left.value(node, globaldata))
        elif self.op == "!~":
            r = re.compile(self.right.value(node, globaldata))
            return not r.search(self.left.value(node, globaldata))
        else:  # pragma: no cover
            raise RuntimeError(f"Unknown filter operator {self.op}")


@dataclasses.dataclass
class FuncFilter(FilterExpr):
    func: str

    def value(self, node, globaldata):
        return globaldata.filter_funcs[self.func](node)


@dataclasses.dataclass
class LiteralFilter(FilterExpr):
    val: str

    def value(self, node, globaldata):
        return self.val


def descend_by_op(node, op):
    if op == ">":
        yield node
    elif op == ">>":
        yield node
        if node is None:
            return
        for n in node.descendants:
            if isinstance(n, bs4.Tag):
                yield n
    elif op == ":":
        yield node
    elif op == "::":
        yield node
        if node is None:
            return
        for n in node.next_siblings:
            if isinstance(n, bs4.Tag):
                yield n
    else:  # pragma: no cover
        raise RuntimeError(f"Unknown trav operator {op}")


@dataclasses.dataclass
class TravOp(Node):
    left: Node
    op: str
    right: Node

    def __repr__(self):
        return self.op

    @property
    def children(self):
        return [self.left, self.right]

    def validate(self, mode):
        if self.op in (":", "::") and mode is not Mode.breadth or self.op in (">", ">>") and mode is not Mode.depth:
            raise RuntimeError(f"{self.op} used in {mode} mode")
        super().validate(mode)

    def full_match(self, match):
        for lmatch in self.left.full_match(match.side(TravSide.left)):
            for n in descend_by_op(lmatch.next, self.op):
                yield from self.right.full_match(lmatch.progress(lmatch.current, n).side(TravSide.right))


@dataclasses.dataclass
class RepOp(Node):
    expr: Node
    trav_op: str
    rep_op: str

    @property
    def children(self):
        return [self.expr]

    def validate(self, mode):
        if self.trav_op in (":", "::") and mode is not Mode.breadth or self.trav_op in (">", ">>") and mode is not Mode.depth:
            raise RuntimeError(f"{self.trav_op} used in {mode} mode")
        super().validate(mode)

    def full_match(self, match):
        ignore = not self.has_extractors
        match = match.subgroup(ignore=ignore)
        if self.rep_op == "*":
            yield match.degroup(ignore=ignore)
        stack = collections.deque([match])
        seen = {match}
        while stack:
            match = stack.popleft()
            for smatch in self.expr.full_match(match.subgroup(ignore=ignore)):
                smatch = smatch.degroup(ignore=ignore)
                if smatch not in seen:
                    yield smatch.degroup(ignore=ignore)
                    for subnode in descend_by_op(smatch.next, self.trav_op):
                        ssmatch = smatch.progress(smatch.current, subnode)
                        if ssmatch not in seen:
                            stack.append(ssmatch)
                    seen.add(smatch)


@dataclasses.dataclass
class MonOp(Node):
    expr: Node
    op: str

    def __repr__(self):
        return self.op

    @property
    def children(self):
        return [self.expr]

    def full_match(self, match):
        if self.op == "?":
            yield match
            yield from self.expr.full_match(match)
        else:  # pragma: no cover
            raise RuntimeError(f"Unknown tag operator {self.op}")


@dataclasses.dataclass
class BinOp(Node):
    left: Node
    op: str
    right: Node

    def __repr__(self):
        return self.op

    @property
    def children(self):
        return [self.left, self.right]

    def full_match(self, match):
        if self.op == "|":
            yield from self.left.full_match(match)
            yield from self.right.full_match(match)
        else:  # pragma: no cover
            raise RuntimeError(f"Unknown tag operator {self.op}")


@dataclasses.dataclass
class ModeSwitch(Node):
    tag_expr: Node
    child_expr: Node

    @property
    def children(self):
        return [self.tag_expr, self.child_expr]

    def full_match(self, match):
        if self.outer_mode == Mode.depth:
            for smatch in self.tag_expr.full_match(match):
                yield from self.child_expr.full_match(smatch)
        else:
            for smatch in self.tag_expr.full_match(match):
                for subnode in descend_by_op(smatch.current, ">"):
                    for ssmatch in self.child_expr.full_match(smatch.progress(smatch.current, subnode)):
                        yield ssmatch.progress(ssmatch.current, smatch.next)

    def validate(self, mode):
        self.outer_mode = mode
        self.tag_expr.validate(mode)
        self.child_expr.validate(mode.opposite)


@dataclasses.dataclass
class End(Node):
    def full_match(self, match):
        if match.trav_side is TravSide.left:
            if match.next is None:
                yield match
            elif self.mode is Mode.breadth and not any(isinstance(t, bs4.Tag) for t in match.next.previous_siblings):
                yield match
            elif self.mode is Mode.depth and not isinstance(match.next.parent, bs4.Tag):
                yield match
        else:
            if match.next is None:
                yield match


@dataclasses.dataclass
class Document(Node):
    expr: Node

    @property
    def children(self):
        return [self.expr]

    def full_match(self, match):
        assert match.next.name == "[document]"
        for subnode in descend_by_op(match.next, ">>"):
            yield from self.expr.full_match(match.progress(match.next, subnode))
