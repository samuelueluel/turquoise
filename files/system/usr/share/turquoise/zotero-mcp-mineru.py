"""Auto-MinerU integration for zotero-mcp.  # [mineru patch]

Parses item PDFs with MinerU (magic-pdf) BEFORE embedding so equations come
out as LaTeX and tables as HTML instead of garbled Unicode. Sidecars are
cached per item at ``<sidecar_dir>/<item_key>.md`` and reused; the parse
runs once per item (policy: always for PDFs lacking a sidecar).

Hook points:
- ``semantic_search.py`` extraction block: ``try_auto_parse()`` runs before
  text-layer extraction for items being (re)embedded.
- ``tools/retrieval.py`` ``get_item_fulltext``: ``read_sidecar()`` is
  preferred over text-layer extraction so answer-time reads show the clean
  MinerU text.

Config (``~/.config/zotero-mcp/config.json`` -> ``semantic_search.mineru``):
- enabled: bool (default false; flip true once verified)
- bin: MinerU CLI binary (default ~/mineru-upgrade-venv/bin/mineru)
- config_json: optional CLI config path exported as MINERU_TOOLS_CONFIG_JSON
- sidecar_dir: sidecar cache dir (default ~/.config/zotero-mcp/mineru-sidecars)
- work_dir: per-item magic-pdf work dir (default ~/.cache/zotero-mcp/mineru-work)
- timeout_seconds: per-parse cap (default 3600)

Re-applied idempotently by zotero-mcp-mineru-patch.py via ``sjust update``;
see General-Tooling and MinerU-Setup.md. Requires the mineru-rocm-venv
(mineru setup memory note) and the ch-family models_config.yml rewire.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

logger = logging.getLogger("zotero_mcp.mineru")

MARKER = "[mineru patch]"


def load_mineru_config(config_path: str | None = None) -> dict:
    """Read the ``semantic_search.mineru`` section from config.json (raw JSON).

    Reads the file directly rather than ``load_config()`` so an unknown
    ``mineru`` key never trips pydantic validation, and so defaults resolve
    even if the server's typed config is loaded with extra-ignore.
    """
    cfg_path = Path(
        config_path
        or os.environ.get(
            "ZOTERO_MCP_CONFIG",
            str(Path.home() / ".config" / "zotero-mcp" / "config.json"),
        )
    )
    cfg: dict = {}
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg = (raw or {}).get("semantic_search", {}).get("mineru", {}) or {}
    except Exception as e:  # missing file / parse error -> defaults
        logger.debug("mineru: config read failed: %s", e)
    defaults = {
        "enabled": False,
        # MinerU 3.4.5 (upgrade 2026-08-19): CLI renamed magic-pdf -> mineru.
        # Explicit configs may still select the compatible 1.x magic-pdf fallback;
        # run_mineru detects the CLI capability before adding version-specific flags.
        "bin": str(Path.home() / "mineru-upgrade-venv/bin/mineru"),
        "config_json": None,
        "sidecar_dir": str(Path.home() / ".config" / "zotero-mcp" / "mineru-sidecars"),
        "work_dir": str(Path.home() / ".cache" / "zotero-mcp" / "mineru-work"),
        "timeout_seconds": 3600,
        # GTT balloon guard (MinerU 3.x env, renamed from 1.x VIRTUAL_VRAM_SIZE).
        # Unset -> MinerU reads real GPU mem (124 GB) -> batch_ratio 16 (fastest;
        # GTT stayed ~7 GB across dense manual windows; sidecar-watch backstops
        # genuine balloons). Set 4 for batch_ratio 1 (conservative).
        "virtual_vram_size": None,
        "backend": "pipeline",
    }
    merged = dict(defaults)
    merged.update({k: v for k, v in cfg.items() if v is not None})
    return merged


def sidecar_path(cfg: dict, item_key: str) -> Path:
    return Path(cfg["sidecar_dir"]) / f"{item_key}.md"


def read_sidecar(cfg: dict, item_key: str) -> str | None:
    """Return the cached MinerU markdown for an item, or None."""
    if not item_key:
        return None
    p = sidecar_path(cfg, item_key)
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning("mineru: sidecar read failed for %s: %s", item_key, e)
        return None


def _find_output_md(out_dir: Path) -> Path | None:
    """mineru writes <out>/<stem>/txt/<stem>.md — locate it (same layout as 1.x)."""
    try:
        for md in sorted(out_dir.glob("*/txt/*.md")):
            return md
    except OSError:
        pass
    return None


_CLI_BACKEND_CAPABILITY_CACHE: dict[str, bool] = {}


def _supports_backend_flag(bin_: Path, env: dict[str, str]) -> bool:
    """Detect whether the selected MinerU CLI accepts ``-b/--backend``.

    MinerU 3.x (``mineru``) exposes the backend option; the retained 1.x
    ``magic-pdf`` CLI does not.  The configured binary is authoritative, not
    its filename or the package version installed in another virtualenv.
    """
    cache_key = str(bin_.resolve())
    cached = _CLI_BACKEND_CAPABILITY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    supported = False
    try:
        probe = subprocess.run(
            [str(bin_), "--help"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
        )
        supported = "--backend" in (probe.stdout or "")
    except Exception as e:
        logger.warning("mineru: CLI capability probe failed for %s: %s", bin_, e)
    _CLI_BACKEND_CAPABILITY_CACHE[cache_key] = supported
    return supported


def _build_mineru_invocation(
    cfg: dict, pdf_path: Path, out_dir: Path
) -> tuple[list[str], dict[str, str], bool]:
    """Build a version-compatible command and environment for MinerU."""
    bin_ = Path(cfg["bin"])
    env = dict(os.environ)

    # ``config_json`` was part of the original magic-pdf integration.  Keep it
    # authoritative for both generations instead of silently relying on a
    # cwd-dependent ``~/magic-pdf.json`` default.
    config_json = cfg.get("config_json")
    if config_json:
        env["MINERU_TOOLS_CONFIG_JSON"] = str(Path(str(config_json)).expanduser())

    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    supports_backend = _supports_backend_flag(bin_, env)

    # MinerU 3.x renamed the guard variable.  Preserve the conservative 1.x
    # fallback that the pre-upgrade integration used when no new setting was
    # explicitly supplied.
    vvs = cfg.get("virtual_vram_size")
    if vvs is not None:
        env["MINERU_VIRTUAL_VRAM_SIZE" if supports_backend else "VIRTUAL_VRAM_SIZE"] = str(vvs)
    elif not supports_backend:
        env.setdefault("VIRTUAL_VRAM_SIZE", "4")

    cmd = [
        str(bin_),
        "-p", str(pdf_path),
        "-o", str(out_dir),
        "-m", "txt",
    ]
    if supports_backend and cfg.get("backend"):
        cmd.extend(["-b", str(cfg["backend"])])
    return cmd, env, supports_backend


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parser_version(bin_: Path) -> str | None:
    """Read the version from the configured MinerU environment, not its name."""
    python = bin_.resolve().parent.parent / "bin" / "python"
    if python.is_file():
        code = (
            "import importlib.metadata as m; "
            "names=('magic-pdf','mineru','magic_pdf'); "
            "print(next((f'{n}=={m.version(n)}' for n in names "
            "if any(d.metadata.get('Name','').lower()==n.lower() for d in m.distributions())), ''))"
        )
        try:
            result = subprocess.run(
                [str(python), "-c", code], capture_output=True, text=True, timeout=15
            )
            version = (result.stdout or "").strip()
            if result.returncode == 0 and version:
                return version
        except Exception as exc:
            logger.debug("mineru: package-version probe failed: %s", exc)
    try:
        result = subprocess.run(
            [str(bin_), "--version"], capture_output=True, text=True, timeout=15
        )
        output = "\n".join((result.stdout or "", result.stderr or ""))
        for line in output.splitlines():
            if "version" in line.lower():
                return line.strip()
    except Exception as exc:
        logger.debug("mineru: CLI-version probe failed: %s", exc)
    return None


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _find_content_list(out_dir: Path) -> Path | None:
    try:
        matches = sorted(out_dir.glob("*/txt/*_content_list.json"))
        return matches[0] if matches else None
    except OSError:
        return None


def run_mineru(
    cfg: dict,
    pdf_path: Path,
    item_key: str,
    attachment_key: str | None = None,
) -> bool:
    """Parse to an immutable run directory and atomically publish its Markdown.

    Raw MinerU outputs are never cleared or reused. Each run retains its
    page-indexed ``content_list.json`` and a manifest binding the output to the
    PDF, attachment, parser version, and raw Markdown hash.
    """
    bin_ = Path(cfg["bin"])
    pdf_path = Path(pdf_path)
    if not bin_.exists():
        logger.warning("mineru: binary not found: %s", bin_)
        return False
    if not pdf_path.is_file():
        logger.warning("mineru: PDF not found: %s", pdf_path)
        return False
    try:
        pdf_hash = _sha256_file(pdf_path)
    except OSError as exc:
        logger.warning("mineru: could not hash PDF for %s: %s", item_key, exc)
        return False

    work = Path(cfg["work_dir"]) / item_key
    run_id = f"{time.strftime('%Y%m%dT%H%M%S')}-{time.time_ns()}-{pdf_hash[:12]}"
    run_dir = work / "runs" / run_id
    out_dir = run_dir / "out"
    log_path = run_dir / "run.log"
    work.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=False)
    cmd, env, supports_backend = _build_mineru_invocation(cfg, pdf_path, out_dir)
    parser_version = _parser_version(bin_)
    logger.info(
        "mineru: using %s CLI (backend_flag=%s, version=%s, config=%s)",
        bin_, supports_backend, parser_version or "unknown",
        env.get("MINERU_TOOLS_CONFIG_JSON", "default"),
    )
    try:
        start = time.time()
        with log_path.open("w", encoding="utf-8") as lf:
            proc = subprocess.run(
                cmd,
                env=env,
                stdout=lf,
                stderr=subprocess.STDOUT,
                timeout=int(cfg.get("timeout_seconds", 3600)),
            )
        # Keep the conventional latest log path for existing watchdogs while
        # retaining the authoritative copy beside this run's raw artifacts.
        try:
            shutil.copy2(log_path, work / "run.log")
        except OSError:
            pass
        elapsed = time.time() - start
        md = _find_output_md(out_dir)
        if proc.returncode == 0 and md is not None:
            raw_markdown = md.read_bytes()
            content_list = _find_content_list(out_dir)
            side = sidecar_path(cfg, item_key)
            side.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=f".{side.name}.", suffix=".tmp", dir=side.parent)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(raw_markdown)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_name, side)
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
            manifest = {
                "manifest_schema": 1,
                "item_key": item_key,
                "attachment_key": attachment_key,
                "pdf_sha256": pdf_hash,
                "parser_version": parser_version,
                "run_id": run_id,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "raw_markdown_path": str(md),
                "raw_markdown_sha256": hashlib.sha256(raw_markdown).hexdigest(),
                "content_list_path": str(content_list) if content_list else None,
                "content_list_sha256": _sha256_file(content_list) if content_list else None,
                "run_log_path": str(log_path),
                "backend_flag_supported": supports_backend,
            }
            _write_json_atomic(run_dir / "manifest.json", manifest)
            _write_json_atomic(work / "latest-run.json", manifest)
            logger.info(
                "mineru: parsed %s in %.0fs -> %s (%.1f KB); raw run: %s",
                item_key, elapsed, side, side.stat().st_size / 1024, run_dir,
            )
            return True
        logger.warning(
            "mineru: parse failed for %s (rc=%s, %.0fs); retained log: %s",
            item_key, proc.returncode, elapsed, log_path,
        )
        return False
    except Exception as e:
        logger.warning("mineru: parse raised for %s: %s; retained work: %s", item_key, e, run_dir)
        return False


def try_auto_parse(item_key: str, reader, config_path: str | None = None) -> tuple[str, str] | None:
    """Return ``(fulltext, source)`` for an item, parsing with MinerU if needed.

    Fast path: sidecar already exists (covers manual parses and prior runs).
    Otherwise, if ``mineru.enabled`` and the item has exactly one resolvable PDF,
    run MinerU and return its text. Multiple PDF attachments are ambiguous and
    are not selected implicitly. A caller applying the quality gate must not
    fall back after a parse failure.
    """
    if not item_key:
        return None
    cfg = load_mineru_config(config_path)

    text = read_sidecar(cfg, item_key)
    if text is not None:
        return text, "mineru-sidecar"

    if not cfg.get("enabled"):
        return None

    try:
        attachments = reader.get_attachment_paths(item_key)
    except Exception as e:
        logger.warning("mineru: attachment resolution failed for %s: %s", item_key, e)
        return None

    pdfs = [
        (str(att.get("key") or ""), Path(att["resolved_path"]))
        for att in attachments
        if att.get("resolved_path")
        and str(att["resolved_path"]).lower().endswith(".pdf")
        and Path(att["resolved_path"]).is_file()
    ]
    if len(pdfs) != 1:
        if pdfs:
            logger.warning("mineru: refusing ambiguous PDF attachment set for %s (%s PDFs)", item_key, len(pdfs))
        return None
    attachment_key, pdf = pdfs[0]

    if run_mineru(cfg, pdf, item_key, attachment_key=attachment_key):
        text = read_sidecar(cfg, item_key)
        if text is not None:
            return text, "mineru"
    return None


def _has_resolvable_pdf(item_key: str, reader) -> bool:
    """True when the item has a resolvable PDF attachment on disk."""
    try:
        for att in reader.get_attachment_paths(item_key):
            rp = att.get("resolved_path")
            if rp and str(rp).lower().endswith(".pdf") and Path(rp).exists():
                return True
    except Exception as e:
        logger.debug("mineru: attachment lookup failed for %s: %s", item_key, e)
    return False


def is_parseable(item_key: str, reader, config_path: str | None = None) -> bool:
    """True when MinerU is enabled and could serve this item: a cached
    sidecar exists, or the item has a resolvable PDF. Used by the update
    loop to decide whether a previously-failed item deserves a retry."""
    if not item_key:
        return False
    cfg = load_mineru_config(config_path)
    if not cfg.get("enabled"):
        return False
    if read_sidecar(cfg, item_key) is not None:
        return True
    return _has_resolvable_pdf(item_key, reader)


def is_backfill_target(item_key: str, reader, config_path: str | None = None) -> bool:
    """True when the item should be re-extracted as part of the MinerU
    backfill: mineru.enabled AND mineru.backfill AND (sidecar cached OR a
    resolvable PDF exists). This turns the first post-enable update into a
    one-time library parse; items without PDFs are never targets."""
    if not item_key:
        return False
    cfg = load_mineru_config(config_path)
    if not (cfg.get("enabled") and cfg.get("backfill")):
        return False
    if read_sidecar(cfg, item_key) is not None:
        return True
    return _has_resolvable_pdf(item_key, reader)
