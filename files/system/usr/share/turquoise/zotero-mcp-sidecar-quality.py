"""Sidecar fidelity screening and eligibility gate for zotero-mcp.

This module is copied into ``zotero_mcp.sidecar_quality`` by the managed
MinerU overlay patch. It deliberately performs conservative mechanical checks;
a PASS means only that these checks found no blocker, not that a human has
verified every table, equation, scan, or generated figure description.
"""
from __future__ import annotations

import hashlib
import html
from html.parser import HTMLParser
import json
import logging
import os
from pathlib import Path
import re
import tempfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger("zotero_mcp.sidecar_quality")

REPORT_SCHEMA = 2
CHECK_VERSION = "2026-09-24.2"

# Character mappings seen in PDF text layers and MinerU output. In particular,
# PyMuPDF can expose the PDF's mathematical minus as U+0015.
_MINUS_CHARS = "−–—‐‑‒﹣－\x01\x15\x16\x17"
_MINUS_TRANSLATION = str.maketrans({char: "-" for char in _MINUS_CHARS})
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<sign>[+-]?)(?P<number>"
    r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)"
)
_TABLE_LABEL_RE = re.compile(r"\btable\s+([a-z]?\d+[a-z]?)\b", re.I)
_IMAGE_REF_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_FIGURE_SCHEMA_LEAKS = (
    "county-clustered se",
    "years relative to policy adoption (t = -5 to +5)",
    "residential; panel b: commercial",
)


class SidecarQualityError(RuntimeError):
    """A sidecar is missing a current, eligible quality report."""


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[dict[str, Any]]] = []
        self._row: list[dict[str, Any]] | None = None
        self._cell: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag.lower() == "tr":
            self._row = []
        elif tag.lower() in {"td", "th"} and self._row is not None:
            try:
                colspan = max(1, int(attrs_dict.get("colspan") or 1))
            except (TypeError, ValueError):
                colspan = 1
            self._cell = {"text": [], "colspan": colspan, "tag": tag.lower()}

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._cell["text"] = " ".join(" ".join(self._cell["text"]).split())
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def quality_report_path(cfg: dict[str, Any], item_key: str) -> Path:
    return Path(cfg["sidecar_dir"]) / f"{item_key}.quality.json"


def _choose_pdf(reader: Any, item_key: str, attachment_key: str | None = None) -> tuple[str, Path]:
    attachments = reader.get_attachment_paths(item_key)
    candidates: list[tuple[str, Path]] = []
    for att in attachments:
        key = str(att.get("key") or "")
        content_type = str(att.get("content_type") or "").lower()
        path = att.get("resolved_path")
        if not path:
            continue
        path = Path(path)
        if content_type != "application/pdf" and path.suffix.lower() != ".pdf":
            continue
        if path.is_file():
            candidates.append((key, path))
    if attachment_key:
        selected = [(key, path) for key, path in candidates if key == attachment_key]
        if len(selected) != 1:
            raise SidecarQualityError(
                f"attachment {attachment_key!r} is not one resolvable PDF child of item {item_key}"
            )
        return selected[0]
    if len(candidates) != 1:
        raise SidecarQualityError(
            f"item {item_key} has {len(candidates)} resolvable PDFs; pass the exact --attachment-key"
        )
    return candidates[0]


def _parser_manifest(
    cfg: dict[str, Any], item_key: str, pdf_hash: str, manifest_path: str | None = None,
) -> dict[str, Any] | None:
    work_root = Path(cfg.get("work_dir", Path.home() / ".cache/zotero-mcp/mineru-work")) / item_key
    if manifest_path is not None:
        # A previous eligible report remains bound to its own immutable run,
        # even when an attempted regeneration leaves a newer rejected run.
        requested = Path(manifest_path).resolve()
        runs = (work_root / "runs").resolve()
        if requested.parent.parent != runs or requested.name != "manifest.json":
            return None
        manifests = [requested] if requested.is_file() else []
    else:
        manifests = sorted(
            (p for p in work_root.glob("runs/*/manifest.json") if p.is_file()),
            key=lambda p: p.stat().st_mtime_ns,
        )
    for path in reversed(manifests):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("pdf_sha256") == pdf_hash:
            data["manifest_path"] = str(path)
            data["manifest_root"] = str(path.parent)
            data["manifest_sha256"] = sha256_file(path)
            return data

    # Backward compatibility for parses created before run manifests existed.
    # These artifacts can support a pilot, but their parser version is unknown.
    legacy = sorted(
        work_root.glob("out/*/txt/*_content_list.json"),
        key=lambda p: p.stat().st_mtime_ns,
    )
    if legacy:
        content_list = legacy[-1]
        raw_md = next(iter(content_list.parent.glob("*.md")), None)
        return {
            "parser_version": None,
            "content_list_path": str(content_list),
            "raw_markdown_path": str(raw_md) if raw_md else None,
            "pdf_sha256": None,
            "legacy_artifacts": True,
        }
    return None


