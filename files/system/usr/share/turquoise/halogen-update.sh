#!/usr/bin/env bash
# Pull and (only when needed) recreate the standalone Peonist Halogen service.
# Halogen is a closed-source release image, not a llama.cpp source build. Keep
# this service outside Lemonade's llama-server binary/dispatch volume.
set -Eeuo pipefail
umask 077

CONTAINER="${HALOGEN_CONTAINER:-halogen}"
# 0.7.0 is the first release with lossless llama.cpp GGUF input; 0.11.x adds
# the thinking answer-room and Pi's thinking-budget field names.
# The tag floats on upstream's `latest`: every run pulls fresh and recreates
# when the resolved image ID changes, so `sjust llm-engine` always ships the
# newest release. Roll back with HALOGEN_IMAGE=...:<numeric-tag> (old images
# stay on disk).
IMAGE="${HALOGEN_IMAGE:-ghcr.io/peonist-ai/halogen-flash-server:latest}"
# Reuse the existing Qwen3.8-Flash-Next GGUF cache maintained by Lemonade.
MODELS="${HALOGEN_MODELS:-$HOME/.local/share/containers/storage/volumes/lemonade26-v108-cache/_data/qwen3.8-flash-next}"
CHECKPOINT="${HALOGEN_CHECKPOINT:-/models/UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf}"
MTP_HEAD="${HALOGEN_MTP_HEAD:-/models/qwen38-flash-next-mtp.hgn}"
TOKENIZER="${HALOGEN_TOKENIZER:-/models/tokenizer}"
# Peonist vision sidecar (.hgn format). Its llama.cpp mmproj equivalents are
# not readable by this engine. Unset HALOGEN_VISION_TOWER to serve text-only.
# No-colon expansion: an explicitly EMPTY HALOGEN_VISION_TOWER must select
# text-only, while a truly unset variable falls back to the tower default.
# ${x:-y} would treat empty as unset and silently load vision.
VISION_TOWER="${HALOGEN_VISION_TOWER-/models/qwen38-flash-next-vision.hgn}"
# Mirror the live Lemonade extra.UD-Q4_K_XL sampling/reasoning profile while
# retaining Halogen's MTP drafter. Values sent by an API request still take
# precedence over these server-side defaults.
TEMPERATURE="${HALOGEN_TEMPERATURE:-1.0}"
TOP_P="${HALOGEN_TOP_P:-0.95}"
TOP_K="${HALOGEN_TOP_K:-20}"
MIN_P="${HALOGEN_MIN_P:-0.0}"
PRESENCE_PENALTY="${HALOGEN_PRESENCE_PENALTY:-0.0}"
ENABLE_THINKING="${HALOGEN_ENABLE_THINKING:-1}"
REASONING_EFFORT="${HALOGEN_REASONING_EFFORT:-xhigh}"
DRAFTER_DEFAULT="${HALOGEN_DRAFTER_DEFAULT:-1}"
CONFIG_VERSION="12"
# The vision mode is part of the container contract. Encode it in the config
# label so a mode switch recreates the container instead of early-exit
# matching a deployment created with the other mode.
CONFIG_VERSION="${CONFIG_VERSION}-$( [[ -n "$VISION_TOWER" ]] && echo vision || echo text )"
FORCE="${FORCE:-false}"
# Upstream default is 1 and the docs call pinning "the setting to reach for if
# you run other large workloads on the same machine"; 0 streams the 68 GiB
# trunk from the page cache on every forward and costs several times decode
# speed. The working 0.5.8 deployment held the weights resident.
PIN_TRUNK="${HALOGEN_FLASH_PIN_TRUNK:-1}"
# The per-forward arena is sized by HALOGEN_MAX_TOK while the image bakes
# HALOGEN_PREFILL_CHUNK=32768 as the prefill call width. Any MAX_TOK override
# without a matching PREFILL_CHUNK overflows the arena on Pi-sized prompts
# ("internal sizing error in the per-forward arena", or a zero-token hang).
# 32768 no longer fits this host's device budget on 0.5.9+; 16384 does only
# with a smaller KV pool, so both are set together.
# HALOGEN_PREFILL_CHUNK=32768 as the prefill call width. Any MAX_TOK override
# without a matching PREFILL_CHUNK overflows the arena on Pi-sized prompts
# ("internal sizing error in the per-forward arena", or a zero-token hang).
# 32768 no longer fits this host's device budget on 0.5.9+; 16384 does only
# with a smaller KV pool, so both are set together.
MAX_TOK="${HALOGEN_MAX_TOK:-8192}"
PREFILL_CHUNK="${HALOGEN_PREFILL_CHUNK:-8192}"
KV_POOL_POSITIONS="${HALOGEN_KV_POOL_POSITIONS:-262144}"
MAX_TOKENS_DEFAULT="${HALOGEN_MAX_TOKENS_DEFAULT:-8192}"
MAX_TOKENS_CAP="${HALOGEN_MAX_TOKENS_CAP:-65536}"

