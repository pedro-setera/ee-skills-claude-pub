"""KiCad S-expression reader and writer (schematics, boards, symbol and footprint libraries, netlists, rule files).

Why it exists
    Scripts that change a KiCad file by re-writing the whole file reformat it: every number, every line break and
    every quoting choice of the original is replaced by the script's own. The file still loads, but a diff shows
    thousands of changed lines, checksums of frozen files stop meaning anything, and a rounding difference can move
    a pad by a nanometre. So this module offers two ways to work, and the second one never touches what it was not
    asked to touch.

1. Whole-file model, for files a script generates itself (a schematic written from code, a netlist that is only read):

       tree = parse(text)             nested Python lists; a quoted token is a Q (a str subclass), a bare token a str
       find(tree, "net")              direct children whose head is "net"
       first(tree, "nets")            the first such child, or None
       walk(tree, "pin")              every descendant whose head is "pin"
       text = dump(tree)              one canonical layout

   Numbers are never converted: "1.27" is read and written as the token "1.27".

2. Edit-in-place model, for files that somebody else wrote (a board, a library, a hand-drawn schematic):

       doc = Document.load(path)      or Document(text)
       fp  = doc.find_all("footprint")[0]
       doc.set(first(fp, "at"), 1, "12.5")           change one token
       doc.replace(first(fp, "layer"), ["layer", Q("B.Cu")])
       doc.remove(node); doc.append(parent, new); doc.insert_after(sibling, new); doc.insert_before(sibling, new)
       new_text = doc.text()          the original text with only those edits applied

   Every byte outside the edited nodes is the byte of the original (line ends included: load() does not translate
   them). Write the result with kicad_io.atomic_write(). After text() parse again before further edits.

Works on any KiCad file, whoever made it. No project settings are read (no board.toml keys). Not a command-line
tool; `python -I sexp.py --self-test` runs a short round-trip check and exits 0 on success, 1 on a failed check.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import re
import sys

__all__ = ["Q", "SexpError", "parse", "dump", "find", "first", "value", "walk", "Document", "Node"]


class SexpError(ValueError):
    """The text is not a complete S-expression (unbalanced parenthesis, unterminated string)."""


class Q(str):
    """A quoted string token (KiCad's "..."). A plain str is a bare token (a keyword or a number)."""


# white space | ( | ) | "quoted" | bare token
_TOKEN = re.compile(r'[ \t\r\n]+|(\()|(\))|"((?:[^"\\]|\\.)*)"|([^ \t\r\n()"]+)', re.S)
_ESC = re.compile(r"\\(x[0-9A-Fa-f]{1,2}|[0-7]{1,3}|.)", re.S)
_UNESC = {"n": "\n", "r": "\r", "t": "\t", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}


def _unescape(raw: str) -> str:
    if "\\" not in raw:
        return raw

    def rep(m):
        s = m.group(1)
        if s in _UNESC:
            return _UNESC[s]
        if s[0] == "x" and len(s) > 1:
            return chr(int(s[1:], 16))
        if s[0] in "01234567":
            return chr(int(s, 8))
        return s                      # \" \\ and any other escaped character stand for themselves

    return _ESC.sub(rep, raw)


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r") + '"'


def _where(text: str, pos: int) -> str:
    line = text.count("\n", 0, pos) + 1
    col = pos - (text.rfind("\n", 0, pos) + 1) + 1
    return f"line {line}, column {col}"


def parse(text: str) -> list:
    """The text as nested lists. One top-level expression gives that list; several give a list of them."""
    stack: list[list] = [[]]
    pos = 0
    for m in _TOKEN.finditer(text):
        if m.start() != pos:
            raise SexpError(f"unreadable text at {_where(text, pos)} (an unterminated string?)")
        pos = m.end()
        k = m.lastindex
        if k is None:
            continue
        if k == 1:
            stack.append([])
        elif k == 2:
            if len(stack) == 1:
                raise SexpError(f"')' without '(' at {_where(text, m.start())}")
            top = stack.pop()
            stack[-1].append(top)
        elif k == 3:
            stack[-1].append(Q(_unescape(m.group(3))))
        else:
            stack[-1].append(m.group(4))
    if pos != len(text):
        raise SexpError(f"unreadable text at {_where(text, pos)} (an unterminated string?)")
    if len(stack) != 1:
        raise SexpError(f"{len(stack) - 1} '(' not closed at the end of the text")
    return stack[0][0] if len(stack[0]) == 1 and isinstance(stack[0][0], list) else stack[0]


def _atom(x) -> str:
    if isinstance(x, Q):
        return _quote(x)
    if isinstance(x, str):
        return x
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        s = f"{x:.6f}".rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    raise TypeError(f"cannot write {type(x).__name__} as an S-expression token")


def dump(node, indent: int = 0, unit: str = "  ") -> str:
    """Canonical text of a tree: a list without sub-lists on one line; otherwise the leading tokens on the first
    line and every further item on its own line, one `unit` deeper."""
    if not isinstance(node, list):
        return _atom(node)
    if not node:
        return "()"
    if all(not isinstance(x, list) for x in node):
        return "(" + " ".join(_atom(x) for x in node) + ")"
    k = 0
    while k < len(node) and not isinstance(node[k], list):
        k += 1
    pad = unit * (indent + 1)
    out = ["(" + " ".join(_atom(x) for x in node[:k])]
    for x in node[k:]:
        out.append("\n" + pad + dump(x, indent + 1, unit))
    return "".join(out) + "\n" + unit * indent + ")"


def find(node, key: str) -> list:
    """All direct child lists of `node` whose first token is `key` (an empty list when `node` is None)."""
    if node is None:
        return []
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def first(node, key: str):
    """The first direct child list whose first token is `key`, or None (also when `node` is None)."""
    if node is None:
        return None
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def value(node, key: str, default=None):
    """The second token of the first child `key` ((key value) -> value), or `default`."""
    f = first(node, key)
    return f[1] if f is not None and len(f) > 1 else default


def walk(node, key: str):
    """Every list below `node`, at any depth, whose first token is `key` (in file order)."""
    todo = [node]
    while todo:
        n = todo.pop()
        if n and n[0] == key and n is not node:
            yield n
        todo.extend(x for x in reversed(n) if isinstance(x, list))


# ---- edit in place ---------------------------------------------------------------------------------------------------
class _Tok(str):
    """A bare token that remembers where it stands in the source text."""
    start: int = -1
    end: int = -1


class _QTok(Q):
    """A quoted token that remembers where it stands in the source text (the quotes included)."""
    start: int = -1
    end: int = -1


class Node(list):
    """A list that remembers where it stands in the source text: text[start] is '(' and text[end - 1] is ')'."""
    start: int = -1
    end: int = -1
    parent: "Node | None" = None


class Document:
    """An existing KiCad file, edited without touching anything else (see the module text)."""

    def __init__(self, text: str):
        self.source = text
        self._edits: list[tuple[int, int, str]] = []
        self.unit = "\t" if re.search(r"\n\t+\(", text) else "  "
        top = Node()
        top.start = 0
        top.end = len(text)
        stack: list[Node] = [top]
        pos = 0
        for m in _TOKEN.finditer(text):
            if m.start() != pos:
                raise SexpError(f"unreadable text at {_where(text, pos)} (an unterminated string?)")
            pos = m.end()
            k = m.lastindex
            if k is None:
                continue
            if k == 1:
                n = Node()
                n.start = m.start()
                n.parent = stack[-1]
                stack.append(n)
            elif k == 2:
                if len(stack) == 1:
                    raise SexpError(f"')' without '(' at {_where(text, m.start())}")
                n = stack.pop()
                n.end = m.end()
                stack[-1].append(n)
            elif k == 3:
                q = _QTok(_unescape(m.group(3)))
                q.start = m.start()
                q.end = m.end()
                stack[-1].append(q)
            else:
                t = _Tok(m.group(4))
                t.start = m.start()
                t.end = m.end()
                stack[-1].append(t)
        if pos != len(text):
            raise SexpError(f"unreadable text at {_where(text, pos)} (an unterminated string?)")
        if len(stack) != 1:
            raise SexpError(f"{len(stack) - 1} '(' not closed at the end of the text")
        self.items: Node = top                              # every top-level expression
        self.root: Node = top[0] if len(top) == 1 and isinstance(top[0], Node) else top

    @classmethod
    def load(cls, path: str) -> "Document":
        with open(path, encoding="utf-8", newline="") as f:           # newline="": line ends stay as they are
            return cls(f.read())

    # ---- queries ---------------------------------------------------------------------------------------------
    def find_all(self, key: str, under=None) -> list:
        """Every node at any depth below `under` (default: the whole file) whose first token is `key`."""
        return list(walk(under if under is not None else self.items, key))

    # ---- helpers ---------------------------------------------------------------------------------------------
    def _span(self, item) -> tuple[int, int]:
        s, e = getattr(item, "start", -1), getattr(item, "end", -1)
        if s < 0 or e < 0:
            raise ValueError("this item is not part of the document (edits take nodes and tokens found in it)")
        return s, e

    def _lead(self, pos: int) -> str:
        """The white space that stands directly before text position `pos`."""
        i = pos
        while i > 0 and self.source[i - 1] in " \t\r\n":
            i -= 1
        return self.source[i:pos]

    def _render(self, new, lead: str) -> str:
        if isinstance(new, list):
            ind = lead.rsplit("\n", 1)[-1] if "\n" in lead else ""
            lines = dump(new, 0, self.unit).split("\n")
            nl = "\r\n" if "\r\n" in lead else "\n"
            return lines[0] + "".join(nl + ind + ln for ln in lines[1:])
        return _atom(new)

    def _edit(self, start: int, end: int, text: str) -> None:
        for s, e, _ in self._edits:
            if (start < e and s < end) or (start == end and s == e == start):
                raise ValueError("two edits touch the same place: apply text() and parse again between them")
        self._edits.append((start, end, text))

    # ---- edits -----------------------------------------------------------------------------------------------
    def replace(self, item, new) -> None:
        """Put `new` (a list, a Q, or a bare token) in the place of `item` (a node or a token of this document)."""
        s, e = self._span(item)
        self._edit(s, e, self._render(new, self._lead(s)))

    def set(self, node, index: int, new) -> None:
        """Replace the index-th item of `node` (0 is the head)."""
        self.replace(node[index], new)

    def remove(self, item) -> None:
        """Take `item` out, together with the white space in front of it."""
        s, e = self._span(item)
        self._edit(s - len(self._lead(s)), e, "")

    def insert_after(self, sibling, new) -> None:
        s, e = self._span(sibling)
        lead = self._lead(s) or " "
        self._edit(e, e, lead + self._render(new, lead))

    def insert_before(self, sibling, new) -> None:
        s, _ = self._span(sibling)
        lead = self._lead(s) or " "
        self._edit(s, s, self._render(new, lead) + lead)

    def append(self, parent, new) -> None:
        """Add `new` as the last item of `parent`."""
        if not isinstance(parent, Node) or parent is self.items or not parent:
            raise ValueError("append needs a non-empty node of this document")
        kids = [x for x in parent if isinstance(x, Node)]
        if kids:
            lead = self._lead(kids[-1].start) or " "
        elif isinstance(new, list) and "\n" in self.source[parent.start:parent.end]:
            lead = self._lead(parent.start) + self.unit
        else:
            lead = " "
        e = self._span(parent[-1])[1]
        self._edit(e, e, lead + self._render(new, lead))

    # ---- result ----------------------------------------------------------------------------------------------
    def text(self) -> str:
        """The source with the edits applied; with no edit, the source itself, byte for byte."""
        out, pos = [], 0
        for s, e, t in sorted(self._edits, key=lambda x: (x[0], x[1])):
            out.append(self.source[pos:s])
            out.append(t)
            pos = e
        out.append(self.source[pos:])
        return "".join(out)


# ---- self-test -------------------------------------------------------------------------------------------------------
def _self_test() -> int:
    nl = "\r\n"
    src = nl.join(['(kicad_pcb', '\t(version 20241229)', '\t(footprint "R_0603"', '\t\t(layer "F.Cu")',
                   '\t\t(at 10.160000 5.08 90)', '\t\t(property "Value" "10k \\"1%\\"\\n2nd \\\\n")', '\t)', ')', ''])
    want = nl.join(['(kicad_pcb', '\t(version 20241229)', '\t(footprint "R_0603"', '\t\t(layer "B.Cu")',
                    '\t\t(at 12.5 5.08 90)', '\t\t(attr smd)', '\t)', ')', ''])
    bad = []
    tree = parse(src)
    fp0 = first(tree, "footprint")
    prop0 = first(fp0, "property")
    if fp0 is None or prop0 is None or value(fp0, "layer") != "F.Cu" or prop0[2] != '10k "1%"\n2nd \\n':
        bad.append("parse")
    if parse(dump(tree)) != tree:
        bad.append("dump/parse round trip")
    d = Document(src)
    if d.text() != src:
        bad.append("an unedited document changed")
    fp = d.find_all("footprint")[0]
    at, layer, prop = first(fp, "at"), first(fp, "layer"), first(fp, "property")
    if at is None or layer is None or prop is None:
        bad.append("find in a document")
    else:
        d.set(at, 1, "12.5")
        d.replace(layer, ["layer", Q("B.Cu")])
        d.append(fp, ["attr", "smd"])
        d.remove(prop)
        if d.text() != want:
            bad.append("edit in place")
    for broken in ('(a (b "c)', "(a (b)", "(a))"):
        try:
            parse(broken)
            bad.append(f"accepted {broken!r}")
        except SexpError:
            pass
    print("sexp self-test:", "PASS" if not bad else "FAIL " + ", ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        sys.exit(_self_test())
    print(__doc__)
    sys.exit(0 if any(a in ("-h", "--help") for a in sys.argv[1:]) else 2)
