"""
Long-text/book import helpers for TTS reading.
"""

from __future__ import annotations

import html
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from models.nlp.prompt_builder import normalize_response_language, response_language_from_edge_voice


BOOK_FILE_EXTENSIONS = (".txt", ".md", ".markdown", ".html", ".htm", ".rtf", ".docx", ".epub", ".pdf")
BOOK_FILE_DIALOG_FILTER = (
    "书籍文件 (*.txt *.md *.markdown *.html *.htm *.rtf *.docx *.epub *.pdf);;"
    "文本文件 (*.txt *.md *.markdown);;"
    "网页 / 电子书 (*.html *.htm *.epub);;"
    "Word 文档 (*.docx);;"
    "PDF 文件 (*.pdf);;"
    "所有文件 (*.*)"
)

LANGUAGE_LABELS = {
    "zh-CN": "中文",
    "zh-HK": "粤语 / 中文",
    "zh-TW": "繁体中文",
    "en-US": "英语",
    "en-GB": "英语",
    "fr-FR": "法语",
    "de-DE": "德语",
    "es-ES": "西班牙语",
    "es-MX": "西班牙语",
    "it-IT": "意大利语",
    "pt-BR": "葡萄牙语",
    "ru-RU": "俄语",
    "nl-NL": "荷兰语",
    "hi-IN": "印地语",
    "ar-EG": "阿拉伯语",
    "ja-JP": "日语",
    "ko-KR": "韩语",
}


@dataclass(frozen=True)
class BookDocument:
    path: str
    title: str
    text: str
    extension: str


class _HTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag in {"br", "p", "div", "section", "article", "chapter", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in {"p", "div", "section", "article", "chapter", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth <= 0 and data:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def read_book_file(path: str | Path) -> BookDocument:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(str(file_path))

    suffix = file_path.suffix.lower()
    if suffix not in BOOK_FILE_EXTENSIONS:
        raise ValueError(f"不支持的书籍格式：{suffix or file_path.name}")

    if suffix in {".txt", ".md", ".markdown"}:
        text = _read_text_file(file_path)
        if suffix in {".md", ".markdown"}:
            text = _strip_markdown(text)
    elif suffix in {".html", ".htm"}:
        text = _html_to_text(_read_text_file(file_path))
    elif suffix == ".rtf":
        text = _rtf_to_text(_read_text_file(file_path))
    elif suffix == ".docx":
        text = _docx_to_text(file_path)
    elif suffix == ".epub":
        text = _epub_to_text(file_path)
    elif suffix == ".pdf":
        text = _pdf_to_text(file_path)
    else:
        text = ""

    text = normalize_reader_text(text)
    if not text:
        raise ValueError(f"{file_path.name} 没有可朗读的文本内容")
    return BookDocument(path=str(file_path), title=file_path.stem, text=text, extension=suffix)


def read_book_files(paths: list[str | Path]) -> list[BookDocument]:
    documents: list[BookDocument] = []
    for path in paths:
        documents.append(read_book_file(path))
    return documents


def combine_documents(documents: list[BookDocument]) -> str:
    chunks: list[str] = []
    for doc in documents:
        chunks.append(f"《{doc.title}》\n{doc.text}")
    return normalize_reader_text("\n\n".join(chunks))


def normalize_reader_text(text: str) -> str:
    value = html.unescape(str(text or "")).replace("\ufeff", "")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t\f\v]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def split_text_for_tts(text: str, max_chars: int = 700) -> list[str]:
    value = normalize_reader_text(text)
    if not value:
        return []
    max_chars = max(120, int(max_chars or 700))
    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for paragraph in re.split(r"\n{2,}", value):
        paragraph = paragraph.strip()
        if not paragraph:
            flush()
            continue
        sentences = _split_sentences(paragraph)
        for sentence in sentences:
            if len(sentence) > max_chars:
                flush()
                chunks.extend(_hard_wrap(sentence, max_chars))
                continue
            if current and len(current) + len(sentence) + 1 > max_chars:
                flush()
            current = f"{current} {sentence}".strip() if current else sentence
        flush()
    flush()
    return chunks


def detect_text_language(text: str) -> str:
    sample = normalize_reader_text(text)[:8000]
    if len(sample.strip()) < 4:
        return ""

    counts = {
        "zh": _count_range(sample, "\u4e00", "\u9fff"),
        "ja": _count_range(sample, "\u3040", "\u30ff"),
        "ko": _count_range(sample, "\uac00", "\ud7af"),
        "ru": _count_range(sample, "\u0400", "\u04ff"),
        "ar": _count_range(sample, "\u0600", "\u06ff"),
        "hi": _count_range(sample, "\u0900", "\u097f"),
    }
    if counts["ja"] >= 3:
        return "ja-JP"
    if counts["ko"] >= 3:
        return "ko-KR"
    if counts["ru"] >= 3:
        return "ru-RU"
    if counts["ar"] >= 3:
        return "ar-EG"
    if counts["hi"] >= 3:
        return "hi-IN"
    if counts["zh"] >= 3:
        return "zh-CN"