fail() {
  echo "halogen-update: $*" >&2
  exit 1
}

case "$FORCE" in
  true|1|force|force=true|--force) FORCE="true" ;;
  false|0|no|force=false) FORCE="false" ;;
  *) fail "invalid FORCE value: $FORCE" ;;
esac
[[ "$PIN_TRUNK" == 0 || "$PIN_TRUNK" == 1 ]] ||
  fail "HALOGEN_FLASH_PIN_TRUNK must be 0 or 1 (got: $PIN_TRUNK)"
(( PIN_TRUNK == 1 )) ||
  fail "HALOGEN_FLASH_PIN_TRUNK=0 is a documented last resort; set it explicitly if you truly want the unpinned trunk"
[[ "$MAX_TOK" =~ ^[1-9][0-9]*$ ]] ||
  fail "HALOGEN_MAX_TOK must be a positive integer (got: $MAX_TOK)"
(( MAX_TOK <= 16384 )) ||
  fail "HALOGEN_MAX_TOK must be <= 16384 (got: $MAX_TOK)"
[[ "$PREFILL_CHUNK" =~ ^[1-9][0-9]*$ ]] ||
  fail "HALOGEN_PREFILL_CHUNK must be a positive integer (got: $PREFILL_CHUNK)"
(( PREFILL_CHUNK == MAX_TOK )) ||
  fail "HALOGEN_PREFILL_CHUNK ($PREFILL_CHUNK) must equal HALOGEN_MAX_TOK ($MAX_TOK): the arena is sized by MAX_TOK while the prefill call width comes from PREFILL_CHUNK"
[[ "$KV_POOL_POSITIONS" =~ ^[1-9][0-9]*$ ]] ||
  fail "HALOGEN_KV_POOL_POSITIONS must be a positive integer (got: $KV_POOL_POSITIONS)"
(( KV_POOL_POSITIONS >= 262144 )) ||
  fail "HALOGEN_KV_POOL_POSITIONS must be >= 262144 (got: $KV_POOL_POSITIONS)"
[[ "$MAX_TOKENS_DEFAULT" =~ ^[1-9][0-9]*$ ]] ||
  fail "HALOGEN_MAX_TOKENS_DEFAULT must be a positive integer (got: $MAX_TOKENS_DEFAULT)"
[[ "$MAX_TOKENS_CAP" =~ ^[1-9][0-9]*$ ]] ||
  fail "HALOGEN_MAX_TOKENS_CAP must be a positive integer (got: $MAX_TOKENS_CAP)"
(( MAX_TOKENS_DEFAULT <= MAX_TOKENS_CAP )) ||
  fail "HALOGEN_MAX_TOKENS_DEFAULT must be <= HALOGEN_MAX_TOKENS_CAP"
(( MAX_TOKENS_CAP <= 65536 )) ||
  fail "HALOGEN_MAX_TOKENS_CAP must be <= 65536 (got: $MAX_TOKENS_CAP)"