def _normalize_text(text: str) -> str:
    text = html.unescape(text).translate(_MINUS_TRANSLATION)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"(?<=[+-])\s+(?=(?:\d|\.))", "", text)
    text = re.sub(r"(?<=\.)\s+(?=\d)", "", text)
    return text


def _number_tokens(text: str) -> list[tuple[str, int]]:
    normalized = _normalize_text(text)
    out: list[tuple[str, int]] = []
    for match in _NUMBER_RE.finditer(normalized):
        try:
            value = Decimal(match.group("number").replace(",", ""))
        except InvalidOperation:
            continue
        if not value:
            continue
        absolute = format(abs(value).normalize(), "f")
        sign = -1 if match.group("sign") == "-" else 1
        out.append((absolute, sign))
    return out


def _stable_finding_id(code: str, locator: str, detail: str = "") -> str:
    return hashlib.sha256(f"{code}\0{locator}\0{detail}".encode("utf-8")).hexdigest()[:12]


def _add_finding(
    findings: list[dict[str, Any]],
    code: str,
    severity: str,
    locator: str,
    message: str,
    detail: str = "",
) -> None:
    finding_id = _stable_finding_id(code, locator, detail)
    if any(f.get("id") == finding_id for f in findings):
        return
    findings.append({
        "id": finding_id,
        "code": code,
        "severity": severity,
        "locator": locator,
        "message": message,
        **({"detail": detail} if detail else {}),
    })


