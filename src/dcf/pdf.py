"""A very small PDF writer (A4, Helvetica, text, rectangles, lines).

Enough for the two-page report and case study without adding a library to the
serverless bundle. Coordinates are in points from the top-left corner. The
standard fonts have no rupee sign, so documents write "INR".
"""

from __future__ import annotations

WIDTH, HEIGHT = 595.0, 842.0
_REPLACE = {"₹": "INR ", "−": "-", "→": "to", "×": "x", "÷": "/", "–": "-", "—": "-"}
# Helvetica advance widths (1/1000 em) for the characters that matter to alignment
_NARROW = set(" ijlI.,:;'|!ft()[]r-/")
_WIDE = set("mwMW%@")


def _clean(text: str) -> str:
    for a, b in _REPLACE.items():
        text = text.replace(a, b)
    return text.encode("cp1252", "replace").decode("cp1252")


def text_width(text: str, size: float) -> float:
    """Approximate width of Helvetica text; digits are exact (0.556 em)."""
    total = 0.0
    for ch in _clean(text):
        if ch.isdigit():
            total += 0.556
        elif ch in _NARROW:
            total += 0.3
        elif ch in _WIDE:
            total += 0.86
        elif ch.isupper():
            total += 0.68
        else:
            total += 0.53
    return total * size


def wrap(text: str, size: float, width: float) -> list[str]:
    """Greedy word wrap to the given width."""
    lines: list[str] = []
    line = ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and text_width(trial, size) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return [*lines, line] if line else lines


class Pdf:
    def __init__(self) -> None:
        self.pages: list[list[str]] = []
        self.add_page()

    def add_page(self) -> None:
        self.pages.append([])

    def text(
        self,
        x: float,
        y: float,
        value: str,
        size: float = 9,
        bold: bool = False,
        grey: float = 0.05,
        align: str = "left",
    ) -> None:
        if align != "left":
            w = text_width(value, size)
            x -= w if align == "right" else w / 2
        safe = _clean(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        self.pages[-1].append(
            f"BT /{'F2' if bold else 'F1'} {size:g} Tf {grey:.3f} g {x:.2f} {HEIGHT - y:.2f} Td "
            f"({safe}) Tj ET"
        )

    def paragraph(
        self, x: float, y: float, value: str, width: float, size: float = 9, grey: float = 0.15
    ) -> float:
        """Wrapped text; returns the y position below it."""
        for line in wrap(value, size, width):
            self.text(x, y, line, size, grey=grey)
            y += size * 1.38
        return y

    def rect(self, x: float, y: float, w: float, h: float, grey: float) -> None:
        self.pages[-1].append(f"{grey:.3f} g {x:.2f} {HEIGHT - y - h:.2f} {w:.2f} {h:.2f} re f")

    def line(
        self, x1: float, y1: float, x2: float, y2: float, grey: float = 0.82, width: float = 0.6
    ) -> None:
        self.pages[-1].append(
            f"{grey:.3f} G {width:g} w {x1:.2f} {HEIGHT - y1:.2f} m {x2:.2f} {HEIGHT - y2:.2f} l S"
        )

    def table(
        self, x: float, y: float, widths: list[float], rows: list[list[str]], size: float = 8.5
    ) -> float:
        """First row is the header; first column is left aligned. Returns y below the table."""
        for r, row in enumerate(rows):
            left = x
            for c, (cell, w) in enumerate(zip(row, widths, strict=True)):
                if c == 0:
                    self.text(left, y, cell, size, bold=r == 0)
                else:
                    self.text(left + w, y, cell, size, bold=r == 0, align="right")
                left += w
            self.line(x, y + 4, x + sum(widths), y + 4)
            y += size * 1.75
        return y

    def to_bytes(self) -> bytes:
        objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
        for name in ("Helvetica", "Helvetica-Bold"):
            objects.append(
                f"<< /Type /Font /Subtype /Type1 /BaseFont /{name} "
                "/Encoding /WinAnsiEncoding >>".encode()
            )
        kids: list[str] = []
        for commands in self.pages:
            stream = "\n".join(commands).encode("cp1252")
            page_no = len(objects) + 1
            kids.append(f"{page_no} 0 R")
            objects.append(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {WIDTH:g} {HEIGHT:g}] "
                "/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                f"/Contents {page_no + 1} 0 R >>".encode()
            )
            objects.append(
                f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
            )
        objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()
        out = bytearray(b"%PDF-1.4\n")
        offsets: list[int] = []
        for i, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        start = len(out)
        out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
        out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
        out += (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n"
        ).encode()
        return bytes(out)