# sjust is a rootless host operation. Do not silently turn this into a
# rootful deployment if somebody invokes the target through sudo.
(( EUID != 0 )) || fail "run as the invoking user, not root or sudo"
[[ -z "${SUDO_USER:-}" ]] || fail "do not run this target through sudo"
command -v podman >/dev/null 2>&1 || fail "podman not found"
[[ -d "$MODELS" ]] || fail "model directory not found: $MODELS"
[[ "$CHECKPOINT" == /models/* ]] ||
  fail "HALOGEN_CHECKPOINT must be a path under /models (got: $CHECKPOINT)"
[[ "$MTP_HEAD" == /models/* ]] ||
  fail "HALOGEN_MTP_HEAD must be a path under /models (got: $MTP_HEAD)"
[[ -z "$VISION_TOWER" || "$VISION_TOWER" == /models/* ]] ||
  fail "HALOGEN_VISION_TOWER must be empty or a path under /models (got: $VISION_TOWER)"
[[ "$TOKENIZER" == /models/* ]] ||
  fail "HALOGEN_TOKENIZER must be a path under /models (got: $TOKENIZER)"
CHECKPOINT_HOST="$MODELS/${CHECKPOINT#/models/}"
MTP_HEAD_HOST="$MODELS/${MTP_HEAD#/models/}"
TOKENIZER_HOST="$MODELS/${TOKENIZER#/models/}"
VISION_TOWER_HOST=""
[[ -z "$VISION_TOWER" ]] || VISION_TOWER_HOST="$MODELS/${VISION_TOWER#/models/}"
[[ -f "$CHECKPOINT_HOST" ]] ||
  fail "GGUF checkpoint not found: $CHECKPOINT_HOST"
[[ -f "$MTP_HEAD_HOST" ]] ||
  fail "Halogen MTP head not found: $MTP_HEAD_HOST"
[[ -z "$VISION_TOWER_HOST" ]] || [[ -f "$VISION_TOWER_HOST" ]] ||
  fail "Halogen vision tower not found: $VISION_TOWER_HOST"
[[ -f "$TOKENIZER_HOST/tokenizer.json" ]] ||
  fail "Halogen tokenizer.json not found: $TOKENIZER_HOST/tokenizer.json"

old_inspect=""
metadata=""
temp_container=""
old_exists="false"

cleanup() {
  if [[ -n "$temp_container" ]]; then
    podman rm -f "$temp_container" >/dev/null 2>&1 || true
  fi
  [[ -z "$old_inspect" ]] || rm -f "$old_inspect"
  [[ -z "$metadata" ]] || rm -f "$metadata"
}
trap cleanup EXIT

if podman container exists "$CONTAINER" >/dev/null 2>&1; then
  old_exists="true"
  old_inspect=$(mktemp "${TMPDIR:-/tmp}/halogen-inspect.XXXXXX")
  podman inspect "$CONTAINER" >"$old_inspect"
else
  exists_rc=$?
  (( exists_rc == 1 )) || fail "could not inspect container state (podman rc=$exists_rc)"
fi

# Turn the existing container's non-secret runtime settings into an explicit,
# bounded allowlist. Environment values are intentionally not copied: this
# target declares only the Halogen setting it owns and never handles secrets.
if [[ "$old_exists" == true ]]; then
  metadata=$(mktemp "${TMPDIR:-/tmp}/halogen-metadata.XXXXXX")
  python3 - "$old_inspect" "$metadata" <<'PY'
import json
import sys

src, dst = sys.argv[1:]
with open(src, encoding="utf-8") as fh:
    item = json.load(fh)[0]

host = item.get("HostConfig") or {}
config = item.get("Config") or {}
state = item.get("State") or {}
labels = config.get("Labels") or {}
annotations = {}
for source in (host.get("Annotations") or {}, config.get("Annotations") or {}):
    annotations.update(source)


def list_or_empty(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def device_option(value):
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    source = value.get("PathOnHost") or value.get("path_on_host")
    target = value.get("PathInContainer") or value.get("path_in_container") or source
    permissions = value.get("CgroupPermissions") or value.get("cgroup_permissions")
    if not source:
        return None
    if permissions:
        return f"{source}:{target}:{permissions}"
    return f"{source}:{target}"


def ulimit_option(value):
    if not isinstance(value, dict):
        return None
    name = value.get("Name") or value.get("name")
    soft = value.get("Soft", value.get("soft"))
    hard = value.get("Hard", value.get("hard"))
    if not name or soft is None or hard is None:
        return None
    name = str(name)
    if name.startswith("RLIMIT_"):
        name = name[7:]
    return f"{name.lower()}={soft}:{hard}"


def secret_option(value):
    # Podman inspect versions have used both strings and small descriptor
    # objects. Preserve names/targets only; never serialize a secret payload.
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    name = (
        value.get("Name") or value.get("name") or value.get("Source") or
        value.get("source") or value.get("ID") or value.get("id")
    )
    target = (
        value.get("Target") or value.get("target") or value.get("File") or
        value.get("file")
    )
    if not name:
        return None
    option = str(name)
    if target:
        option += f",target={target}"
    return option


def unique(values):
    result = []
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


devices = [device_option(value) for value in list_or_empty(host.get("Devices"))]
devices = unique(devices)

# RLIMIT_NPROC is specific to the invoking host/user namespace. Replaying
# an old value can make rootless crun reject the container at startup when the
# host limit changes, so let Podman inherit the current limit instead.
ulimits = [
    value for value in
    (ulimit_option(value) for value in list_or_empty(host.get("Ulimits")))
    if value and not value.startswith("nproc=")
]
ulimits = unique(ulimits)

secrets = []
unparsed_secrets = 0
for field in (host.get("Secrets"), config.get("Secrets")):
    for value in list_or_empty(field):
        option = secret_option(value)
        if option is None:
            unparsed_secrets += 1
        else:
            secrets.append(option)
for mount in item.get("Mounts") or []:
    if isinstance(mount, dict) and mount.get("Type") == "secret":
        option = secret_option(mount)
        if option is None:
            unparsed_secrets += 1
        else:
            secrets.append(option)

restart = host.get("RestartPolicy") or {}
restart_name = restart.get("Name") or "no"
restart_max = restart.get("MaximumRetryCount") or 0

out = {
    "image_id": item.get("Image") or "",
    "config_version": labels.get("io.turquoise.halogen-config-version") or "",
    "state": state.get("Status") or "",
    "network": host.get("NetworkMode") or "",
    "ipc": host.get("IpcMode") or "",
    "shm_size": int(host.get("ShmSize") or 0),
    "restart": str(restart_name),
    "restart_max": int(restart_max),
    "privileged": bool(host.get("Privileged")),
    "readonly_rootfs": bool(host.get("ReadonlyRootfs")),
    "userns_mode": host.get("UsernsMode") or "",
    "keep_groups": annotations.get("run.oci.keep_original_groups") == "1",
    "devices": devices,
    "security_opts": [str(value) for value in list_or_empty(host.get("SecurityOpt"))],
    "cap_add": [str(value) for value in list_or_empty(host.get("CapAdd"))],
    "cap_drop": [str(value) for value in list_or_empty(host.get("CapDrop"))],
    "groups": [str(value) for value in list_or_empty(host.get("GroupAdd"))],
    "ulimits": ulimits,
    "secrets": unique(secrets),
    "unparsed_secrets": unparsed_secrets,
}

with open(dst, "w", encoding="utf-8") as fh:
    json.dump(out, fh)
PY
fi

meta_value() {
  local key="$1"
  python3 - "$metadata" "$key" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    value = json.load(fh).get(sys.argv[2], "")
if isinstance(value, bool):
    print("true" if value else "false")
else:
    print(value)
PY
}

meta_list() {
  local key="$1"
  python3 - "$metadata" "$key" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    values = json.load(fh).get(sys.argv[2], [])
for value in values:
    sys.stdout.write(str(value))
    sys.stdout.write("\0")
PY
}

old_image_id=""
old_config_version=""
old_state=""
network=""
ipc=""
shm_size="0"
restart_name=""
restart_max="0"
privileged="false"
readonly_rootfs="false"
userns_mode=""
unparsed_secrets="0"
declare -a old_devices=() security_opts=() cap_add=() cap_drop=() groups=() ulimits=() secrets=()
if [[ "$old_exists" == true ]]; then
  old_image_id=$(meta_value image_id)
  old_config_version=$(meta_value config_version)
  old_state=$(meta_value state)
  network=$(meta_value network)
  ipc=$(meta_value ipc)
  shm_size=$(meta_value shm_size)
  restart_name=$(meta_value restart)
  restart_max=$(meta_value restart_max)
  privileged=$(meta_value privileged)
  readonly_rootfs=$(meta_value readonly_rootfs)
  userns_mode=$(meta_value userns_mode)
  unparsed_secrets=$(meta_value unparsed_secrets)
  mapfile -d '' -t old_devices < <(meta_list devices)
  mapfile -d '' -t security_opts < <(meta_list security_opts)
  mapfile -d '' -t cap_add < <(meta_list cap_add)
  mapfile -d '' -t cap_drop < <(meta_list cap_drop)
  mapfile -d '' -t groups < <(meta_list groups)
  mapfile -d '' -t ulimits < <(meta_list ulimits)
  mapfile -d '' -t secrets < <(meta_list secrets)

  (( unparsed_secrets == 0 )) ||
    fail "existing container has secret settings this helper cannot preserve safely"
  [[ "$privileged" != true ]] ||
    fail "refusing to recreate a privileged Halogen container"
fi

# Pull the pinned release on every invocation. The resolved image ID, not the
# mutable local tag, decides whether a recreation is necessary.
echo "halogen-update: pulling $IMAGE"
podman pull "$IMAGE"
new_image_id=$(podman image inspect "$IMAGE" --format '{{.Id}}')
[[ -n "$new_image_id" ]] || fail "could not resolve image ID for $IMAGE"

if [[ "$old_exists" == true && "$FORCE" != true &&
      "$old_image_id" == "$new_image_id" &&
      "$old_config_version" == "$CONFIG_VERSION" ]]; then
  echo "halogen-update: $CONTAINER already uses $IMAGE at $new_image_id (config $CONFIG_VERSION)"
  if [[ "$old_state" != running ]]; then
    echo "halogen-update: starting stopped $CONTAINER"
    podman start "$CONTAINER" >/dev/null
  fi
  exit 0
fi

# This is a desired configuration, not a clone of every old HostConfig field.
# BYO GGUF assets are staged in the Lemonade cache before this target runs. The
# model directory remains read-only and HALOGEN_DOWNLOAD is deliberately absent:
# this target never downloads or modifies model weights.
temp_container="${CONTAINER}.new.$$"
while podman container exists "$temp_container" >/dev/null 2>&1; do
  temp_container="${CONTAINER}.new.$$.${RANDOM}"
done
create_args=(
  --name "$temp_container"
  --label "io.turquoise.halogen-config-version=$CONFIG_VERSION"
  --env "HALOGEN_FLASH_PIN_TRUNK=$PIN_TRUNK"
  --env "HALOGEN_MAX_TOK=$MAX_TOK"
  --env "HALOGEN_PREFILL_CHUNK=$PREFILL_CHUNK"
  --env "HALOGEN_KV_POOL_POSITIONS=$KV_POOL_POSITIONS"
  --env "HALOGEN_MAX_TOKENS_DEFAULT=$MAX_TOKENS_DEFAULT"
  --env "HALOGEN_MAX_TOKENS_CAP=$MAX_TOKENS_CAP"
  --env "HALOGEN_CHECKPOINT=$CHECKPOINT"
  --env "HALOGEN_MTP_HEAD=$MTP_HEAD"
  --env "HALOGEN_TOKENIZER=$TOKENIZER"
  --env "HALOGEN_TEMPERATURE=$TEMPERATURE"
  --env "HALOGEN_TOP_P=$TOP_P"
  --env "HALOGEN_TOP_K=$TOP_K"
  --env "HALOGEN_MIN_P=$MIN_P"
  --env "HALOGEN_PRESENCE_PENALTY=$PRESENCE_PENALTY"
  --env "HALOGEN_ENABLE_THINKING=$ENABLE_THINKING"
  --env "HALOGEN_REASONING_EFFORT=$REASONING_EFFORT"
  --env "HALOGEN_DRAFTER_DEFAULT=$DRAFTER_DEFAULT"
  --volume "$MODELS:/models:ro"
  --publish "127.0.0.1:8731:8731"
)
# Absent rather than empty: an empty HALOGEN_VISION_TOWER is not documented
# as equivalent to unset, so the text-only opt-out must omit the flag.
[[ -z "$VISION_TOWER" ]] || create_args+=(--env "HALOGEN_VISION_TOWER=$VISION_TOWER")

if [[ "$old_exists" == true ]]; then
  if ((${#old_devices[@]})); then
    for value in "${old_devices[@]}"; do
      create_args+=(--device "$value")
    done
  else
    # The old inspect format may omit devices created through rootless device
    # passthrough. Use the documented Halogen GPU devices when none are listed.
    for value in /dev/kfd /dev/dri; do
      [[ -e "$value" ]] || fail "required GPU device is missing: $value"
      create_args+=(--device "$value")
    done
  fi
else
  for value in /dev/kfd /dev/dri; do
    [[ -e "$value" ]] || fail "required GPU device is missing: $value"
    create_args+=(--device "$value")
  done
fi

if [[ "$old_exists" == true ]]; then
  case "$network" in
    ""|default) ;;
    host|host:*|none|container:*|ns:*)
      fail "existing network mode '$network' cannot provide a loopback-only published API"
      ;;
    *) create_args+=(--network "$network") ;;
  esac
fi
[[ -z "$ipc" ]] || create_args+=(--ipc "$ipc")
if [[ "$old_exists" == true ]]; then
  restart_value="$restart_name"
  [[ -n "$restart_value" && "$restart_value" != "no" ]] || restart_value="unless-stopped"
else
  restart_value="unless-stopped"
fi
if [[ "$restart_value" == "on-failure" && "$restart_max" =~ ^[1-9][0-9]*$ ]]; then
  restart_value="$restart_value:$restart_max"
fi
create_args+=(--restart "$restart_value")
# Podman rejects an explicit shared-memory size with host IPC; host IPC
# already supplies the relevant namespace, so do not carry the stale value.
if [[ "$ipc" != "host" && "$shm_size" =~ ^[1-9][0-9]*$ ]]; then
  create_args+=(--shm-size "$shm_size")
fi

if [[ "$old_exists" == true && ${#security_opts[@]} -gt 0 ]]; then
  for value in "${security_opts[@]}"; do
    create_args+=(--security-opt "$value")
  done
else
  # Required by the published AMD quickstart; preserve a non-empty old list.
  create_args+=(--security-opt seccomp=unconfined)
fi
for value in "${cap_add[@]}"; do create_args+=(--cap-add "$value"); done
for value in "${cap_drop[@]}"; do create_args+=(--cap-drop "$value"); done
[[ "$readonly_rootfs" == true ]] && create_args+=(--read-only)
[[ -z "$userns_mode" || "$userns_mode" == "default" ]] ||
  create_args+=(--userns "$userns_mode")

if [[ "$old_exists" == true ]]; then
  for value in "${groups[@]}"; do create_args+=(--group-add "$value"); done
  keep_groups=$(meta_value keep_groups)
  if [[ "$keep_groups" == true ]]; then
    has_keep_groups=false
    for value in "${groups[@]}"; do
      [[ "$value" == keep-groups ]] && has_keep_groups=true
    done
    [[ "$has_keep_groups" == true ]] || create_args+=(--group-add keep-groups)
  fi
else
  create_args+=(--group-add keep-groups)
fi

has_memlock=false
for value in "${ulimits[@]}"; do
  create_args+=(--ulimit "$value")
  [[ "$value" == memlock=* ]] && has_memlock=true
done
[[ "$has_memlock" == true ]] || create_args+=(--ulimit memlock=-1:-1)
for value in "${secrets[@]}"; do create_args+=(--secret "$value"); done

# Create before removing the old container so image/config validation happens
# before any service downtime. No automatic retry changes Halogen's performance
# settings if startup later fails.
echo "halogen-update: recreating $CONTAINER from $IMAGE (config $CONFIG_VERSION, HALOGEN_CHECKPOINT=$CHECKPOINT, HALOGEN_MTP_HEAD=$MTP_HEAD, HALOGEN_TOKENIZER=$TOKENIZER, HALOGEN_VISION_TOWER=$VISION_TOWER, HALOGEN_TEMPERATURE=$TEMPERATURE, HALOGEN_TOP_P=$TOP_P, HALOGEN_TOP_K=$TOP_K, HALOGEN_MIN_P=$MIN_P, HALOGEN_PRESENCE_PENALTY=$PRESENCE_PENALTY, HALOGEN_ENABLE_THINKING=$ENABLE_THINKING, HALOGEN_REASONING_EFFORT=$REASONING_EFFORT, HALOGEN_DRAFTER_DEFAULT=$DRAFTER_DEFAULT, HALOGEN_FLASH_PIN_TRUNK=$PIN_TRUNK, HALOGEN_MAX_TOK=$MAX_TOK, HALOGEN_PREFILL_CHUNK=$PREFILL_CHUNK, HALOGEN_KV_POOL_POSITIONS=$KV_POOL_POSITIONS, HALOGEN_MAX_TOKENS_DEFAULT=$MAX_TOKENS_DEFAULT, HALOGEN_MAX_TOKENS_CAP=$MAX_TOKENS_CAP)"
podman create "${create_args[@]}" "$IMAGE" all >/dev/null
if [[ "$old_exists" == true ]]; then
  case "$old_state" in
    running|paused|pausing|stopping) podman stop --time 30 "$CONTAINER" >/dev/null ;;
  esac
  podman rm -f "$CONTAINER" >/dev/null
fi
podman rename "$temp_container" "$CONTAINER"
temp_container=""
podman start "$CONTAINER" >/dev/null
echo "halogen-update: $CONTAINER started; models remain at $MODELS (read-only mount)"
