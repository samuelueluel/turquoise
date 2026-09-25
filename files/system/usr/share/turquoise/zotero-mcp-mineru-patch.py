#!/usr/bin/env python3
"""Idempotently apply the zotero-mcp auto-MinerU patch.

Why: zotero semantic search extracts text-layer PDF text only, so equations
arrive as garbled Unicode and tables as run-on text. This patch slots MinerU
(magic-pdf) in before embedding: for every item being (re)embedded that has a
PDF and no cached sidecar, MinerU parses it, the sidecar Markdown becomes the
embedded fulltext, and answer-time fulltext reads prefer the sidecar.

Files (all in the zotero_mcp package dir passed as argv[1]):
- mineru.py               copied from zotero-mcp-mineru.py next to this script
- semantic_search.py      import + current extraction-batch hook
- tools/retrieval.py      import + sidecar preference in get_item_fulltext
- tools/search.py         embedder pre-check warning

Marker comment: "[mineru patch]". Re-applied by sjust update; see
General-Tooling §3.2.5 and MinerU-Setup.md.
Usage: zotero-mcp-mineru-patch.py <path/to/zotero_mcp-package-dir>
Prints: "applied" | "already" | "mismatch" (mismatch exits 1).
"""
import shutil
import sys
from pathlib import Path

pkg = Path(sys.argv[1])
here = Path(__file__).resolve().parent
src_mineru = here / "zotero-mcp-mineru.py"
src_sidecar_quality = here / "zotero-mcp-sidecar-quality.py"

errors: list[str] = []
changed = False

# --- 1. mineru.py ----------------------------------------------------------
# This module is wholly owned by the patch, so synchronize it on every
# application.  Checking only for existence left an older patched copy in
# place after the MinerU 3.x update and prevented bug fixes from deploying.
target_mineru = pkg / "mineru.py"
if not src_mineru.exists():
    errors.append("mineru.py source (zotero-mcp-mineru.py) not found next to this script")
else:
    try:
        needs_copy = (
            not target_mineru.exists()
            or target_mineru.read_bytes() != src_mineru.read_bytes()
        )
    except OSError as e:
        errors.append(f"could not compare mineru.py: {e}")
        needs_copy = False
    if needs_copy:
        shutil.copy2(src_mineru, target_mineru)
        changed = True


# --- 1b. sidecar_quality.py ------------------------------------------------
target_quality = pkg / "sidecar_quality.py"
if not src_sidecar_quality.exists():
    errors.append("sidecar_quality.py source (zotero-mcp-sidecar-quality.py) not found next to this script")
else:
    try:
        needs_copy = (
            not target_quality.exists()
            or target_quality.read_bytes() != src_sidecar_quality.read_bytes()
        )
    except OSError as e:
        errors.append(f"could not compare sidecar_quality.py: {e}")
        needs_copy = False
    if needs_copy:
        shutil.copy2(src_sidecar_quality, target_quality)
        changed = True


def _apply(path: Path, edits: list[tuple[str, str]], name: str) -> None:
    """Apply edits to a file only when every anchor is present (all-or-nothing)."""
    global changed
    if "[mineru patch]" in path.read_text(encoding="utf-8"):
        return  # already patched
    src = path.read_text(encoding="utf-8")
    work = src
    for old, new in edits:
        if old in work:
            work = work.replace(old, new, 1)
        else:
            errors.append(f"{name} anchor missing")
            return
    path.write_text(work, encoding="utf-8")
    changed = True


