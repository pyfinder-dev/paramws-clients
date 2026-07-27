"""Unit tests for the package-owned logger configuration."""
import contextlib
import importlib
import inspect
import io
import logging
import logging.handlers
import os
from pathlib import Path
import sys
import tempfile
import unittest


_MISSING = object()


class TestPackageLogger(unittest.TestCase):
    """Exercise logger configuration without leaking process-wide state."""

    def setUp(self):
        self.original_cwd = os.getcwd()
        self.original_log_file = os.environ.get("PARAMWS_LOG_FILE", _MISSING)
        self.package_logger = logging.getLogger("paramws")
        self.original_handlers = list(self.package_logger.handlers)
        self.original_level = self.package_logger.level
        self.original_propagate = self.package_logger.propagate
        self.original_disabled = self.package_logger.disabled
        self.original_attributes = {
            name: self.package_logger.__dict__.get(name, _MISSING)
            for name in ("ok", "OK", "finder", "FINDER")
        }
        self.root_logger = logging.getLogger()
        self.original_root_handlers = list(self.root_logger.handlers)
        self.original_root_level = self.root_logger.level
        self.original_logging_attributes = {
            name: logging.__dict__.get(name, _MISSING)
            for name in ("ok", "OK", "finder", "FINDER")
        }

        # Keep any pre-existing handler open but detached while temporary test
        # configurations replace the package-owned output.
        self.package_logger.handlers = []
        for name in self.original_attributes:
            self.package_logger.__dict__.pop(name, None)

        self.temp_directory = tempfile.TemporaryDirectory()
        os.chdir(self.temp_directory.name)
        os.environ.pop("PARAMWS_LOG_FILE", None)
        self.customlogger = importlib.import_module("paramws.utils.customlogger")
        self.original_output_mode = self.customlogger.OUTPUT_MODE
        self.customlogger._configure_logger("file")
        self.customlogger._remove_owned_handlers()
        Path("paramws.log").unlink(missing_ok=True)

    def tearDown(self):
        for handler in list(self.package_logger.handlers):
            self.package_logger.removeHandler(handler)
            if handler not in self.original_handlers:
                handler.close()

        self.package_logger.handlers = self.original_handlers
        self.package_logger.setLevel(self.original_level)
        self.package_logger.propagate = self.original_propagate
        self.package_logger.disabled = self.original_disabled
        for name, value in self.original_attributes.items():
            self.package_logger.__dict__.pop(name, None)
            if value is not _MISSING:
                self.package_logger.__dict__[name] = value

        self.root_logger.handlers = self.original_root_handlers
        self.root_logger.setLevel(self.original_root_level)
        for name, value in self.original_logging_attributes.items():
            logging.__dict__.pop(name, None)
            if value is not _MISSING:
                logging.__dict__[name] = value

        self.customlogger.OUTPUT_MODE = self.original_output_mode
        if self.original_log_file is _MISSING:
            os.environ.pop("PARAMWS_LOG_FILE", None)
        else:
            os.environ["PARAMWS_LOG_FILE"] = self.original_log_file
        os.chdir(self.original_cwd)
        self.temp_directory.cleanup()

    def _configure_file(self, path=None):
        if path is None:
            os.environ.pop("PARAMWS_LOG_FILE", None)
        else:
            os.environ["PARAMWS_LOG_FILE"] = str(path)
        return self.customlogger._configure_logger("file")

    def _flush_handlers(self):
        for handler in self.package_logger.handlers:
            handler.flush()

    def _read_log(self, path=None):
        self._flush_handlers()
        target = Path("paramws.log") if path is None else Path(path)
        return target.read_text(encoding="utf-8")

    def test_file_mode_is_the_visible_default(self):
        self.assertEqual(self.customlogger.OUTPUT_MODE, "file")
        self.customlogger._configure_logger()
        self.assertIsInstance(
            self.package_logger.handlers[0],
            logging.handlers.RotatingFileHandler,
        )

    def test_default_file_is_relative_to_the_working_directory(self):
        self._configure_file()
        self.package_logger.info("working-directory log")

        self.assertTrue(Path(self.temp_directory.name, "paramws.log").is_file())
        self.assertIn("working-directory log", self._read_log())

    def test_environment_variable_overrides_the_default_path(self):
        selected_path = Path(self.temp_directory.name, "selected", "package.log")
        selected_path.parent.mkdir()
        self._configure_file(selected_path)
        self.package_logger.info("selected path")

        self.assertIn("selected path", self._read_log(selected_path))
        self.assertFalse(Path("paramws.log").exists())

    def test_file_configuration_appends_existing_content(self):
        log_path = Path("append.log")
        log_path.write_text("existing content\n", encoding="utf-8")
        self._configure_file(log_path)
        self.package_logger.info("new content")

        output = self._read_log(log_path)
        self.assertTrue(output.startswith("existing content\n"))
        self.assertIn("new content", output)

    def test_file_logger_and_handler_use_debug_level_and_rotation_limits(self):
        self._configure_file()
        handler = self.package_logger.handlers[0]

        self.assertEqual(self.package_logger.level, logging.DEBUG)
        self.assertEqual(handler.level, logging.DEBUG)
        self.assertIsInstance(handler, logging.handlers.RotatingFileHandler)
        self.assertEqual(handler.maxBytes, 1_000_000)
        self.assertEqual(handler.backupCount, 7)
        self.assertEqual(handler.mode, "a")
        self.assertEqual(handler.encoding.lower().replace("-", ""), "utf8")

    def test_file_output_contains_standard_and_ok_records_without_ansi(self):
        self._configure_file()
        messages = {
            "DEBUG": self.package_logger.debug,
            "INFO": self.package_logger.info,
            "WARNING": self.package_logger.warning,
            "ERROR": self.package_logger.error,
            "CRITICAL": self.package_logger.critical,
            "OK": self.package_logger.ok,
        }
        for level_name, method in messages.items():
            method("%s record", level_name)

        output = self._read_log()
        for level_name in messages:
            self.assertIn(level_name, output)
            self.assertIn(level_name + " record", output)
        self.assertNotIn("\x1b[", output)

    def test_ok_uses_the_registered_level_name(self):
        self._configure_file()
        self.package_logger.ok("successful operation")

        self.assertEqual(
            logging.getLevelName(self.customlogger.OK_LOG_LEVEL),
            "OK",
        )
        self.assertIn("OK       successful operation", self._read_log())

    def test_reconfiguration_does_not_duplicate_handlers_or_messages(self):
        self._configure_file()
        self._configure_file()
        self._configure_file()
        self.package_logger.info("only once")

        self.assertEqual(len(self.package_logger.handlers), 1)
        self.assertEqual(self._read_log().count("only once"), 1)

    def test_root_logger_state_is_unchanged(self):
        root_stream = io.StringIO()
        root_handler = logging.StreamHandler(root_stream)
        self.root_logger.handlers = [root_handler]
        self.root_logger.setLevel(logging.ERROR)

        self.customlogger._configure_logger("file")

        self.assertEqual(self.root_logger.handlers, [root_handler])
        self.assertEqual(self.root_logger.level, logging.ERROR)

    def test_package_records_do_not_propagate_to_root_handlers(self):
        root_stream = io.StringIO()
        root_handler = logging.StreamHandler(root_stream)
        self.root_logger.handlers = [root_handler]
        self.root_logger.setLevel(logging.DEBUG)
        self._configure_file()

        self.package_logger.error("package-only record")
        root_handler.flush()

        self.assertFalse(self.package_logger.propagate)
        self.assertEqual(root_stream.getvalue(), "")

    def test_custom_methods_are_bound_only_to_the_package_logger(self):
        self._configure_file()

        self.assertTrue(callable(self.package_logger.ok))
        self.assertFalse(hasattr(self.package_logger, "OK"))
        self.assertFalse(hasattr(self.package_logger, "finder"))
        self.assertFalse(hasattr(self.package_logger, "FINDER"))
        for name in ("ok", "OK", "finder", "FINDER"):
            self.assertFalse(hasattr(logging, name))
        self.assertFalse(hasattr(logging.Logger, "ok"))

    def test_removed_custom_level_has_no_module_artifacts(self):
        self._configure_file()

        self.assertFalse(hasattr(self.customlogger, "FINDER_LOG_LEVEL"))
        self.assertNotEqual(
            logging.getLevelName(logging.INFO + 6),
            "FinDer",
        )
        self.assertNotIn("FinDer", self._read_log())

    def test_console_mode_emits_colored_standard_and_ok_records(self):
        stream = io.StringIO()
        with contextlib.redirect_stderr(stream):
            self.customlogger._configure_logger("console")

        messages = (
            (self.package_logger.debug, "debug"),
            (self.package_logger.info, "info"),
            (self.package_logger.warning, "warning"),
            (self.package_logger.error, "error"),
            (self.package_logger.critical, "critical"),
            (self.package_logger.ok, "ok"),
        )
        for method, message in messages:
            method(message)

        output = stream.getvalue()
        for message in ("debug", "info", "warning", "error", "critical", "ok"):
            self.assertIn(message, output)
        self.assertGreaterEqual(output.count("\x1b["), len(messages))
        self.assertIn("\x1b[92mOK", output)
        self.assertFalse(Path("paramws.log").exists())

    def test_unusable_file_falls_back_once_and_warns_with_the_cause(self):
        failed_path = Path(self.temp_directory.name, "missing", "paramws.log")
        os.environ["PARAMWS_LOG_FILE"] = str(failed_path)
        stream = io.StringIO()

        with contextlib.redirect_stderr(stream):
            configured = self.customlogger._configure_logger("file")

        output = stream.getvalue()
        self.assertIs(configured, self.package_logger)
        self.assertEqual(len(self.package_logger.handlers), 1)
        self.assertIsInstance(
            self.package_logger.handlers[0],
            logging.StreamHandler,
        )
        self.assertNotIsInstance(
            self.package_logger.handlers[0],
            logging.FileHandler,
        )
        self.assertIn(str(failed_path), output)
        self.assertIn("No such file or directory", output)
        self.assertIn("WARNING", output)
        self.assertFalse(failed_path.exists())

    def test_rotation_retains_no_more_than_seven_backups(self):
        log_path = Path("rotating.log")
        self._configure_file(log_path)
        payload = "x" * 1_000_010

        for index in range(10):
            self.package_logger.info("%s-%d", payload, index)

        self._flush_handlers()
        backups = list(Path(".").glob("rotating.log.*"))
        self.assertLessEqual(len(backups), 7)
        self.assertEqual(len(backups), 7)

    def test_ok_records_direct_and_explicit_stacklevel_callers(self):
        self._configure_file()
        direct_line = inspect.currentframe().f_lineno + 1
        self.package_logger.ok("direct caller")

        def report_for_caller():
            self.package_logger.ok("delegated caller", stacklevel=2)

        delegated_line = inspect.currentframe().f_lineno + 1
        report_for_caller()
        output = self._read_log()

        self.assertIn(
            "direct caller (test_customlogger.py:{})".format(direct_line),
            output,
        )
        self.assertIn(
            "delegated caller (test_customlogger.py:{})".format(delegated_line),
            output,
        )

    def test_module_reload_keeps_one_package_handler(self):
        self._configure_file()
        reloaded = importlib.reload(self.customlogger)
        reloaded._configure_logger()
        self.package_logger.info("after reload")

        self.assertIs(reloaded.logger, self.package_logger)
        self.assertEqual(len(self.package_logger.handlers), 1)
        self.assertEqual(self._read_log().count("after reload"), 1)


if __name__ == "__main__":
    unittest.main()
