"""The app wires together and registers its tools (no DB needed at import)."""


def test_app_builds_and_registers_tools():
    from one.ai.registry import registry
    from one.main import create_app

    app = create_app()
    assert app.title == "Nettcom ONE"

    names = {t.name for t in registry.list()}
    assert "ledger.post_move" in names


def test_sequence_formatting():
    from one.sequences.service import format_value

    assert format_value("NF-", 5, 42) == "NF-00042"