# --- 2. semantic_search.py -------------------------------------------------
ss = pkg / "semantic_search.py"
if ss.exists():
    _apply(ss, [
        (
            "from .local_db import PERSONAL_LIBRARY_GROUP_ID, LocalZoteroReader",
            "from .local_db import PERSONAL_LIBRARY_GROUP_ID, LocalZoteroReader\n"
            "from . import mineru as _mineru  # [mineru patch] auto-MinerU before embedding (see zotero-mcp-mineru-patch.py)",
        ),
        (
            '''def _extract_fulltext_batch(reader, items):
    """Yield ``(item_id, (text, source) | None)`` for every item in ``items``.

    Prefers the reader's batch API, which parallelises across a process pool
    when configured. Falls back to one call per item for readers that do not
    provide it — the minimal doubles used in tests implement only
    ``extract_fulltext_for_item(item_id)``, and they should not have to grow
    a new method just because the real reader gained a faster path.
    """
    batch = getattr(reader, "extract_fulltext_for_items", None)
    if batch is not None:
        yield from batch(items)
        return
    for item_id, _item_key in items:
        yield item_id, reader.extract_fulltext_for_item(item_id)
''',
            '''def _extract_fulltext_batch(reader, items):
    """Yield ``(item_id, (text, source) | None)`` for every item in ``items``.

    [mineru patch] Use cached MinerU sidecars when present and, when enabled,
    parse PDFs before falling back to the normal text-layer extractor. The
    unmodified batch path is retained when MinerU is disabled and no sidecar
    exists, preserving the reader's process-pool extraction behavior.
    """
    items = list(items)
    mineru_config = _mineru.load_mineru_config()
    sidecars = [
        (item_id, item_key, _mineru.read_sidecar(mineru_config, item_key))
        for item_id, item_key in items
    ]

    # Keep the upstream batch extractor on the ordinary path. A cached sidecar
    # or enabled auto-MinerU intentionally opts into the per-item path below.
    if not mineru_config.get("enabled") and not any(
        text is not None for _item_id, _item_key, text in sidecars
    ):
        batch = getattr(reader, "extract_fulltext_for_items", None)
        if batch is not None:
            yield from batch(items)
            return
        for item_id, _item_key in items:
            yield item_id, reader.extract_fulltext_for_item(item_id)
        return

    for item_id, item_key, sidecar in sidecars:
        if sidecar is not None:
            yield item_id, (sidecar, "mineru-sidecar")
            continue
        mineru_fulltext = _mineru.try_auto_parse(item_key, reader)
        if mineru_fulltext:
            yield item_id, mineru_fulltext
        else:
            yield item_id, reader.extract_fulltext_for_item(item_id)
''',
        ),
    ], "semantic_search.py")
else:
    errors.append("semantic_search.py not found")

# --- 3. tools/retrieval.py -------------------------------------------------
rv = pkg / "tools" / "retrieval.py"
if rv.exists():
    _apply(rv, [
        (
            "from zotero_mcp import client as _client\nfrom zotero_mcp import utils as _utils\n",
            "from zotero_mcp import client as _client\n"
            "from zotero_mcp import utils as _utils\n"
            "from zotero_mcp import mineru as _mineru  # [mineru patch] sidecar preference for fulltext reads\n",
        ),
        (
            "                    local_item = reader.get_item_by_key(item_key)\n"
            "                    if local_item:\n"
            "                        extracted = reader.extract_fulltext_for_item(local_item.item_id)",
            "                    local_item = reader.get_item_by_key(item_key)\n"
            "                    if local_item:\n"
            "                        # [mineru patch] prefer the MinerU sidecar (clean equations/tables) when present\n"
            "                        _mineru_text = _mineru.read_sidecar(_mineru.load_mineru_config(), item_key)\n"
            "                        if _mineru_text:\n"
            "                            ctx.info(\"Retrieved full text from MinerU sidecar\")\n"
            "                            return _helpers._prepend_size_warning(\n"
            "                                f\"{metadata}\\n\\n---\\n\\n## Full Text\\n\\n{_mineru_text}\",\n"
            "                                \"Consider using zotero_semantic_search to find specific content instead of reading full papers.\"\n"
            "                            )\n"
            "                        extracted = reader.extract_fulltext_for_item(local_item.item_id)",
        ),
    ], "tools/retrieval.py")
else:
    errors.append("tools/retrieval.py not found")

