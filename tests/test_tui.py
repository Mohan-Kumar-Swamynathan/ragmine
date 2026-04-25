"""
tests/test_tui.py
~~~~~~~~~~~~~~~~~
Tests for Textual TUI.
"""

import pytest


class TestTUIApp:
    """Tests for TUI app."""

    def test_tui_import(self):
        from ragmine.tui.app import RagmineTUI
        assert RagmineTUI is not None

    def test_tui_css(self):
        from ragmine.tui.app import RagmineTUI

        app = RagmineTUI()
        assert "#chat-container" in app.CSS
        assert "#messages" in app.CSS
        assert "#input-area" in app.CSS

    def test_tui_bindings(self):
        from ragmine.tui.app import RagmineTUI

        app = RagmineTUI()
        binding_actions = [b.action for b in app.BINDINGS]
        assert "quit" in binding_actions