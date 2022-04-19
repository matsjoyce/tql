import abc
import collections
from collections.abc import Callable, Iterable, Mapping, Sequence
import dataclasses
import enum
import re
from typing import Any, Optional, TypeAlias, Union

import bs4


class Mode(enum.Enum):
    DEPTH = 0
    BREADTH = 1

    @property
    def opposite(self) -> "Mode":
        if self is self.DEPTH:
            return Mode(self.BREADTH)
        return Mode(self.DEPTH)


class TravSide(enum.Enum):
    LEFT = 0
    RIGHT = 1


FilterFunc: TypeAlias = Callable[[bs4.Tag], bool]
ExtractorResult: TypeAlias = Union[bs4.Tag, str]

# These types should be recursive
ExtractorMatches: TypeAlias = Union[tuple[Any, ...], "ExtractorMatch"]
Results: TypeAlias = Union[tuple[Any, ...], ExtractorResult]


@dataclasses.dataclass(frozen=True)
class GlobalData:
    filter_funcs: Mapping[str, FilterFunc]


class Match:
    def __init__(
        self,
        current: Optional[bs4.Tag],
        next: Optional[bs4.Tag],
        exts: tuple[tuple[ExtractorMatches, ...], ...],
        trav_side: Optional[TravSide],
        globaldata: GlobalData,
    ) -> None:
        self.current = current
        self.next = next
        self.exts = exts
        self.trav_side = trav_side
        self.globaldata = globaldata

    def progress(
        self,
        current: Optional[bs4.Tag],
        next: Optional[bs4.Tag],
        ext: Optional[tuple["ExtractorMatch", ...]] = None,
        trav_side: Optional[TravSide] = None,
    ) -> "Match":
        return Match(
            current,
            next,
            self.exts[:-1] + (self.exts[-1] + ext,) if ext is not None else self.exts,
            trav_side or self.trav_side,
            self.globaldata,
        )

    def subgroup(self, ignore: bool = False) -> "Match":
        if ignore:
            return self
        return Match(
            self.current, self.next, self.exts + ((),), self.trav_side, self.globaldata
        )

    def degroup(self, ignore: bool = False) -> "Match":
        if ignore:
            return self
        return Match(
            self.current,
            self.next,
            self.exts[:-2] + (self.exts[-2] + (self.exts[-1],),),
            self.trav_side,
            self.globaldata,
        )

    def side(self, trav_side: TravSide) -> "Match":
        return Match(self.current, self.next, self.exts, trav_side, self.globaldata)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Match(current={repr(self.current)[:100]}, next={self.next!r}, exts={self.exts}, trav_side={self.trav_side})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Match)
            and self.current is other.current
            and self.next is other.next
            and self.trav_side is other.trav_side
            and self.exts == other.exts
        )

    def __hash__(self) -> int:
        return hash((type(self), self.current, self.next, self.exts, self.trav_side))


@dataclasses.dataclass  # type: ignore[misc]
class Node(abc.ABC):
    def __post_init__(self) -> None:
        self.mode: Optional[Mode] = None

    def __str__(self) -> str:
        return "\n".join(self.pprint())

    def pprint(self, level: int = 0) -> Sequence[str]:
        return ["    " * level + repr(self)] + [
            line for child in self.children for line in child.pprint(level=level + 1)
        ]

    @property
    def children(self) -> Sequence["Node"]:
        return []

    def validate(self, mode: Mode) -> None:
        for child in self.children:
            child.validate(mode)
        self.mode = mode

    @property
    def has_extractors(self) -> bool:
        return any(child.has_extractors for child in self.children)

    @abc.abstractmethod
    def full_match(self, match: Match) -> Iterable[Match]:  # pragma: no cover
        pass

    def start_match(
        self, node: bs4.Tag, **filterfuncs: FilterFunc
    ) -> Iterable[ExtractorMatches]:
        seen = set()
        for match in self.full_match(
            Match(None, node, ((),), None, GlobalData(filterfuncs))
        ):
            if match.exts[0] not in seen:
                seen.add(match.exts[0])
                yield match.exts[0]

    def match(self, node: bs4.Tag, **filterfuncs: FilterFunc) -> Iterable[Results]:
        for match in self.start_match(node, **filterfuncs):
            yield self.resolve_match(match)

    def resolve_match(self, obj: ExtractorMatches) -> Results:
        if isinstance(obj, ExtractorMatch):
            return obj.result()
        else:
            return tuple(self.resolve_match(so) for so in obj)


