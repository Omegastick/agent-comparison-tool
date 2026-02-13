"""Tests for container module utilities."""

from act.container import parse_activity_line


class TestParseActivityLine:
    def test_glob_tool_with_ansi(self):
        line = "\x1b[32m✱ Glob\x1b[0m found 3 files"
        assert parse_activity_line(line) == "✱ Glob found 3 files"

    def test_read_tool_with_ansi(self):
        line = "\x1b[34m→ Read\x1b[0m src/main.py"
        assert parse_activity_line(line) == "→ Read src/main.py"

    def test_write_tool_with_ansi(self):
        line = "\x1b[34m← Write\x1b[0m src/output.py"
        assert parse_activity_line(line) == "← Write src/output.py"

    def test_bash_tool_with_ansi(self):
        line = "\x1b[33m$ git status\x1b[0m"
        assert parse_activity_line(line) == "$ git status"

    def test_settings_tool(self):
        line = "⚙ Settings updated"
        assert parse_activity_line(line) == "⚙ Settings updated"

    def test_plain_tool_prefix_no_ansi(self):
        line = "✱ Glob **/*.py"
        assert parse_activity_line(line) == "✱ Glob **/*.py"

    def test_non_tool_line_returns_none(self):
        line = "Starting benchmark run..."
        assert parse_activity_line(line) is None

    def test_empty_line_returns_none(self):
        assert parse_activity_line("") is None

    def test_ansi_only_returns_none(self):
        assert parse_activity_line("\x1b[32m\x1b[0m") is None

    def test_line_with_nested_ansi_codes(self):
        line = "\x1b[1m\x1b[34m→ Read\x1b[0m\x1b[0m /workspace/src/main.py"
        assert parse_activity_line(line) == "→ Read /workspace/src/main.py"

    def test_whitespace_stripped(self):
        line = "  \x1b[32m✱ Glob\x1b[0m results  \n"
        assert parse_activity_line(line) == "✱ Glob results"

    def test_bullet_task_with_ansi(self):
        line = "\x1b[0m• \x1b[0mCreate Speckit plan\x1b[90m General Agent\x1b[0m"
        assert parse_activity_line(line) == "• Create Speckit plan General Agent"

    def test_regular_log_with_ansi_returns_none(self):
        line = "\x1b[32mINFO\x1b[0m: Container started successfully"
        assert parse_activity_line(line) is None
