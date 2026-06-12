"""
Task 1 — Thu thập văn bản pháp luật về ma tuý và các chất cấm.

Tải toàn văn từ nguồn công khai (thuvienphapluat.vn, hethongphapluat.com),
rồi lưu PDF UTF-8 — không dùng nội dung giả khi link 404.
"""

import io
import re
import time
from html import unescape
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

MIN_VALID_BYTES = 10_000

LEGAL_DOCUMENTS = [
    {
        "filename": "luat-phong-chong-ma-tuy-2021.pdf",
        "title": "Luật Phòng, chống ma túy 2021 (73/2021/QH14)",
        "page_url": (
            "https://thuvienphapluat.vn/van-ban/Trach-nhiem-hinh-su/"
            "Luat-Phong-chong-ma-tuy-2021-445185.aspx"
        ),
        "source": "thuvienphapluat",
    },
    {
        "filename": "nghi-dinh-105-2021.pdf",
        "title": "Nghị định 105/2021/NĐ-CP",
        "page_url": (
            "https://thuvienphapluat.vn/van-ban/Van-hoa-Xa-hoi/"
            "Nghi-dinh-105-2021-ND-CP-huong-dan-Luat-Phong-chong-ma-tuy-496664.aspx"
        ),
        "source": "thuvienphapluat",
    },
    {
        "filename": "bo-luat-hinh-su-ma-tuy.pdf",
        "title": "Bộ luật Hình sự 2015 — Chương XX: Các tội phạm về ma túy",
        "page_url": "https://hethongphapluat.com/bo-luat-hinh-su-2015/phan-2/chuong-20",
        "source": "hethongphapluat",
    },
]


def setup_directory():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Thu muc da san sang: {DATA_DIR}")


def _fetch_html(url: str) -> str:
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(
                url, headers=BROWSER_HEADERS, timeout=90, allow_redirects=True
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except Exception as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Khong tai duoc trang: {url}") from last_error


def _strip_html(html_fragment: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html_fragment, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"[ \t]+", " ", text)).strip()


def _extract_paragraphs(html: str, start: int, end: int) -> list[str]:
    chunk = html[start:end]
    paragraphs: list[str] = []
    for match in re.finditer(r"<p[^>]*>(.*?)</p>", chunk, flags=re.S | re.I):
        text = _strip_html(match.group(1))
        if len(text) >= 3:
            paragraphs.append(text)
    return paragraphs


def _extract_thuvienphapluat(html: str) -> str:
    start_markers = [
        'name="dieu_1"',
        "Quốc hội ban hành",
        "Chính phủ ban hành",
    ]
    start = -1
    for marker in start_markers:
        pos = html.find(marker)
        if pos >= 0:
            start = pos
            break
    if start < 0:
        raise ValueError("Khong tim thay noi dung van ban tren thuvienphapluat.vn")

    end_markers = [
        'id="divFooter"',
        'class="footer"',
        "Liên quan hiệu lực",
        "Các bản dự thảo",
    ]
    end = len(html)
    for marker in end_markers:
        pos = html.find(marker, start)
        if 0 <= pos < end:
            end = pos

    paragraphs = _extract_paragraphs(html, start, end)
    if len(paragraphs) < 20:
        raise ValueError(f"Noi dung qua ngan ({len(paragraphs)} doan)")
    return "\n\n".join(paragraphs)


def _extract_hethongphapluat(html: str) -> str:
    start = -1
    for pattern in (
        r"<p[^>]*>\s*Điều 247[^<]*</p>",
        r"<h1[^>]*>.*?Chương 20.*?</h1>",
        r"Chương XX",
    ):
        match = re.search(pattern, html, re.S | re.I)
        if match:
            start = match.start()
            break
    if start < 0:
        start = html.find("Điều 247")
    if start < 0:
        raise ValueError("Khong tim thay Chuong XX tren hethongphapluat.com")

    end = len(html)
    for marker in ('class="footer"', "id=\"footer\"", "Liên hệ", "</main>", "</body>"):
        pos = html.find(marker, start)
        if 0 <= pos < end:
            end = pos

    paragraphs = _extract_paragraphs(html, start, end)
    if len(paragraphs) < 10:
        raise ValueError(f"Noi dung Chuong XX qua ngan ({len(paragraphs)} doan)")
    return "\n\n".join(paragraphs)


def fetch_document_text(doc: dict) -> str:
    html = _fetch_html(doc["page_url"])
    if doc["source"] == "thuvienphapluat":
        body = _extract_thuvienphapluat(html)
    else:
        body = _extract_hethongphapluat(html)
    return f"{doc['title']}\n\nNguon: {doc['page_url']}\n\n{body}"


