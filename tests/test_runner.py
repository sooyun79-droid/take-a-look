import subprocess
import tempfile
import unittest
from unittest.mock import patch

from take_a_look.runner import run_suite


class RunnerTests(unittest.TestCase):
    def run_fake(self, content, code=0, running=False):
        instances = []

        class Process:
            def __init__(self, argv, stdout, stderr, env, shell):
                self.argv, self.env = argv, env
                self.returncode = None if running else code
                stderr.write(content)
                stderr.flush()
                instances.append(self)

            def poll(self):
                return self.returncode

            def kill(self):
                self.returncode = -9

            def wait(self, timeout):
                return self.returncode

        with patch("take_a_look.runner.shutil.which", return_value="docker"), patch("take_a_look.runner.subprocess.Popen", Process), patch("take_a_look.runner.subprocess.run") as cleanup, patch.dict("os.environ", {"API_KEY": "private-value", "DOCKER_HOST": "tcp://external"}):
            result = run_suite({"test_x.py": b"pass"}, "sha256:" + "a" * 64, timeout=0 if running else 45)
        self.assertNotIn("API_KEY", instances[0].env)
        self.assertNotIn("DOCKER_HOST", instances[0].env)
        cleanup.assert_called_once()
        self.assertEqual(cleanup.call_args.args[0][1:3], ["rm", "-f"])
        return result

    def test_suite_output_structural_only(self):
        result = self.run_fake(b"TOP_SECRET_RAW_DATA\nRan 2 tests in 0.001s\n\nOK\n")
        self.assertEqual(result.outcome, "passed")
        self.assertEqual(result.details["test_count"], 2)
        self.assertNotIn("TOP_SECRET", str(result))

    def test_zero_tests_and_missing_counts_are_not_pass(self):
        for content in (b"Ran 0 tests in 0.001s\nOK\n", b"no test framework output"):
            self.assertEqual(self.run_fake(content).outcome, "no_tests")

    def test_timeout_stops_container_and_records_failure(self):
        result = self.run_fake(b"", running=True)
        self.assertEqual(result.outcome, "stopped")
        self.assertEqual(result.details["reason_code"], "TIMEOUT")

    def test_suite_exit_failure_not_lost(self):
        result = self.run_fake(b"Ran 2 tests in 0.001s\nFAILED\n", code=1)
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.exit_code, 1)


if __name__ == "__main__":
    unittest.main()
