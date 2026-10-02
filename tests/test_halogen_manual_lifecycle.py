"""Regression checks for manual-only Halogen startup; never invoke real Podman."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UPDATER = Path(os.environ.get("HALOGEN_TEST_UPDATER", str(
    ROOT / "files/system/usr/share/turquoise/halogen-update.sh")))
WRAPPER = Path(os.environ.get("HALOGEN_TEST_WRAPPER", str(Path.home() / ".local/bin/halogen")))

FAKE_PODMAN = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps(args) + "\n")
mode = os.environ.get("FAKE_MODE", "update")
exists = os.environ.get("FAKE_EXISTS", "1") == "1"
state = os.environ.get("FAKE_STATE", "exited")
if args[:2] == ["container", "exists"]:
    sys.exit(0 if exists and args[2] == "halogen" else 1)
if args[:2] == ["image", "exists"]:
    sys.exit(0)
if args[:2] == ["image", "inspect"]:
    print("new-image")
elif args[0] == "inspect":
    if "--format" in args:
        if args[-1] != "halogen" or not exists:
            sys.exit(1)
        fmt = args[args.index("--format") + 1]
        if ".State.Status" in fmt:
            print(state)
        elif "halogen.variant" in fmt:
            print("iq4")
        elif "halogen.vision" in fmt:
            print("off")
        elif "halogen.max_tok" in fmt:
            print("8192")
        else:
            sys.exit("unexpected inspect format")
    else:
        print(Path(os.environ["FAKE_INSPECT"]).read_text())
elif args[0] in ("start", "run", "restart"):
    if mode == "update":
        sys.exit("UPDATER MUST NOT START HALOGEN")
    if args[0] == "run" and "--restart=no" not in args:
        sys.exit("new container must disable restarts")
elif args[0] == "update":
    if "--restart=no" not in args:
        sys.exit("existing container must disable restarts")
elif args[0] == "create":
    assert "--restart=no" in args, args
    assert "127.0.0.1:8731:8731" in args, args
    assert any(a.endswith(":/models:ro") for a in args), args
elif args[0] not in ("pull", "stop", "rm", "rename", "logs"):
    sys.exit("unexpected podman command: " + repr(args))
'''


class ManualLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        podman = self.bin / "podman"
        podman.write_text(FAKE_PODMAN)
        podman.chmod(0o755)
        curl = self.bin / "curl"
        curl.write_text('#!/bin/sh\nprintf \'{"status":"ok"}\\n\'\n')
        curl.chmod(0o755)
        self.models = self.root / "models"
        (self.models / "UD-IQ4_XS").mkdir(parents=True)
        (self.models / "UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf").touch()
        (self.models / "qwen38-flash-next-mtp.hgn").touch()
        (self.models / "tokenizer").mkdir()
        (self.models / "tokenizer/tokenizer.json").write_text("{}")
        self.log = self.root / "calls.jsonl"
        self.inspect = self.root / "inspect.json"
        # Do not inherit exported Podman functions or engine overrides.
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("BASH_FUNC_", "HALOGEN_")) and k != "SUDO_USER"}
        self.env.update(
            PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
            FAKE_LOG=str(self.log), FAKE_INSPECT=str(self.inspect),
            HALOGEN_MODELS=str(self.models), HALOGEN_IQ4_MODELS=str(self.models),
            HALOGEN_VISION_TOWER="", HALOGEN_EVICT_LEMONADE="0", FORCE="false",
        )

    def fixture(self, state="exited", image="new-image", version="13-text"):
        self.env["FAKE_STATE"] = state
        self.inspect.write_text(json.dumps([{
            "Image": image, "State": {"Status": state},
            "Config": {"Labels": {"io.turquoise.halogen-config-version": version}},
            "HostConfig": {
                "IpcMode": "host", "NetworkMode": "default",
                "RestartPolicy": {"Name": "always", "MaximumRetryCount": 0},
                "Devices": ["/dev/kfd", "/dev/dri"],
            },
        }]))

    def run_script(self, script, *args):
        result = subprocess.run(["bash", str(script), *args], env=self.env,
                                input="", text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_unchanged_preserves_stopped_and_running_state(self):
        for state in ("exited", "running"):
            with self.subTest(state=state):
                self.log.unlink(missing_ok=True)
                self.fixture(state=state)
                calls = self.run_script(UPDATER)
                self.assertIn(["update", "--restart=no", "halogen"], calls)
                self.assertFalse(any(c[0] in ("create", "start", "run", "restart", "stop")
                                     for c in calls))

    def test_recreation_always_leaves_container_stopped(self):
        cases = [
            ("exited", "old-image", "13-text", False),
            ("running", "old-image", "13-text", False),
            ("exited", "new-image", "12-text", False),
            ("running", "new-image", "13-text", True),
        ]
        for state, image, version, force in cases:
            with self.subTest(state=state, image=image, version=version, force=force):
                self.log.unlink(missing_ok=True)
                self.fixture(state, image, version)
                self.env["FORCE"] = str(force).lower()
                calls = self.run_script(UPDATER)
                creates = [c for c in calls if c[0] == "create"]
                self.assertEqual(len(creates), 1)
                self.assertIn("--restart=no", creates[0])
                self.assertFalse(any(c[0] in ("start", "run", "restart") for c in calls))
                self.assertEqual(any(c[0] == "stop" for c in calls), state == "running")

    @unittest.skipUnless(Path("/dev/kfd").exists() and Path("/dev/dri").exists(),
                         "first-time provision requires AMD device paths")
    def test_first_provision_does_not_start(self):
        self.env["FAKE_EXISTS"] = "0"
        calls = self.run_script(UPDATER)
        self.assertTrue(any(c[0] == "create" for c in calls))
        self.assertFalse(any(c[0] in ("start", "run", "restart") for c in calls))

    def test_explicit_start_repairs_existing_policy(self):
        self.env["FAKE_MODE"] = "wrapper"
        calls = self.run_script(WRAPPER, "start", "iq4", "off", "8k")
        repair = ["update", "--restart=no", "halogen"]
        launch = ["start", "halogen"]
        self.assertIn(repair, calls)
        self.assertIn(launch, calls)
        self.assertLess(calls.index(repair), calls.index(launch))

    def test_explicit_ensure_still_works(self):
        self.env["FAKE_MODE"] = "wrapper"
        calls = self.run_script(WRAPPER, "ensure", "iq4", "off", "8k")
        self.assertIn(["start", "halogen"], calls)

    def test_explicit_start_creates_manual_only_container(self):
        self.env.update(FAKE_MODE="wrapper", FAKE_EXISTS="0")
        calls = self.run_script(WRAPPER, "start", "iq4", "off", "8k")
        launches = [c for c in calls if c[0] == "run"]
        self.assertEqual(len(launches), 1)
        self.assertIn("--restart=no", launches[0])
        self.assertIn("127.0.0.1:8731:8731", launches[0])
        self.assertIn(str(self.models) + ":/models:ro", launches[0])

    def test_status_and_stop_never_start(self):
        for command in ("status", "stop"):
            with self.subTest(command=command):
                self.log.unlink(missing_ok=True)
                calls = self.run_script(WRAPPER, command)
                self.assertFalse(any(c[0] in ("start", "run", "restart", "create") for c in calls))


if __name__ == "__main__":
    unittest.main()