def _plain_html_text(source: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", source)).split())


def _table_caption(prefix: str) -> str:
    matches = list(_TABLE_LABEL_RE.finditer(prefix))
    if not matches:
        return ""
    match = matches[-1]
    line_start = prefix.rfind("\n", 0, match.start()) + 1
    line_end = prefix.find("\n", match.end())
    if line_end < 0:
        line_end = len(prefix)
    return " ".join(prefix[line_start:line_end].split())[:240]


def _table_label(caption: str) -> str | None:
    match = _TABLE_LABEL_RE.search(caption)
    return match.group(1).lower() if match else None


def _extract_tables(sidecar: str) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for match in re.finditer(r"<table\b[^>]*>.*?</table\s*>", sidecar, re.I | re.S):
        parser = _TableParser()
        try:
            parser.feed(match.group(0))
            parser.close()
        except Exception:
            continue
        prefix = sidecar[max(0, match.start() - 600):match.start()]
        caption = _table_caption(prefix)
        line = sidecar.count("\n", 0, match.start()) + 1
        tables.append({"caption": caption, "rows": parser.rows, "line": line, "html": match.group(0)})
    return tables


def _logical_width(row: list[dict[str, Any]]) -> int:
    return sum(int(cell.get("colspan", 1)) for cell in row)


def _cell_text(row: list[dict[str, Any]], index: int) -> str:
    if index >= len(row):
        return ""
    return str(row[index].get("text") or "")


def _check_table(table: dict[str, Any], page_text: str | None, findings: list[dict[str, Any]]) -> dict[str, Any]:
    caption = table["caption"] or f"table near line {table['line']}"
    label = _table_label(caption) or "unknown"
    rows: list[list[dict[str, Any]]] = table["rows"]
    locator_base = f"table:{label}"
    widths = [_logical_width(row) for row in rows if row]
    expected_width = max(widths, default=0)

    # Pair coefficient and t-statistic columns from the table header. The first
    # header row may contain period labels; actual data starts after the row
    # with the coefficient/statistic field names.
    header_pairs: list[tuple[int, int, int]] = []
    header_end = 0
    for row_no, row in enumerate(rows[:4], 1):
        texts = [re.sub(r"[^a-z]+", " ", _cell_text(row, i).lower()).strip() for i in range(len(row))]
        coefficient_cols = [i for i, text in enumerate(texts) if "coefficient" in text or text == "coef"]
        statistic_cols = [i for i, text in enumerate(texts) if "statistic" in text]
        if coefficient_cols or statistic_cols:
            header_end = row_no
        for coef_col in coefficient_cols:
            later = [j for j in statistic_cols if j > coef_col]
            if later:
                stat_col = min(later)
                pair = (coef_col, stat_col, _logical_width(row))
                if pair not in header_pairs:
                    header_pairs.append(pair)

    data_widths = [
        _logical_width(row) for row in rows[header_end:] if row
    ]
    expected_data_width = max(data_widths, default=expected_width)
    for row_no, row in enumerate(rows, 1):
        width = _logical_width(row)
        row_has_numeric = any(_number_tokens(_cell_text(row, j)) for j in range(len(row)))
        if row_no > header_end and row_has_numeric and width and expected_data_width and width != expected_data_width:
            _add_finding(
                findings, "table_row_width_mismatch", "critical",
                f"{locator_base}:row:{row_no}",
                f"Table row has {width} logical columns; widest row has {expected_width}.",
            )

        # Header dates such as 1993-98 legitimately contain two numeric
        # tokens in one cell. Lint only body rows, after recognized headers.
        if row_no <= header_end:
            continue
        for col_no, cell in enumerate(row, 1):
            values = _number_tokens(str(cell.get("text") or ""))
            if len(values) > 1:
                _add_finding(
                    findings, "multiple_numeric_values_in_cell", "critical",
                    f"{locator_base}:row:{row_no}:cell:{col_no}",
                    f"A table cell contains {len(values)} numeric values; inspect for a shifted or merged row.",
                    detail=str(cell.get("text") or "")[:100],
                )

    # Detect row-wrap/column-shift symptoms: a labeled, numerically empty row
    # is followed by a row containing numeric data. The label need not end in
    # punctuation; MinerU can split proper names at arbitrary positions.
    for i in range(max(header_end, 0), len(rows) - 1):
        row, nxt = rows[i], rows[i + 1]
        if not row or not nxt:
            continue
        label_text = _cell_text(row, 0).strip()
        next_label = _cell_text(nxt, 0).strip()
        values = [_cell_text(row, j).strip() for j in range(1, len(row))]
        next_values = [_cell_text(nxt, j).strip() for j in range(1, len(nxt))]
        row_has_number = any(_number_tokens(_cell_text(row, j)) for j in range(len(row)))
        if (
            label_text
            and not label_text.endswith(":")
            and not row_has_number
            and values
            and not any(values)
            and next_label
            and any(_number_tokens(v) for v in next_values)
        ):
            _add_finding(
                findings, "blank_labeled_row_followed_by_numeric_row", "warning",
                f"{locator_base}:row:{i + 1}",
                "A labeled row has no numeric cells and is followed by a numeric row; inspect for a split or shifted table row.",
                detail=f"{label_text} → {next_label}",
            )

    sign_disagreements = 0
    for row_no, row in enumerate(rows[header_end:], header_end + 1):
        for pair_no, (header_coef_col, header_stat_col, header_width) in enumerate(header_pairs, 1):
            # MinerU HTML may omit a leading rowspan cell from the repeated
            # header row; align the two header columns to the wider data row.
            offset = max(0, _logical_width(row) - header_width)
            coef_col = header_coef_col + offset
            stat_col = header_stat_col + offset
            if max(coef_col, stat_col) >= len(row):
                continue
            coef_tokens = _number_tokens(_cell_text(row, coef_col))
            stat_tokens = _number_tokens(_cell_text(row, stat_col))
            if len(coef_tokens) != 1 or len(stat_tokens) != 1:
                continue
            if coef_tokens[0][1] != stat_tokens[0][1]:
                sign_disagreements += 1
                _add_finding(
                    findings, "coefficient_tstat_sign_disagreement", "critical",
                    f"{locator_base}:row:{row_no}:pair:{pair_no}",
                    "Coefficient and t-statistic have opposite signs; verify against the rendered PDF page.",
                    detail=f"coefficient={_cell_text(row, coef_col).strip()}; t={_cell_text(row, stat_col).strip()}",
                )

    page_sign_mismatches = 0
    if page_text is not None:
        pdf_counts = Counter(_number_tokens(page_text))
        table_counts = Counter(
            token
            for row in rows
            for cell in row
            for token in _number_tokens(str(cell.get("text") or ""))
        )
        for (absolute, sign), count in table_counts.items():
            own = pdf_counts[(absolute, sign)]
            opposite = pdf_counts[(absolute, -sign)]
            if own == 0 and opposite > 0:
                page_sign_mismatches += 1
                _add_finding(
                    findings, "page_matched_numeric_sign_mismatch", "critical",
                    f"{locator_base}:number:{'-' if sign < 0 else '+'}{absolute}",
                    "A signed table value is absent on its matched PDF page while the opposite sign occurs there.",
                    detail=f"table count={count}; page opposite-sign count={opposite}",
                )

    return {
        "label": label,
        "line": table["line"],
        "page_idx": None,
        "row_count": len(rows),
        "logical_widths": widths,
        "coefficient_tstat_pairs": len(header_pairs),
        "coefficient_tstat_sign_disagreements": sign_disagreements,
        "page_sign_mismatches": page_sign_mismatches,
    }


def _content_list_data(manifest: dict[str, Any] | None) -> tuple[list[dict[str, Any]], str | None]:
    if not manifest:
        return [], None
    content_path = manifest.get("content_list_path")
    if not content_path:
        root = manifest.get("manifest_root")
        if root:
            candidates = sorted(Path(root).glob("out/*/txt/*_content_list.json"))
            content_path = str(candidates[0]) if candidates else None
    if not content_path:
        return [], None
    path = Path(content_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], None
    if not isinstance(raw, list):
        return [], None
    manifest["content_list_path"] = str(path)
    # Preserve the parser's declared hash. Store the observed hash separately
    # so a later report cannot legitimize content changed after the parse.
    manifest["content_list_sha256_actual"] = sha256_file(path)
    return [x for x in raw if isinstance(x, dict)], str(path)


def _map_table_pages(tables: list[dict[str, Any]], content_list: list[dict[str, Any]]) -> None:
    table_blocks = [item for item in content_list if item.get("type") == "table"]
    for table in tables:
        label = _table_label(table.get("caption", ""))
        if not label:
            continue
        for item in table_blocks:
            caption = " ".join(map(str, item.get("table_caption") or []))
            raw_label = _table_label(caption)
            if raw_label == label and isinstance(item.get("page_idx"), int):
                table["page_idx"] = item["page_idx"]
                break


def _figure_report(sidecar: str, content_list: list[dict[str, Any]], pdf_path: Path, findings: list[dict[str, Any]]) -> dict[str, Any]:
    refs = list(_IMAGE_REF_RE.finditer(sidecar))
    schemas = 0
    leaked: list[str] = []
    missing_schema: list[str] = []
    sidecar_lines = sidecar.splitlines()
    for match in refs:
        image_path = match.group(1).split()[0]
        line_no = sidecar.count("\n", 0, match.start())
        schema_lines: list[str] = []
        found = False
        for line in sidecar_lines[line_no + 1:min(line_no + 10, len(sidecar_lines))]:
            if "[Figure Schema]" in line:
                found = True
                schemas += 1
                continue
            if found and line.strip().startswith("- "):
                schema_lines.append(line)
            elif found and line.strip():
                break
        if not found:
            missing_schema.append(image_path)
            _add_finding(
                findings, "figure_schema_missing", "critical",
                f"figure:{image_path}",
                "An indexed image reference has no adjacent figure schema; determine whether it is a figure and whether enrichment is required.",
            )
        schema_text = " ".join(schema_lines).lower()
        caption_match = re.search(r"-\s*Caption:\s*(.+)", schema_text, re.I)
        caption = caption_match.group(1).strip() if caption_match else ""
        for phrase in _FIGURE_SCHEMA_LEAKS:
            if phrase in schema_text:
                leaked.append(image_path)
                _add_finding(
                    findings, "figure_prompt_example_leak", "critical",
                    f"figure:{image_path}",
                    "A figure schema contains wording copied from a generic prompt example; verify and remove unsupported content.",
                    detail=phrase,
                )
                break
    content_images = [item for item in content_list if item.get("type") == "image"]
    image_paths = {str(item.get("img_path") or "") for item in content_images}
    unmatched_refs = [m.group(1).split()[0] for m in refs if m.group(1).split()[0] not in image_paths]
    if unmatched_refs:
        for image_path in unmatched_refs:
            _add_finding(
                findings, "sidecar_image_not_in_content_list", "warning",
                f"figure:{image_path}",
                "The sidecar image reference has no matching page-indexed MinerU image record.",
            )

    # Raster-image coverage is a lower bound only. Vector figures cannot be
    # ruled out by this test, so a zero result is recorded as unknown, not none.
    raster_by_page: dict[int, int] = {}
    try:
        import fitz
        doc = fitz.open(pdf_path)
        try:
            for page_idx, page in enumerate(doc):
                raster_by_page[page_idx] = len(page.get_images(full=True))
        finally:
            doc.close()
    except Exception as exc:
        logger.warning("sidecar quality: raster coverage probe failed: %s", exc)
    image_pages = {
        item.get("page_idx") for item in content_images
        if isinstance(item.get("page_idx"), int)
    }
    raster_pages_without_crops = [
        page_idx for page_idx, count in raster_by_page.items()
        if count and page_idx not in image_pages
    ]
    for page_idx in raster_pages_without_crops:
        _add_finding(
            findings, "pdf_raster_image_page_not_in_mineru", "critical",
            f"page:{page_idx + 1}",
            "The PDF contains raster image content on this page but MinerU produced no page-indexed image crop.",
        )
    return {
        "sidecar_image_references": len(refs),
        "adjacent_schemas": schemas,
        "missing_schema_images": missing_schema,
        "prompt_example_leak_images": leaked,
        "content_list_image_records": len(content_images),
        "unmatched_sidecar_image_references": unmatched_refs,
        "pdf_raster_image_pages": [i + 1 for i, n in raster_by_page.items() if n],
        "raster_pages_without_mineru_crops": [i + 1 for i in raster_pages_without_crops],
        "vector_figure_coverage": "not_assessed",
    }


def _status(findings: list[dict[str, Any]], fatal: bool = False) -> str:
    if fatal:
        return "failed"
    if any(f.get("severity") == "critical" for f in findings):
        return "review_required"
    return "eligible"


def build_quality_report(
    item_key: str,
    cfg: dict[str, Any],
    reader: Any,
    attachment_key: str | None = None,
) -> dict[str, Any]:
    """Screen a sidecar and return a provenance-bound report (does not write)."""
    sidecar_path = Path(cfg["sidecar_dir"]) / f"{item_key}.md"
    findings: list[dict[str, Any]] = []
    fatal = False
    report: dict[str, Any] = {
        "report_schema": REPORT_SCHEMA,
        "check_version": CHECK_VERSION,
        "item_key": item_key,
        "sidecar_path": str(sidecar_path),
        "status": "failed",
        "eligibility_basis": "automated_screen_only_not_human_verification",
        "findings": findings,
    }
    try:
        if not sidecar_path.is_file():
            raise SidecarQualityError(f"sidecar is missing: {sidecar_path}")
        sidecar_bytes = sidecar_path.read_bytes()
        sidecar = sidecar_bytes.decode("utf-8", errors="strict")
        report["sidecar_sha256"] = _sha256_bytes(sidecar_bytes)
        report["sidecar_bytes"] = len(sidecar_bytes)
        selected_attachment, pdf_path = _choose_pdf(reader, item_key, attachment_key)
        pdf_hash = sha256_file(pdf_path)
        report.update({
            "attachment_key": selected_attachment,
            "pdf_path": str(pdf_path),
            "pdf_sha256": pdf_hash,
        })
    except Exception as exc:
        fatal = True
        _add_finding(findings, "quality_input_unavailable", "critical", "item", str(exc))
        report["status"] = _status(findings, fatal=True)
        return report

    manifest = _parser_manifest(cfg, item_key, pdf_hash)
    raw_markdown_actual_hash = None
    raw_markdown_path = (manifest or {}).get("raw_markdown_path")
    raw_markdown_declared_hash = (manifest or {}).get("raw_markdown_sha256")
    if manifest is not None:
        if not raw_markdown_path or not raw_markdown_declared_hash:
            if manifest.get("parser_version"):
                _add_finding(
                    findings, "raw_markdown_provenance_missing", "critical", "provenance",
                    "The run manifest does not declare a raw Markdown path and SHA-256 hash.",
                )
        else:
            try:
                raw_markdown_actual_hash = sha256_file(raw_markdown_path)
            except OSError as exc:
                _add_finding(
                    findings, "raw_markdown_missing_or_unreadable", "critical", "provenance",
                    f"The manifest-bound raw Markdown artifact is unavailable: {exc}",
                )
            else:
                if raw_markdown_actual_hash != raw_markdown_declared_hash:
                    _add_finding(
                        findings, "raw_markdown_hash_mismatch", "critical", "provenance",
                        "The preserved raw Markdown does not match the SHA-256 declared in its run manifest.",
                    )
    report["parser"] = {
        "version": (manifest or {}).get("parser_version"),
        "manifest_path": (manifest or {}).get("manifest_path"),
        "manifest_sha256": (manifest or {}).get("manifest_sha256"),
        "raw_markdown_path": raw_markdown_path,
        "raw_markdown_sha256": raw_markdown_declared_hash,
        "raw_markdown_sha256_actual": raw_markdown_actual_hash,
        "legacy_artifacts": bool((manifest or {}).get("legacy_artifacts")),
    }
    content_list, content_list_path = _content_list_data(manifest)
    content_list_declared_hash = (manifest or {}).get("content_list_sha256")
    content_list_actual_hash = (manifest or {}).get("content_list_sha256_actual")
    if manifest is not None and content_list_path:
        if manifest.get("parser_version") and not content_list_declared_hash:
            _add_finding(
                findings, "content_list_provenance_missing", "critical", "provenance",
                "The run manifest does not declare a page-indexed content-list SHA-256 hash.",
            )
        elif content_list_declared_hash and content_list_declared_hash != content_list_actual_hash:
            _add_finding(
                findings, "content_list_hash_mismatch", "critical", "provenance",
                "The page-indexed content list does not match the SHA-256 declared in its run manifest.",
            )
    if manifest is None:
        _add_finding(
            findings, "raw_parse_manifest_missing", "critical", "provenance",
            "No preserved raw MinerU run manifest was found for the current PDF; parser version and page-indexed source could not be bound.",
        )
    elif not content_list:
        _add_finding(
            findings, "content_list_missing_or_unreadable", "critical", "provenance",
            "No readable page-indexed content_list.json was found for the raw MinerU parse.",
        )
    elif not manifest.get("parser_version"):
        _add_finding(
            findings, "parser_version_unknown", "critical", "provenance",
            "The sidecar predates the run manifest or its parser version is unknown; provenance needs review.",
        )
    if content_list_path:
        report["content_list"] = {
            "path": content_list_path,
            "manifest_sha256": content_list_declared_hash,
            "sha256": content_list_actual_hash,
            "page_count": len({x.get("page_idx") for x in content_list if isinstance(x.get("page_idx"), int)}),
            "block_count": len(content_list),
        }

    try:
        import fitz
        pdf = fitz.open(pdf_path)
        try:
            pdf_pages = [page.get_text("text") or "" for page in pdf]
            report["pdf_page_count"] = len(pdf_pages)
        finally:
            pdf.close()
    except Exception as exc:
        pdf_pages = []
        _add_finding(
            findings, "pdf_text_layer_unavailable", "critical", "pdf",
            f"Could not extract a page-indexed PDF text layer for mechanical comparison: {type(exc).__name__}: {exc}",
        )

    tables = _extract_tables(sidecar)
    _map_table_pages(tables, content_list)
    table_summaries: list[dict[str, Any]] = []
    for table in tables:
        page_idx = table.get("page_idx")
        page_text = pdf_pages[page_idx] if isinstance(page_idx, int) and 0 <= page_idx < len(pdf_pages) else None
        summary = _check_table(table, page_text, findings)
        summary["page_idx"] = page_idx
        table_summaries.append(summary)
        if page_text is None:
            _add_finding(
                findings, "table_page_unmatched", "critical",
                f"table:{_table_label(table.get('caption', '')) or 'unknown'}",
                "The sidecar table could not be mapped to the page-indexed MinerU/PDF source; page-matched numeric checks were not run.",
            )
    report["tables"] = table_summaries
    report["figure_coverage"] = _figure_report(sidecar, content_list, pdf_path, findings)

    report["checks"] = {
        "tables_screened": len(tables),
        "page_matched_tables": sum(t.get("page_idx") is not None for t in tables),
        "coefficient_tstat_sign_disagreements": sum(t["coefficient_tstat_sign_disagreements"] for t in table_summaries),
        "page_matched_numeric_sign_mismatches": sum(t["page_sign_mismatches"] for t in table_summaries),
        "manual_visual_review_performed": False,
        "figure_semantics_verified": False,
        "vector_figure_coverage_verified": False,
    }
    report["status"] = _status(findings)
    return report


def write_quality_report(report: dict[str, Any], cfg: dict[str, Any]) -> Path:
    path = quality_report_path(cfg, str(report["item_key"]))
    if path.is_file():
        import shutil
        import time
        history = Path(cfg["sidecar_dir"]) / ".quality-history" / str(report["item_key"])
        archived = history / f"{time.time_ns()}.json"
        history.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, archived)
        report["previous_report_path"] = str(archived)
    _atomic_json(path, report)
    return path


