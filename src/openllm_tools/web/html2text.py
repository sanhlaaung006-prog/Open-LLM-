"""Turn HTML into compact Markdown-ish text for an LLM to read.

Not a browser and not a full Markdown renderer - just enough structure
(headings, links, lists, code, quotes, tables) that a model can follow
a page without drowning in markup.

Built on :mod:`html.parser`, so there are no dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

__all__ = ["HtmlDocument", "html_to_text", "extract_title"]

# Sentinels that protect <pre> whitespace from the collapsing pass below.
_PRE_NL = "\x00"
_PRE_SP = "\x01"
_PRE_TAB = "\x02"

_SKIP_TAGS = {
    "script", "style", "noscript", "template", "svg", "iframe", "canvas",
    "head", "object", "embed", "video", "audio",
}

_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}

_HEADINGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}


@dataclass
class HtmlDocument:
    """The result of converting an HTML document to text."""

    text: str
    title: str | None = None

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.text


class _Converter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.title: str | None = None
        self._title_parts: list[str] = []
        self._in_title = False
        self._skip_depth = 0
        self._pre_depth = 0
        self._lists: list[str] = []          # "ul" | "ol"
        self._list_counters: list[int] = []
        self._link_stack: list[str] = []     # hrefs of open <a> tags

    # -- helpers ---------------------------------------------------------
    def _emit(self, chunk: str) -> None:
        if chunk:
            self.out.append(chunk)

    def _newline(self, count: int = 1) -> None:
        self.out.append("\n" * count)

    def _ensure_newline(self) -> None:
        """Start a new line unless we are already at the start of one."""
        if not self.out:
            return
        tail = "".join(self.out[-2:])
        if not tail.endswith("\n"):
            self.out.append("\n")

    # -- parser hooks ----------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrib = {k.lower(): (v or "") for k, v in attrs}

        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return

        if tag == "title":
            self._in_title = True
            return

        if self._skip_depth:
            return

        if tag in _VOID_TAGS:
            if tag == "br":
                self._emit("\n")
            elif tag == "hr":
                self._ensure_newline()
                self._emit("\n---\n")
            elif tag == "img":
                alt = attrib.get("alt", "").strip()
                src = attrib.get("src", "").strip()
                if alt or src:
                    self._emit(f"![{alt}]({src})")
            return

        if tag in _HEADINGS:
            self._ensure_newline()
            self._emit("\n" + _HEADINGS[tag] + " ")
        elif tag in ("p", "div", "section", "article", "header", "footer", "main",
                     "aside", "nav", "figure", "figcaption", "form", "fieldset",
                     "details", "summary", "dl"):
            self._ensure_newline()
            self._emit("\n")
        elif tag == "ul" or tag == "ol":
            self._ensure_newline()
            self._lists.append(tag)
            self._list_counters.append(0)
        elif tag == "li":
            self._ensure_newline()
            depth = max(len(self._lists) - 1, 0)
            if self._lists and self._lists[-1] == "ol":
                self._list_counters[-1] += 1
                marker = f"{self._list_counters[-1]}. "
            else:
                marker = "- "
            self._emit("  " * depth + marker)
        elif tag == "pre":
            self._ensure_newline()
            self._pre_depth += 1
            self._emit("\n```\n")
        elif tag == "code":
            if not self._pre_depth:
                self._emit("`")
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "blockquote":
            self._ensure_newline()
            self._emit("\n> ")
        elif tag == "a":
            href = attrib.get("href", "").strip()
            if href.lower().startswith("javascript:"):
                href = ""
            self._link_stack.append(href)
            if href:
                self._emit("[")
        elif tag == "tr":
            self._ensure_newline()
            self._emit("|")
        elif tag in ("td", "th"):
            self._emit(" ")
        elif tag == "br":
            self._emit("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return

        if tag == "title":
            self._in_title = False
            title = re.sub(r"\s+", " ", "".join(self._title_parts)).strip()
            if title:
                self.title = title
            return

        if self._skip_depth:
            return

        if tag in _VOID_TAGS:
            return

        if tag in _HEADINGS:
            self._emit("\n")
        elif tag in ("p", "div", "section", "article", "header", "footer", "main",
                     "aside", "nav", "figure", "figcaption", "form", "fieldset",
                     "details", "summary", "dl", "table"):
            self._ensure_newline()
            self._emit("\n")
        elif tag in ("ul", "ol"):
            if self._lists:
                self._lists.pop()
                self._list_counters.pop()
            self._ensure_newline()
            self._emit("\n")
        elif tag == "li":
            self._ensure_newline()
        elif tag == "pre":
            self._pre_depth = max(0, self._pre_depth - 1)
            self._emit("\n```\n")
        elif tag == "code":
            if not self._pre_depth:
                self._emit("`")
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "a":
            href = self._link_stack.pop() if self._link_stack else ""
            if href:
                self._emit(f"]({href})")
        elif tag in ("td", "th"):
            self._emit(" |")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
            return
        if self._skip_depth:
            return
        if self._pre_depth:
            data = (
                data.replace("\t", _PRE_TAB * 4)
                .replace(" ", _PRE_SP)
                .replace("\n", _PRE_NL)
            )
            self._emit(data)
            return
        self._emit(data)


_WS_RUN = re.compile(r"[ \t\f\v\u00a0]+")
_SPACE_AROUND_NL = re.compile(r" *\n *")
_BLANK_RUN = re.compile(r"\n{3,}")
_SPACE_BEFORE_PUNCT = re.compile(r" +([.,;:!?)])")
_EMPTY_LINK = re.compile(r"!?\[\]\([^)]*\)")
_BARE_BULLET = re.compile(r"^[ \t]*(?:[-*]|\d+\.)[ \t]*$", re.MULTILINE)


def _tidy(text: str) -> str:
    for _ in range(2):
        text = _WS_RUN.sub(" ", text)
        text = _SPACE_AROUND_NL.sub("\n", text)
        text = _EMPTY_LINK.sub("", text)
        text = _BARE_BULLET.sub("", text)
        text = _BLANK_RUN.sub("\n\n", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    return text.strip()


def html_to_text(html: str) -> HtmlDocument:
    """Convert an HTML document into readable text plus its ``<title>``."""
    parser = _Converter()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # pragma: no cover - html.parser is very forgiving
        pass

    raw = "".join(parser.out)
    text = _tidy(raw)
    # Restore whitespace that was protected inside <pre> blocks.
    text = (
        text.replace(_PRE_NL, "\n")
        .replace(_PRE_TAB, "\t")
        .replace(_PRE_SP, " ")
    )
    # Collapse the padding that block-level tags leave around fenced code.
    text = re.sub(r"```\s*\n\s*\n", "```\n", text)
    return HtmlDocument(text=text.strip(), title=parser.title)


def extract_title(html: str) -> str | None:
    """Return only the document title (cheap when the body is huge)."""
    return html_to_text(html).title
