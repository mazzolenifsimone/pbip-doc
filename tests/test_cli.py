"""
Unit tests for CLI commands in pbip_doc.cli.
Vanilla Python unittest suite.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pbip_doc.cli import main, build_parser
from pbip_doc.docgen.config import DocGenConfig


class TestCLIReportInspect(unittest.TestCase):
    def setUp(self):
        self.sample_root = Path(__file__).resolve().parent.parent / "samples" / "Ecommerce_Sales"
        self.report_folder = self.sample_root / "Ecommerce Sales.Report"

    def test_report_inspect_on_report_folder(self):
        """Verifies report-inspect succeeds on .Report directory without UnboundLocalError."""
        self.assertTrue(self.report_folder.exists(), f"Sample folder missing: {self.report_folder}")
        stdout_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            exit_code = main(["report-inspect", str(self.report_folder)])
        output = stdout_buf.getvalue()
        self.assertEqual(exit_code or 0, 0)
        self.assertIn("PBIP REPORT: Ecommerce Sales", output)
        self.assertIn("PAGE: 'Executive Summary'", output)
        self.assertIn("PAGE: 'Customer Analytics'", output)

    def test_report_inspect_on_solution_root(self):
        """Verifies report-inspect succeeds on PBIP solution root directory."""
        self.assertTrue(self.sample_root.exists(), f"Sample root missing: {self.sample_root}")
        stdout_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            exit_code = main(["report-inspect", str(self.sample_root)])
        output = stdout_buf.getvalue()
        self.assertEqual(exit_code or 0, 0)
        self.assertIn("PBIP REPORT: Ecommerce Sales", output)
        self.assertIn("PAGE: 'Executive Summary'", output)
        self.assertIn("PAGE: 'Customer Analytics'", output)

    def test_cli_prog_name_and_help(self):
        """Verifies CLI prog name is pbip-doc and help reflects offline HTML Wiki Portal."""
        parser = build_parser()
        self.assertEqual(parser.prog, "pbip-doc")
        help_buf = io.StringIO()
        with contextlib.redirect_stdout(help_buf):
            parser.print_help()
        help_text = help_buf.getvalue()
        self.assertIn("pbip-doc", help_text)
        self.assertIn("HTML Wiki Portal", help_text)
        self.assertIn("Markdown docs", help_text)


class TestCLIEarlyValidationAndConfigWarnings(unittest.TestCase):
    def test_docgen_nonexistent_path_fails_early_without_progress(self):
        """Verifies docgen exits immediately with code 1 and no [1/4] progress when path does not exist."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            with self.assertRaises(SystemExit) as ctx:
                main(["docgen", "non_existent_pbip_folder_xyz"])
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("[ERROR] Path not found: non_existent_pbip_folder_xyz", stderr_buf.getvalue())
        self.assertNotIn("[1/4]", stdout_buf.getvalue())

    def test_inspect_and_report_inspect_nonexistent_path_fail_early(self):
        """Verifies inspect and report-inspect reject nonexistent paths immediately with code 1."""
        for cmd in ("inspect", "report-inspect"):
            stderr_buf = io.StringIO()
            with contextlib.redirect_stderr(stderr_buf):
                with self.assertRaises(SystemExit) as ctx:
                    main([cmd, "missing_input_path_xyz"])
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("[ERROR] Path not found: missing_input_path_xyz", stderr_buf.getvalue())

    def test_config_from_dict_and_file_warns_on_unknown_keys(self):
        """Verifies DocGenConfig.from_dict() and from_file() warn on stderr for unknown keys with suggestions."""
        stderr_buf = io.StringIO()
        with contextlib.redirect_stderr(stderr_buf):
            cfg = DocGenConfig.from_dict({
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": "Test Config",
                "description": "Metadata",
                "_comment": "Ignore me",
                "//": "Also ignore",
                "theme": "dark",
                "totally_unknown_key": True,
            })
        warn_out = stderr_buf.getvalue()
        self.assertIsInstance(cfg, DocGenConfig)
        self.assertIn("[WARNING]", warn_out)
        self.assertIn("'theme' (did you mean 'html_theme'?)", warn_out)
        self.assertIn("'totally_unknown_key'", warn_out)
        self.assertNotIn("$schema", warn_out)
        self.assertNotIn("title", warn_out)
        self.assertNotIn("description", warn_out)
        self.assertNotIn("_comment", warn_out)

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "pbip_doc.config.json"
            cfg_path.write_text(json.dumps({"format": "both", "html_theme": "light"}), encoding="utf-8")
            stderr_buf_file = io.StringIO()
            with contextlib.redirect_stderr(stderr_buf_file):
                cfg_file = DocGenConfig.from_file(str(cfg_path))
            file_warn = stderr_buf_file.getvalue()
            self.assertEqual(cfg_file.html_theme, "light")
            self.assertIn("[WARNING]", file_warn)
            self.assertIn("'format' (did you mean 'output_format'?)", file_warn)


if __name__ == "__main__":
    unittest.main()