def verify_current_report(
    item_key: str,
    cfg: dict[str, Any],
    reader: Any,
    sidecar_text: str | None = None,
) -> dict[str, Any]:
    """Require a current eligible report; raises rather than falling back."""
    path = quality_report_path(cfg, item_key)
    if not path.is_file():
        raise SidecarQualityError(
            f"sidecar quality report missing for {item_key}: {path}; run zotero-sidecar.sh check {item_key}"
        )
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SidecarQualityError(f"quality report unreadable for {item_key}: {exc}") from exc
    if report.get("report_schema") != REPORT_SCHEMA or report.get("check_version") != CHECK_VERSION:
        raise SidecarQualityError(
            f"quality report is stale for {item_key} (schema/check version mismatch); rerun the sidecar check"
        )
    sidecar_path = Path(cfg["sidecar_dir"]) / f"{item_key}.md"
    if not sidecar_path.is_file():
        raise SidecarQualityError(f"quality gate: sidecar disappeared for {item_key}: {sidecar_path}")
    current_sidecar_hash = _sha256_bytes(sidecar_text.encode("utf-8")) if sidecar_text is not None else sha256_file(sidecar_path)
    try:
        attachment_key, pdf_path = _choose_pdf(reader, item_key, report.get("attachment_key"))
        current_pdf_hash = sha256_file(pdf_path)
    except Exception as exc:
        raise SidecarQualityError(f"quality gate cannot resolve the reported PDF for {item_key}: {exc}") from exc
    if report.get("attachment_key") != attachment_key:
        raise SidecarQualityError(f"quality report attachment changed for {item_key}; rerun the sidecar check")
    if report.get("sidecar_sha256") != current_sidecar_hash:
        raise SidecarQualityError(f"quality report is stale after a sidecar change for {item_key}; rerun the sidecar check")
    if report.get("pdf_sha256") != current_pdf_hash:
        raise SidecarQualityError(f"quality report is stale after a PDF change for {item_key}; rerun the sidecar check")
    parser_report = report.get("parser", {})
    if parser_report.get("version") is None:
        raise SidecarQualityError(f"quality report has no verified parser version for {item_key}; review provenance")
    manifest = _parser_manifest(cfg, item_key, current_pdf_hash, parser_report.get("manifest_path"))
    if manifest is None:
        raise SidecarQualityError(f"raw parse provenance disappeared for {item_key}; rerun the sidecar check")
    if report.get("parser", {}).get("manifest_path") != manifest.get("manifest_path"):
        raise SidecarQualityError(f"raw parse changed for {item_key}; rerun the sidecar check")
    if parser_report.get("manifest_sha256") != manifest.get("manifest_sha256"):
        raise SidecarQualityError(f"raw parse manifest changed for {item_key}; rerun the sidecar check")
    raw_markdown_path = manifest.get("raw_markdown_path")
    raw_markdown_declared_hash = manifest.get("raw_markdown_sha256")
    if not raw_markdown_path or not raw_markdown_declared_hash:
        raise SidecarQualityError(f"raw Markdown provenance is missing for {item_key}; review the parse")
    try:
        raw_markdown_actual_hash = sha256_file(raw_markdown_path)
    except OSError as exc:
        raise SidecarQualityError(f"raw Markdown artifact is unavailable for {item_key}: {exc}") from exc
    if raw_markdown_actual_hash != raw_markdown_declared_hash:
        raise SidecarQualityError(f"raw Markdown artifact changed for {item_key}; rerun the sidecar check")
    if (
        parser_report.get("raw_markdown_sha256") != raw_markdown_declared_hash
        or parser_report.get("raw_markdown_sha256_actual") != raw_markdown_actual_hash
    ):
        raise SidecarQualityError(f"raw Markdown provenance changed for {item_key}; rerun the sidecar check")
    content_list, content_list_path = _content_list_data(manifest)
    current_content_list_hash = manifest.get("content_list_sha256_actual")
    declared_content_list_hash = manifest.get("content_list_sha256")
    recorded_content = report.get("content_list") or {}
    if not content_list or not content_list_path:
        raise SidecarQualityError(f"page-indexed MinerU source is unavailable for {item_key}; rerun the sidecar check")
    if not declared_content_list_hash or declared_content_list_hash != current_content_list_hash:
        raise SidecarQualityError(f"page-indexed source does not match its run manifest for {item_key}; review provenance")
    if (
        recorded_content.get("sha256") != current_content_list_hash
        or recorded_content.get("manifest_sha256") != declared_content_list_hash
    ):
        raise SidecarQualityError(f"page-indexed MinerU source changed for {item_key}; rerun the sidecar check")
    if report.get("status") != "eligible":
        blocked = [f"{f.get('id')} {f.get('code')} ({f.get('locator')})" for f in report.get("findings", []) if f.get("severity") == "critical"]
        sample = "; ".join(blocked[:5]) or report.get("status")
        raise SidecarQualityError(
            f"sidecar {item_key} is not eligible for indexing ({report.get('status')}): {sample}"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Screen MinerU sidecars and manage provenance-bound quality reports")
    parser.add_argument("action", choices=("check", "eligible"), help="check writes a report; eligible only verifies existing reports")
    parser.add_argument("item_keys", nargs="+", help="exact Zotero parent-item keys")
    parser.add_argument("--attachment-key", help="pin one PDF attachment (only for one item)")
    parser.add_argument("--dry-run", action="store_true", help="print reports without writing them")
    args = parser.parse_args(argv)
    if args.attachment_key and (len(args.item_keys) != 1 or args.action != "check"):
        parser.error("--attachment-key is allowed only for one item with the check action")

    try:
        from zotero_mcp import mineru
        from zotero_mcp.local_db import LocalZoteroReader
        cfg = mineru.load_mineru_config()
        raw_config_path = os.environ.get("ZOTERO_MCP_CONFIG", str(Path.home() / ".config/zotero-mcp/config.json"))
        try:
            raw_cfg = json.loads(Path(raw_config_path).read_text(encoding="utf-8"))
            db_path = raw_cfg.get("semantic_search", {}).get("zotero_db_path")
        except Exception:
            db_path = None
        reader = LocalZoteroReader(db_path=db_path)
    except Exception as exc:
        print(f"ERROR: could not initialize local Zotero reader: {exc}")
        return 2

    exit_code = 0
    try:
        for key in args.item_keys:
            try:
                if args.action == "eligible":
                    report = verify_current_report(key, cfg, reader)
                    print(json.dumps({"item_key": key, "status": report["status"], "eligible": True}, ensure_ascii=False))
                else:
                    report = build_quality_report(key, cfg, reader, args.attachment_key)
                    path = None if args.dry_run else write_quality_report(report, cfg)
                    report["report_path"] = str(path) if path else None
                    print(json.dumps(report, ensure_ascii=False, indent=2))
                    if report.get("status") != "eligible":
                        exit_code = 1
            except Exception as exc:
                print(f"ERROR {key}: {type(exc).__name__}: {exc}")
                exit_code = 1
    finally:
        close = getattr(reader, "close", None)
        if callable(close):
            close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