    latin = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", sample)
    if not latin:
        return ""
    lowered = f" {' '.join(latin).lower()} "
    if re.search(r"[àâçéèêëîïôùûüÿœæ]", lowered) or _has_words(lowered, {" le ", " la ", " les ", " des ", " une ", " est ", " pour "}):
        return "fr-FR"
    if re.search(r"[äöüß]", lowered) or _has_words(lowered, {" der ", " die ", " das ", " und ", " ist ", " nicht "}):
        return "de-DE"
    if re.search(r"[ñáéíóúü]", lowered) or _has_words(lowered, {" el ", " los ", " las ", " que ", " para ", " una ", " con "}):
        return "es-ES"
    if re.search(r"[ãõáéíóúç]", lowered) or _has_words(lowered, {" você ", " que ", " para ", " uma ", " não ", " com "}):
        return "pt-BR"
    if _has_words(lowered, {" il ", " lo ", " gli ", " una ", " che ", " per ", " sono "}):
        return "it-IT"
    if _has_words(lowered, {" de ", " het ", " een ", " niet ", " voor ", " zijn "}):
        return "nl-NL"
    return "en-US"


def language_label(language: str) -> str:
    normalized = normalize_response_language(language)
    return LANGUAGE_LABELS.get(normalized, normalized or "未知")


def language_family(language: str) -> str:
    normalized = normalize_response_language(language)
    if not normalized:
        return ""
    if normalized.startswith("zh-"):
        return "zh"
    return normalized.split("-", 1)[0].lower()


def languages_compatible(configured_language: str, detected_language: str) -> bool:
    configured_family = language_family(configured_language)
    detected_family = language_family(detected_language)
    if not configured_family or not detected_family:
        return True
    return configured_family == detected_family


def voice_language_from_settings(
    settings: dict[str, Any] | None,
    voice_choice: dict[str, Any] | None = None,
    default_edge_voice: str = "",
) -> str:
    settings = settings or {}
    for key in ("response_language", "reply_language", "language", "lang"):
        language = normalize_response_language(settings.get(key))
        if language:
            return language

    language = response_language_from_edge_voice(settings.get("edge_voice"))
    if language:
        return language

    if isinstance(voice_choice, dict):
        pack_language = voice_choice.get("language")
        if isinstance(pack_language, dict):
            language = normalize_response_language(pack_language.get("id") or pack_language.get("label"))
            if language:
                return language
        elif isinstance(pack_language, str):
            language = normalize_response_language(pack_language)
            if language:
                return language
        language = response_language_from_edge_voice(voice_choice.get("edge_voice"))
        if language:
            return language

    return response_language_from_edge_voice(default_edge_voice)


def _read_text_file(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "big5", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _strip_markdown(text: str) -> str:
    value = re.sub(r"```.*?```", "\n", text, flags=re.DOTALL)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"!\[[^\]]*]\([^)]+\)", "", value)
    value = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", value)
    value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s{0,3}>\s?", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*[-*+]\s+", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*\d+\.\s+", "", value, flags=re.MULTILINE)
    value = value.replace("***", "").replace("**", "").replace("__", "").replace("_", "")
    return value


def _html_to_text(text: str) -> str:
    parser = _HTMLTextParser()
    parser.feed(text)
    parser.close()
    return parser.text()


def _rtf_to_text(text: str) -> str:
    value = text.replace("\\par", "\n").replace("\\line", "\n").replace("\\tab", " ")
    value = re.sub(r"\\'[0-9a-fA-F]{2}", "", value)
    value = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", value)
    value = re.sub(r"[{}]", "", value)
    return value


def _docx_to_text(path: Path) -> str:
    paragraphs: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = ["word/document.xml"]
        names.extend(sorted(name for name in archive.namelist() if re.match(r"word/(header|footer)\d+\.xml$", name)))
        for name in names:
            if name not in archive.namelist():
                continue
            root = ElementTree.fromstring(archive.read(name))
            for paragraph in root.iter():
                if _xml_local_name(paragraph.tag) != "p":
                    continue
                parts: list[str] = []
                for node in paragraph.iter():
                    local = _xml_local_name(node.tag)
                    if local == "t" and node.text:
                        parts.append(node.text)
                    elif local in {"tab", "br"}:
                        parts.append("\t" if local == "tab" else "\n")
                text = "".join(parts).strip()
                if text:
                    paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _epub_to_text(path: Path) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.lower().endswith((".xhtml", ".html", ".htm"))
            and not name.lower().endswith(("nav.xhtml", "toc.xhtml"))
        ]
        for name in sorted(names):
            try:
                raw = archive.read(name).decode("utf-8", errors="ignore")
            except Exception:
                continue
            text = _html_to_text(raw)
            if text.strip():
                parts.append(text)
    return "\n\n".join(parts)


def _pdf_to_text(path: Path) -> str:
    reader_cls: Any | None = None
    try:
        from pypdf import PdfReader  # type: ignore

        reader_cls = PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader_cls = PdfReader
        except ImportError as exc:
            raise RuntimeError("读取 PDF 需要安装 pypdf 或 PyPDF2。") from exc

    reader = reader_cls(str(path))
    pages: list[str] = []
    for page in getattr(reader, "pages", []):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)


def _split_sentences(paragraph: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;.!?])\s+", paragraph)
    if len(parts) == 1:
        parts = re.split(r"(?<=[。！？!?；;.!?])", paragraph)
    return [part.strip() for part in parts if part.strip()]


def _hard_wrap(text: str, max_chars: int) -> list[str]:
    out: list[str] = []
    value = text.strip()
    while value:
        if len(value) <= max_chars:
            out.append(value)
            break
        cut = value.rfind(" ", 0, max_chars)
        if cut < max_chars // 2:
            cut = max_chars
        out.append(value[:cut].strip())
        value = value[cut:].strip()
    return out


def _count_range(text: str, start: str, end: str) -> int:
    return sum(1 for char in text if start <= char <= end)


def _has_words(value: str, words: set[str]) -> bool:
    return any(word in value for word in words)


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag
