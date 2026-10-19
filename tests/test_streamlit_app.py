import pytest


def test_ui_analysis_actions_render_without_exceptions(monkeypatch):
    pytest.importorskip("streamlit")
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("SPN_DC_NO_PERSIST", "1")
    app_path = Path(__file__).resolve().parents[1] / "spn_dc" / "streamlit_app.py"
    app = AppTest.from_file(str(app_path)).run()
    assert not app.exception
    for label in (
        "Create / reset cipher",
        "Random P-layer",
        "Randomize all S-boxes",
        "Propagate",
        "Generate paths",
        "Run constraint check",
        "Identity P",
    ):
        next(button for button in app.button if button.label == label).click().run()
        assert not app.exception, [error.message for error in app.exception]
