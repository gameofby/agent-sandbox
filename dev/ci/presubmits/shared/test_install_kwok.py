#!/usr/bin/env python3
# Copyright 2026 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests independent caching for the KWOK binaries."""

import os
import pathlib
import subprocess
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
INSTALL_KWOK = REPO_ROOT / "dev" / "ci" / "shared" / "install-kwok"


class InstallKwokTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = pathlib.Path(self.temp_dir.name)
        self.bin_dir = root / "bin"
        self.bin_dir.mkdir()
        self.curl_bin = root / "curl-bin"
        self.curl_bin.mkdir()
        self.calls_file = root / "curl-calls"
        fake_curl = self.curl_bin / "curl"
        fake_curl.write_text(
            "#!/usr/bin/env bash\n"
            "for arg in \"$@\"; do\n"
            "  if [[ \"$arg\" == https://* ]]; then\n"
            "    printf '%s\\n' \"$arg\" >> \"${FAKE_CURL_CALLS}\"\n"
            "  fi\n"
            "done\n"
            "touch \"${@: -1}\"\n",
            encoding="utf-8",
        )
        fake_curl.chmod(0o755)

    def run_installer(self):
        env = os.environ.copy()
        env["PATH"] = f"{self.curl_bin}:{env['PATH']}"
        env["FAKE_CURL_CALLS"] = str(self.calls_file)
        return subprocess.run(
            [str(INSTALL_KWOK), "v0.6.0", str(self.bin_dir)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_downloads_each_missing_binary(self):
        result = self.run_installer()

        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("kwokctl", "kwok"):
            binary = self.bin_dir / name
            self.assertTrue(binary.is_file())
            self.assertTrue(os.access(binary, os.X_OK))
        self.assertEqual(
            self.calls_file.read_text(encoding="utf-8").splitlines(),
            [
                "https://github.com/kubernetes-sigs/kwok/releases/download/"
                "v0.6.0/kwokctl-linux-amd64",
                "https://github.com/kubernetes-sigs/kwok/releases/download/"
                "v0.6.0/kwok-linux-amd64",
            ],
        )

    def test_installs_a_missing_binary_when_the_other_is_cached(self):
        kwokctl = self.bin_dir / "kwokctl"
        kwokctl.write_text("cached", encoding="utf-8")
        kwokctl.chmod(0o755)

        result = self.run_installer()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(kwokctl.read_text(encoding="utf-8"), "cached")
        self.assertTrue((self.bin_dir / "kwok").is_file())
        self.assertEqual(
            self.calls_file.read_text(encoding="utf-8").splitlines(),
            [
                "https://github.com/kubernetes-sigs/kwok/releases/download/"
                "v0.6.0/kwok-linux-amd64",
            ],
        )


if __name__ == "__main__":
    unittest.main()