# --- 4. tools/search.py (embedder pre-check warning) -------------------------
sc = pkg / "tools" / "search.py"
if sc.exists():
    _apply(sc, [
        (
            '        ctx.info("Starting semantic search database update...")\n\n'
            '        # Import semantic search module',
            '        ctx.info("Starting semantic search database update...")\n\n'
            '        # [mineru patch] pre-check the embedding backend so a dead embedder\n'
            '        # produces an actionable message instead of a pile of upsert errors\n'
            '        embedder_warning = ""\n'
            '        try:\n'
            '            import json as _json\n'
            '            import urllib.request as _ur\n'
            '            _cfg = _json.loads((Path.home() / ".config" / "zotero-mcp" / "config.json").read_text(encoding="utf-8"))\n'
            '            _ss = _cfg.get("semantic_search", {}) or {}\n'
            '            _ec = _ss.get("embedding_config", {}) or {}\n'
            '            _url = (_ec.get("base_url") or "").rstrip("/")\n'
            '            if _ss.get("embedding_model") == "openai" and _url:\n'
            '                try:\n'
            '                    with _ur.urlopen(_url + "/models", timeout=2):\n'
            '                        pass\n'
            '                except Exception:\n'
            '                    embedder_warning = (\n'
            '                        "\\n\\n⚠️ The embedding backend at %s is unreachable.\\n"\n'
            '                        "MinerU parses still ran and sidecars are saved (nothing lost), but the "\n'
            '                        "embedding/upsert phase FAILED. Start it with `serve-embedder`, then "\n'
            '                        "re-run this update to finish indexing." % _url\n'
            '                    )\n'
            '                    ctx.info(\n'
            '                        "Embedder at %s is down; parses will run but embedding will fail. "\n'
            '                        "Start it with `serve-embedder` and re-run." % _url\n'
            '                    )\n'
            '        except Exception:\n'
            '            pass\n\n'
            '        # Import semantic search module',
        ),
        (
            '            if stats.get(\'start_time\'):\n'
            '                output.append(f"**Started:** {stats[\'start_time\']}")\n'
            '            if stats.get(\'end_time\'):\n'
            '                output.append(f"**Completed:** {stats[\'end_time\']}")\n\n'
            '        return "\\n".join(output)',
            '            if stats.get(\'start_time\'):\n'
            '                output.append(f"**Started:** {stats[\'start_time\']}")\n'
            '            if stats.get(\'end_time\'):\n'
            '                output.append(f"**Completed:** {stats[\'end_time\']}")\n\n'
            '        if embedder_warning:\n'
            '            output.append(embedder_warning)\n\n'
            '        return "\\n".join(output)',
        ),
    ], "tools/search.py")
else:
    errors.append("tools/search.py not found")

# --- 5. shared sidecar eligibility gate -----------------------------------
if ss.exists():
    src = ss.read_text(encoding="utf-8")
    quality_import = "from . import sidecar_quality as _sidecar_quality  # [sidecar quality patch] shared pre-index eligibility gate"
    if "[sidecar quality patch]" not in src:
        mineru_import = "from . import mineru as _mineru  # [mineru patch] auto-MinerU before embedding (see zotero-mcp-mineru-patch.py)"
        if mineru_import not in src:
            errors.append("semantic_search.py quality import anchor missing")
        else:
            start = src.find("def _extract_fulltext_batch(reader, items):")
            end = src.find("\n\n#: End-of-stream marker", start)
            if start < 0 or end < 0:
                errors.append("semantic_search.py extraction function boundaries missing")
            else:
                new_function = '''def _extract_fulltext_batch(reader, items):
    """Yield fulltext only after any MinerU sidecar passes its current gate.

    [sidecar quality patch] A rejected sidecar raises before item chunks are
    prepared/deleted. Never fall back to another text route after a sidecar is
    missing, stale, or review-required.
    """
    items = list(items)
    mineru_config = _mineru.load_mineru_config()
    sidecars = [
        (item_id, item_key, _mineru.read_sidecar(mineru_config, item_key))
        for item_id, item_key in items
    ]

    # Retain the upstream batch extractor when the MinerU sidecar path is not
    # in use; ordinary non-sidecar documents need no sidecar-quality report.
    sidecar_present = any(
        _mineru.sidecar_path(mineru_config, item_key).exists()
        or _sidecar_quality.quality_report_path(mineru_config, item_key).exists()
        for _item_id, item_key in items
    )
    if not mineru_config.get("enabled") and not any(
        text is not None for _item_id, _item_key, text in sidecars
    ) and not sidecar_present:
        batch = getattr(reader, "extract_fulltext_for_items", None)
        if batch is not None:
            yield from batch(items)
            return
        for item_id, _item_key in items:
            yield item_id, reader.extract_fulltext_for_item(item_id)
        return

    for item_id, item_key, sidecar in sidecars:
        sidecar_path = _mineru.sidecar_path(mineru_config, item_key)
        if sidecar_path.exists() and sidecar is None:
            raise _sidecar_quality.SidecarQualityError(
                f"sidecar exists but cannot be read for {item_key}; refusing unaudited fallback"
            )
        if sidecar is None and _sidecar_quality.quality_report_path(mineru_config, item_key).exists():
            raise _sidecar_quality.SidecarQualityError(
                f"quality report exists but sidecar is missing for {item_key}; refusing unaudited fallback"
            )
        if sidecar is not None:
            _sidecar_quality.verify_current_report(
                item_key, mineru_config, reader, sidecar_text=sidecar
            )
            yield item_id, (sidecar, "mineru-sidecar")
            continue

        if mineru_config.get("enabled"):
            try:
                attachments = reader.get_attachment_paths(item_key)
            except Exception as exc:
                raise _sidecar_quality.SidecarQualityError(
                    f"could not resolve PDF attachments for {item_key}; refusing unaudited fallback: {exc}"
                ) from exc
            pdf_attachments = [
                (str(att.get("key") or ""), Path(att["resolved_path"]))
                for att in attachments
                if att.get("resolved_path")
                and str(att.get("resolved_path")).lower().endswith(".pdf")
                and Path(att["resolved_path"]).is_file()
            ]
            has_pdf = bool(pdf_attachments)
        else:
            has_pdf = False
        if has_pdf:
            parsed = _mineru.try_auto_parse(item_key, reader)
            if parsed is None:
                raise _sidecar_quality.SidecarQualityError(
                    f"MinerU parse failed for {item_key}; refusing fallback to an unaudited text route"
                )
            text, _source = parsed
            attachment_key = pdf_attachments[0][0] if len(pdf_attachments) == 1 else None
            report = _sidecar_quality.build_quality_report(
                item_key, mineru_config, reader, attachment_key=attachment_key
            )
            _sidecar_quality.write_quality_report(report, mineru_config)
            _sidecar_quality.verify_current_report(
                item_key, mineru_config, reader, sidecar_text=text
            )
            yield item_id, parsed
            continue
        yield item_id, reader.extract_fulltext_for_item(item_id)
'''
                src = src[:start] + new_function + src[end:]
                src = src.replace(mineru_import, mineru_import + "\n" + quality_import, 1)
                ss.write_text(src, encoding="utf-8")
                changed = True

    # Defer destructive force-rebuild reset until fulltext extraction has
    # completed, so a quality-gate rejection leaves the current index intact.
    src = ss.read_text(encoding="utf-8")
    if "reset_after_quality_preflight = force_full_rebuild and not batch_enabled" not in src:
        reset_early = '''            if force_full_rebuild and not batch_enabled:
                logger.info("Force rebuilding database...")
                self.chroma_client.reset_collection()
'''
        if reset_early not in src:
            errors.append("semantic_search.py early force-rebuild reset anchor missing")
        else:
            src = src.replace(
                reset_early,
                "            reset_after_quality_preflight = force_full_rebuild and not batch_enabled\n",
                1,
            )
            before_indexing = '''                    if extract_fulltext and target_sync_version is not None:
                        target_sync_version = self._verify_local_snapshot_version(
                            target_sync_version
                        )

            stats["total_items"] = len(all_items)
'''
            after_preflight = '''                    if extract_fulltext and target_sync_version is not None:
                        target_sync_version = self._verify_local_snapshot_version(
                            target_sync_version
                        )

            if reset_after_quality_preflight:
                logger.info("Force rebuilding database after extraction and sidecar preflight...")
                self.chroma_client.reset_collection()

            stats["total_items"] = len(all_items)
'''
            if before_indexing not in src:
                errors.append("semantic_search.py deferred-reset insertion anchor missing")
            else:
                src = src.replace(before_indexing, after_preflight, 1)
                ss.write_text(src, encoding="utf-8")
                changed = True

