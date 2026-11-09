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

"""Tests the shared download retry policy for CI scripts."""

import os
import pathlib
import subprocess
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
DOWNLOAD_WITH_RETRY = REPO_ROOT / "dev" / "ci" / "shared" / "download-with-retry"


class DownloadWithRetryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = pathlib.Path(self.temp_dir.name)
        self.bin_dir = root / "bin"
        self.bin_dir.mkdir()
        self.args_file = root / "curl-args"
        self.destination = root / "artifact"
        fake_curl = self.bin_dir / "curl"
        fake_curl.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$@\" > \"${FAKE_CURL_ARGS}\"\n"
            "if [[ \"${FAKE_CURL_EXIT:-0}\" == 0 ]]; then\n"
            "  touch \"${@: -1}\"\n"
            "fi\n"
            "exit \"${FAKE_CURL_EXIT:-0}\"\n",
            encoding="utf-8",
        )
        fake_curl.chmod(0o755)

    def run_helper(self, exit_code=0):
        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["FAKE_CURL_ARGS"] = str(self.args_file)
        env["FAKE_CURL_EXIT"] = str(exit_code)
        return subprocess.run(
            [
                str(DOWNLOAD_WITH_RETRY),
                "https://example.test/artifact",
                str(self.destination),
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_uses_five_minute_retry_policy(self):
        result = self.run_helper()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.destination.exists())
        self.assertEqual(
            self.args_file.read_text(encoding="utf-8").splitlines(),
            [
                "-fsSL",
                "--retry",
                "19",
                "--retry-delay",
                "15",
                "--retry-max-time",
                "300",
                "--retry-connrefused",
                "https://example.test/artifact",
                "-o",
                str(self.destination),
            ],
        )

    def test_returns_the_curl_failure(self):
        result = self.run_helper(exit_code=7)

        self.assertEqual(result.returncode, 7)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
