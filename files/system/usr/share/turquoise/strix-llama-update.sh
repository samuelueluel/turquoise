#!/usr/bin/env bash
# Build, update, and maintain the strix-llama toolbox image and container
# using ROCm 10.0 and pwilkin's custom retained-PM4 ROCr/HIP runtime
# from https://github.com/kyuz0/amd-strix-halo-toolboxes main
# (toolboxes/Dockerfile.rocm-10.0-strix-llama, merged from PR #133).
set -Eeuo pipefail
umask 022

REPO_URL="https://github.com/kyuz0/amd-strix-halo-toolboxes.git"
REPO_DIR="${STRIX_TOOLBOX_REPO:-$HOME/.local/share/amd-strix-halo-toolboxes}"
GIT_REF="origin/main"
IMAGE="localhost/llama-rocm-10.0-strix-llama"
TOOLBOX_NAME="llama-rocm-10.0-strix-llama"
FORCE="${FORCE:-false}"

case "$FORCE" in
  true|1|force|force=true|--force) FORCE="true" ;;
  false|0|no|force=false) FORCE="false" ;;
  *) echo "strix-llama-update: invalid FORCE value: $FORCE" >&2; exit 1 ;;
esac

(( EUID != 0 )) || { echo "strix-llama-update: run as invoking user, not root or sudo" >&2; exit 1; }
[[ -z "${SUDO_USER:-}" ]] || { echo "strix-llama-update: do not run through sudo" >&2; exit 1; }
command -v podman >/dev/null 2>&1 || { echo "strix-llama-update: podman not found" >&2; exit 1; }
command -v git >/dev/null 2>&1 || { echo "strix-llama-update: git not found" >&2; exit 1; }

echo "=== strix-llama toolbox maintenance (main: ROCm 10 + Retained PM4) ==="

# 1. Ensure repository exists and local main is updated to origin/main
if [[ ! -d "$REPO_DIR/.git" ]]; then
  echo "Cloning $REPO_URL into $REPO_DIR..."
  mkdir -p "$(dirname "$REPO_DIR")"
  git clone "$REPO_URL" "$REPO_DIR"
else
  echo "Fetching latest upstream main..."
  git -C "$REPO_DIR" fetch origin main || true
fi
git -C "$REPO_DIR" checkout -B main "$GIT_REF"

DOCKERFILE="$REPO_DIR/toolboxes/Dockerfile.rocm-10.0-strix-llama"
[[ -f "$DOCKERFILE" ]] || {
  echo "strix-llama-update: Dockerfile not found at $DOCKERFILE" >&2
  exit 1
}

CURRENT_COMMIT=$(git -C "$REPO_DIR" rev-parse HEAD)
echo "Current main commit: $CURRENT_COMMIT"

# 2. Check if image needs building
image_exists="false"
if podman image exists "$IMAGE" >/dev/null 2>&1; then
  image_exists="true"
fi

IMAGE_METADATA_FILE="$REPO_DIR/.built-image-commit"
last_built_commit=""
[[ -f "$IMAGE_METADATA_FILE" ]] && last_built_commit=$(cat "$IMAGE_METADATA_FILE" 2>/dev/null || true)

need_build="false"
if [[ "$FORCE" == "true" ]]; then
  echo "Build forced via FORCE=true."
  need_build="true"
elif [[ "$image_exists" != "true" ]]; then
  echo "Image $IMAGE does not exist locally; building."
  need_build="true"
elif [[ "$last_built_commit" != "$CURRENT_COMMIT" ]]; then
  echo "Source commit changed ($last_built_commit -> $CURRENT_COMMIT); rebuilding."
  need_build="true"
else
  echo "Image $IMAGE is up to date with commit $CURRENT_COMMIT."
fi

# 3. Build image if needed
if [[ "$need_build" == "true" ]]; then
  echo "Building $IMAGE with Ninja and ROCm 10.0 (this may take 15-30 minutes)..."
  (
    cd "$REPO_DIR/toolboxes"
    podman build \
      --label "git-commit=$CURRENT_COMMIT" \
      --label "builder=strix-llama-update" \
      -t "$IMAGE" \
      -f Dockerfile.rocm-10.0-strix-llama \
      .
  )
  printf '%s\n' "$CURRENT_COMMIT" > "$IMAGE_METADATA_FILE"
  echo "Build complete: $IMAGE"
fi

# 4. Ensure toolbox container exists and matches the image
if command -v toolbox >/dev/null 2>&1; then
  toolbox_exists="false"
  if podman container exists "$TOOLBOX_NAME" 2>/dev/null; then
    toolbox_exists="true"
  fi

  need_container_refresh="false"
  if [[ "$need_build" == "true" || "$toolbox_exists" != "true" ]]; then
    need_container_refresh="true"
  else
    c_img=$(podman inspect "$TOOLBOX_NAME" --format '{{.Image}}' 2>/dev/null || true)
    i_img=$(podman inspect "$IMAGE" --format '{{.Id}}' 2>/dev/null || true)
    if [[ -n "$c_img" && -n "$i_img" && "$c_img" != "$i_img" ]]; then
      echo "Toolbox container image differs from latest $IMAGE; refreshing."
      need_container_refresh="true"
    fi
  fi

  if [[ "$need_container_refresh" == "true" ]]; then
    if [[ "$toolbox_exists" == "true" ]] || podman container exists "$TOOLBOX_NAME" 2>/dev/null; then
      echo "Refreshing toolbox container $TOOLBOX_NAME..."
      toolbox rm -f "$TOOLBOX_NAME" >/dev/null 2>&1 || podman rm -f "$TOOLBOX_NAME" >/dev/null 2>&1 || true
    else
      echo "Creating toolbox container $TOOLBOX_NAME..."
      podman rm -f "$TOOLBOX_NAME" >/dev/null 2>&1 || true
    fi
    toolbox create "$TOOLBOX_NAME" \
      --image "$IMAGE" \
      -- --device /dev/dri --device /dev/kfd --group-add video --group-add render \
      --security-opt seccomp=unconfined
    echo "Toolbox container $TOOLBOX_NAME ready."
  else
    echo "Toolbox container $TOOLBOX_NAME already exists and is current."
  fi
fi

# 5. If strix-llama-server container was running, restart it
if podman container exists strix-llama-server >/dev/null 2>&1; then
  server_state=$(podman inspect --format '{{.State.Status}}' strix-llama-server 2>/dev/null || true)
  if [[ "$server_state" == "running" && "$need_build" == "true" ]]; then
    echo "Restarting strix-llama-server with updated image..."
    if command -v strix-llama >/dev/null 2>&1; then
      strix-llama stop || true
      strix-llama start || true
    else
      podman restart strix-llama-server || true
    fi
  fi
fi

echo "=== strix-llama toolbox maintenance finished successfully ==="