class Tag(Node):
    @property
    def children(self) -> Sequence["Tag"]:
        return []

    def full_match(self, match: Match) -> Iterable[Match]:
        if match.next is None or not self.tag_match(match.next):
            return
        if self.mode is Mode.DEPTH:
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
    def tag_match(self, node: bs4.Tag) -> bool:  # pragma: no cover
        ...

    @property
    def has_name(self) -> bool:
        return any(c.has_name for c in self.children)

    @property
    def has_id(self) -> bool:
        return any(c.has_id for c in self.children)

    def validate(self, mode: Mode) -> None:
        super().validate(mode)
        for child in self.children:
            if not isinstance(child, Tag):  # pragma: no cover
                raise RuntimeError("Non-tag inside tag!")


@dataclasses.dataclass
class NameTag(Tag):
    name: str

    def tag_match(self, node: bs4.Tag) -> bool:
        return not self.name or node.name == self.name

    @property
    def has_name(self) -> bool:
        return self.name is not None


@dataclasses.dataclass
class ClassTag(Tag):
    klass: str

    def tag_match(self, node: bs4.Tag) -> bool:
        klasses = node.get("class", [])
        return isinstance(klasses, list) and self.klass in klasses


@dataclasses.dataclass
class IdTag(Tag):
    id: str

    def tag_match(self, node: bs4.Tag) -> bool:
        return self.id == node.get("id")

    @property
    def has_id(self) -> bool:
        return True


@dataclasses.dataclass
class BothTag(Tag):
    left: Tag
    right: Tag

    @property
    def children(self) -> Sequence[Tag]:
        return [self.left, self.right]

    def tag_match(self, node: bs4.Tag) -> bool:
        return self.left.tag_match(node) and self.right.tag_match(node)

    def validate(self, mode: Mode) -> None:
        super().validate(mode)

        if self.right.has_name:
            raise RuntimeError("Tag name should be on the left")
        if self.left.has_id and self.right.has_id:
            raise RuntimeError("Cannot have two or more ids")


@dataclasses.dataclass
class NotTag(Tag):
    expr: Tag

    @property
    def children(self) -> Sequence[Tag]:
        return [self.expr]

    @property
    def has_name(self) -> bool:
        return False

    @property
    def has_id(self) -> bool:
        return False

    def tag_match(self, node: bs4.Tag) -> bool:
        return not self.expr.tag_match(node)


@dataclasses.dataclass
class Extractors(Node):
    expr: Node
    extractors: Sequence["Extractor"]

    @property
    def children(self) -> Sequence[Node]:
        return [self.expr]

    def validate(self, mode: Mode) -> None:
        super().validate(mode)
        for extractor in self.extractors:
            extractor.validate()

    def full_match(self, match: Match) -> Iterable[Match]:
        for smatch in self.expr.full_match(match):
            assert (
                smatch.current is not None
            ), "Trying to extract when current node is None"
            yield smatch.progress(
                smatch.current,
                smatch.next,
                tuple(ExtractorMatch(smatch.current, ext) for ext in self.extractors),
            )

    @property
    def has_extractors(self) -> bool:
        return bool(self.extractors) or super().has_extractors


