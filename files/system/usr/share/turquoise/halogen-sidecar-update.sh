#!/usr/bin/env bash
# Refresh the W4B quality sidecar (overlay) used by the NATIVE Halogen
# deployment (~/.local/bin/halogen start/ensure w4b, weights in
# ~/halogen-models). Peonist re-ships this ~2.4 GB patch file occasionally;
# 0.6.0 changed it, and the server prints a NOTE at startup when the copy on
# disk predates the image. The BYO-GGUF deployment created by
# halogen-update.sh mounts the Lemonade cache and never reads this file, so
# this target is a no-op for that variant.
#
# Behavior: a HEAD request reads the remote ETag; when it matches the recorded
# one nothing is downloaded. Otherwise the file is fetched, compared against
# the installed copy by content, and installed with a one-shot .bak backup.
# Restart Halogen afterwards to load it:
#   halogen stop && halogen ensure w4b
set -Eeuo pipefail
umask 077

REPO="peonist-ai/halogen-qwen3.8-flash-next"
FILENAME="qwen38-flash-next-w4b.overlay.hgn"
URL="https://huggingface.co/${REPO}/resolve/main/${FILENAME}"
MODELS_DIR="${HALOGEN_W4B_MODELS:-$HOME/halogen-models}"
TARGET="$MODELS_DIR/$FILENAME"
STATE="$MODELS_DIR/.w4b-overlay-etag"

fail() {
  echo "halogen-sidecar-update: $*" >&2
  exit 1
}

command -v curl >/dev/null 2>&1 || fail "curl not found"
[[ -d "$MODELS_DIR" ]] || fail "W4B models directory not found: $MODELS_DIR"

remote_etag=$(curl -fsSI -L "$URL" | grep -i '^etag:' | tail -1 | tr -d '\r' | awk '{print $2}') || true
remote_etag=${remote_etag%\"}
remote_etag=${remote_etag#\"}
[[ -n "$remote_etag" ]] ||
  fail "could not read an ETag for $FILENAME from Hugging Face; check connectivity"

recorded=""
[[ -f "$STATE" ]] && recorded=$(cat "$STATE")
if [[ "$recorded" == "$remote_etag" ]]; then
  echo "halogen-sidecar-update: sidecar is current (etag $remote_etag)"
  exit 0
fi

echo "halogen-sidecar-update: remote sidecar changed (etag ${recorded:-none} -> $remote_etag); downloading $FILENAME"
tmp=$(mktemp "$MODELS_DIR/.overlay-download.XXXXXX")
cleanup() { rm -f "$tmp"; }
trap cleanup EXIT
curl -fsSL -o "$tmp" "$URL"
[[ -s "$tmp" ]] || fail "downloaded sidecar is empty"

if [[ -f "$TARGET" ]] && cmp -s "$tmp" "$TARGET"; then
  printf '%s\n' "$remote_etag" > "$STATE"
  echo "halogen-sidecar-update: content identical to the installed file; recorded etag"
  exit 0
fi

if [[ -f "$TARGET" ]]; then
  cp --preserve=mode "$TARGET" "$TARGET.bak"
fi
mv "$tmp" "$TARGET"
trap - EXIT
printf '%s\n' "$remote_etag" > "$STATE"
echo "halogen-sidecar-update: installed new sidecar at $TARGET (previous copy: $TARGET.bak)"
echo "halogen-sidecar-update: restart Halogen to load it:  halogen stop && halogen ensure w4b"