def _find_unicode_font() -> str | None:
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\times.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def _text_to_pdf(title: str, text: str) -> bytes:
    font_path = _find_unicode_font()
    if font_path:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.pdfgen import canvas

            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            pdfmetrics.registerFont(TTFont("LegalFont", font_path))
            c.setFont("LegalFont", 10)

            width, height = A4
            x, y = 50, height - 50
            line_height = 14
            max_chars = 95

            for raw_line in text.splitlines():
                line = raw_line.strip() or ""
                if not line:
                    y -= line_height
                    continue
                while len(line) > max_chars:
                    if y < 60:
                        c.showPage()
                        c.setFont("LegalFont", 10)
                        y = height - 50
                    c.drawString(x, y, line[:max_chars])
                    line = line[max_chars:]
                    y -= line_height
                if y < 60:
                    c.showPage()
                    c.setFont("LegalFont", 10)
                    y = height - 50
                c.drawString(x, y, line)
                y -= line_height

            c.save()
            return buffer.getvalue()
        except Exception:
            pass

    return _minimal_pdf_bytes(f"{title}\n\n{text}")


def _minimal_pdf_bytes(text: str) -> bytes:
    """Build a valid multi-page PDF containing plain text (ASCII fallback)."""
    safe = text.encode("latin-1", errors="replace").decode("latin-1")
    lines = (
        safe.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .split("\n")
    )
    segments: list[str] = []
    for line in lines:
        while len(line) > 90:
            segments.append(line[:90])
            line = line[90:]
        if line:
            segments.append(line)

    pages: list[list[str]] = []
    for i in range(0, len(segments), 45):
        pages.append(segments[i : i + 45])
    if not pages:
        pages = [["No content"]]

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")

    kid_refs = " ".join(f"{3 + i * 2} 0 R" for i in range(len(pages)))
    objects.append(
        f"2 0 obj<< /Type /Pages /Kids [{kid_refs}] /Count {len(pages)} >>endobj\n".encode()
    )

    for page_idx, page_lines in enumerate(pages):
        page_id = 3 + page_idx * 2
        content_id = page_id + 1

        stream_lines = ["BT", "/F1 11 Tf", "50 750 Td"]
        for i, line in enumerate(page_lines):
            if i:
                stream_lines.append("0 -14 Td")
            stream_lines.append(f"({line}) Tj")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("latin-1", errors="replace")

        objects.append(
            f"{page_id} 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R /Resources<< /Font<< /F1 {3 + len(pages) * 2} 0 R >> >> >>endobj\n".encode()
        )
        objects.append(
            f"{content_id} 0 obj<< /Length {len(stream)} >>stream\n".encode()
            + stream
            + b"\nendstream\nendobj\n"
        )

    font_id = 3 + len(pages) * 2
    objects.append(
        f"{font_id} 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n".encode()
    )

    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj
    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += (
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode()
    return pdf


def _needs_refresh(filepath: Path) -> bool:
    if not filepath.exists():
        return True
    if filepath.stat().st_size < MIN_VALID_BYTES:
        return True
    header = filepath.read_bytes()[:5]
    return header != b"%PDF-"


def download_document(doc: dict) -> None:
    filepath = DATA_DIR / doc["filename"]
    txt_path = filepath.with_suffix(".txt")

    if filepath.exists() and filepath.stat().st_size >= MIN_VALID_BYTES and not txt_path.exists():
        print(f"  -> Tao file UTF-8 tu nguon (PDF da co san)")
        text = fetch_document_text(doc)
        txt_path.write_text(text, encoding="utf-8")
        print(f"  [OK] Da luu: {txt_path.name} ({len(text):,} chars)")
        return

    if not _needs_refresh(filepath):
        print(f"  [OK] Da co san: {filepath.name} ({filepath.stat().st_size:,} bytes)")
        return

    print(f"  -> Tai toan van tu: {doc['page_url']}")
    text = fetch_document_text(doc)
    if len(text) < 5000:
        raise RuntimeError(
            f"Noi dung {doc['filename']} qua ngan ({len(text)} chars) — kiem tra nguon."
        )

    pdf_bytes = _text_to_pdf(doc["title"], text)
    if len(pdf_bytes) < MIN_VALID_BYTES:
        raise RuntimeError(
            f"PDF {doc['filename']} qua nho ({len(pdf_bytes)} bytes) sau khi tao."
        )

    filepath.write_bytes(pdf_bytes)
    text_path = filepath.with_suffix(".txt")
    text_path.write_text(text, encoding="utf-8")
    print(
        f"  [OK] Da luu: {filepath.name} ({len(pdf_bytes):,} bytes) "
        f"+ {text_path.name} ({len(text):,} chars)"
    )


def download_all():
    """Download all legal documents from official public sources."""
    setup_directory()
    for doc in LEGAL_DOCUMENTS:
        print(f"\n[{doc['filename']}]")
        download_document(doc)
    print("\n[OK] Hoan tat thu thap van ban phap luat.")


if __name__ == "__main__":
    download_all()