class ExtractorMatch:
    def __init__(self, node: bs4.Tag, extractor: "Extractor"):
        self.node = node
        self.extractor = extractor

    def result(self) -> ExtractorResult:
        return self.extractor.extract(self.node)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ExtractorMatch)
            and self.node is other.node
            and self.extractor is other.extractor
        )

    def __hash__(self) -> int:
        return hash((type(self), self.node, id(self.extractor)))


@dataclasses.dataclass
class Extractor:
    type: str

    def validate(self) -> None:
        if self.type.startswith(".") or self.type in ("node", "txt"):
            return
        raise RuntimeError(f"{self.type} is not a valid extractor")

    def extract(self, node: bs4.Tag) -> ExtractorResult:
        if self.type == "node":
            return node
        elif self.type == "txt":
            return node.text
        elif self.type.startswith("."):
            return str(node.get(self.type[1:], ""))
        else:  # pragma: no cover
            raise RuntimeError(f"Unknown extractor {self.type}")


@dataclasses.dataclass
class Filter(Node):
    expr: Node
    filter: "FilterExpr"

    @property
    def children(self) -> Sequence[Node]:
        return [self.expr]

    def full_match(self, match: Match) -> Iterable[Match]:
        for smatch in self.expr.full_match(match):
            assert (
                smatch.current is not None
            ), "Trying to filter when current node is None"
            if self.filter.value(smatch.current, smatch.globaldata):
                yield smatch


class FilterExpr(abc.ABC):
    @abc.abstractmethod
    def value(
        self, node: bs4.Tag, globaldata: GlobalData
    ) -> Union[ExtractorResult, bool]:  # pragma: no cover
        pass


@dataclasses.dataclass
class ExtractorFilter(FilterExpr):
    extractor: Extractor

    def value(self, node: bs4.Tag, globaldata: GlobalData) -> ExtractorResult:
        return self.extractor.extract(node)


@dataclasses.dataclass
class OpFilter(FilterExpr):
    left: FilterExpr
    op: str
    right: FilterExpr

    def value(self, node: bs4.Tag, globaldata: GlobalData) -> bool:
        if self.op == "&&":
            return bool(
                self.left.value(node, globaldata) and self.right.value(node, globaldata)
            )
        elif self.op == "||":
            return bool(
                self.left.value(node, globaldata) or self.right.value(node, globaldata)
            )
        elif self.op == "==":
            return self.left.value(node, globaldata) == self.right.value(
                node, globaldata
            )
        elif self.op == "!=":
            return self.left.value(node, globaldata) != self.right.value(
                node, globaldata
            )
        elif self.op == "~~":
            attr = self.left.value(node, globaldata)
            if not isinstance(attr, str):
                raise RuntimeError("LHS of ~~ must be a string")
            pattern = self.right.value(node, globaldata)
            if not isinstance(pattern, str):
                raise RuntimeError("RHS of ~~ must be a string")
            r = re.compile(pattern)
            return r.search(attr) is not None
        elif self.op == "!~":
            attr = self.left.value(node, globaldata)
            if not isinstance(attr, str):
                raise RuntimeError("LHS of ~~ must be a string")
            pattern = self.right.value(node, globaldata)
            if not isinstance(pattern, str):
                raise RuntimeError("RHS of ~~ must be a string")
            r = re.compile(pattern)
            return r.search(attr) is None
        else:  # pragma: no cover
            raise RuntimeError(f"Unknown filter operator {self.op}")


@dataclasses.dataclass
class FuncFilter(FilterExpr):
    func: str

    def value(self, node: bs4.Tag, globaldata: GlobalData) -> bool:
        return globaldata.filter_funcs[self.func](node)


@dataclasses.dataclass
class LiteralFilter(FilterExpr):
    val: str

    def value(self, node: bs4.Tag, globaldata: GlobalData) -> str:
        return self.val