else:
    errors.append("semantic_search.py not found for sidecar quality patch")

# Preserve a quality-gate rejection through ordinary local-DB fallback and
# update-database error handling. Other local database errors still use the
# upstream API fallback unchanged.
if ss.exists():
    src = ss.read_text(encoding="utf-8")
    local_marker = "[sidecar quality rejection: do not fall back to API]"
    local_catch = '''        except Exception as e:
            logger.error(f"Error reading from local database: {e}")
            logger.info("Falling back to API...")
            return self._get_items_from_api(limit, item_keys=item_keys)
'''
    if local_marker not in src:
        if local_catch not in src:
            errors.append("semantic_search.py local-DB fallback catch anchor missing")
        else:
            src = src.replace(
                local_catch,
                '''        except _sidecar_quality.SidecarQualityError:  # [sidecar quality rejection: do not fall back to API]
            raise
''' + local_catch,
                1,
            )
    update_marker = "[sidecar quality rejection: propagate update failure]"
    update_catch = '''        except Exception as e:
            logger.error(f"Error updating database: {e}")
            stats["error"] = str(e)
'''
    if update_marker not in src:
        if update_catch not in src:
            errors.append("semantic_search.py update-database exception catch anchor missing")
        else:
            src = src.replace(
                update_catch,
                '''        except _sidecar_quality.SidecarQualityError:  # [sidecar quality rejection: propagate update failure]
            raise
''' + update_catch,
                1,
            )
    ss.write_text(src, encoding="utf-8")

if errors:
    print("mismatch: " + "; ".join(errors))
    sys.exit(1)

print("applied" if changed else "already")