def descend_by_op(node: Optional[bs4.Tag], op: str) -> Iterable[Optional[bs4.Tag]]:
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

    def __repr__(self) -> str:
        return self.op

    @property
    def children(self) -> Sequence[Node]:
        return [self.left, self.right]

    def validate(self, mode: Mode) -> None:
        if (
            self.op in (":", "::")
            and mode is not Mode.BREADTH
            or self.op in (">", ">>")
            and mode is not Mode.DEPTH
        ):
            raise RuntimeError(f"{self.op} used in {mode} mode")
        super().validate(mode)

    def full_match(self, match: Match) -> Iterable[Match]:
        for lmatch in self.left.full_match(match.side(TravSide.LEFT)):
            for n in descend_by_op(lmatch.next, self.op):
                yield from self.right.full_match(
                    lmatch.progress(lmatch.current, n).side(TravSide.RIGHT)
                )


@dataclasses.dataclass
class RepOp(Node):
    expr: Node
    trav_op: str
    rep_op: str

    @property
    def children(self) -> Sequence[Node]:
        return [self.expr]

    def validate(self, mode: Mode) -> None:
        if (
            self.trav_op in (":", "::")
            and mode is not Mode.BREADTH
            or self.trav_op in (">", ">>")
            and mode is not Mode.DEPTH
        ):
            raise RuntimeError(f"{self.trav_op} used in {mode} mode")
        super().validate(mode)

    def full_match(self, match: Match) -> Iterable[Match]:
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

    def __repr__(self) -> str:
        return self.op

    @property
    def children(self) -> Sequence[Node]:
        return [self.expr]

    def full_match(self, match: Match) -> Iterable[Match]:
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

    def __repr__(self) -> str:
        return self.op

    @property
    def children(self) -> Sequence[Node]:
        return [self.left, self.right]

    def full_match(self, match: Match) -> Iterable[Match]:
        if self.op == "|":
            yield from self.left.full_match(match)
            yield from self.right.full_match(match)
        else:  # pragma: no cover
            raise RuntimeError(f"Unknown tag operator {self.op}")


@dataclasses.dataclass
class ModeSwitch(Node):
    tag_expr: Node
    child_expr: Node

    def __post_init__(self) -> None:
        super().__post_init__()
        self.outer_mode: Optional[Mode] = None

    @property
    def children(self) -> Sequence[Node]:
        return [self.tag_expr, self.child_expr]

    def full_match(self, match: Match) -> Iterable[Match]:
        if self.outer_mode == Mode.DEPTH:
            for smatch in self.tag_expr.full_match(match):
                yield from self.child_expr.full_match(smatch)
        else:
            for smatch in self.tag_expr.full_match(match):
                for subnode in descend_by_op(smatch.current, ">"):
                    for ssmatch in self.child_expr.full_match(
                        smatch.progress(smatch.current, subnode)
                    ):
                        yield ssmatch.progress(ssmatch.current, smatch.next)

    def validate(self, mode: Mode) -> None:
        self.outer_mode = mode
        self.tag_expr.validate(mode)
        self.child_expr.validate(mode.opposite)


@dataclasses.dataclass
class End(Node):
    def full_match(self, match: Match) -> Iterable[Match]:
        if match.trav_side is TravSide.LEFT:
            if match.next is None:
                yield match
            elif self.mode is Mode.BREADTH and not any(
                isinstance(t, bs4.Tag) for t in match.next.previous_siblings
            ):
                yield match
            elif self.mode is Mode.DEPTH and not isinstance(match.next.parent, bs4.Tag):
                yield match
        else:
            if match.next is None:
                yield match


@dataclasses.dataclass
class Document(Node):
    expr: Node

    @property
    def children(self) -> Sequence[Node]:
        return [self.expr]

    def full_match(self, match: Match) -> Iterable[Match]:
        if match.next is not None and match.next.name != "[document]":
            raise RuntimeError("Matching should run on the complete document")
        for subnode in descend_by_op(match.next, ">>"):
            yield from self.expr.full_match(match.progress(match.next, subnode))
