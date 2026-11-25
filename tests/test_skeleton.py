"""M1 smoke test: every engine module imports cleanly."""

import importlib

import pytest

MODULES = [
    "dcf",
    "dcf.exceptions",
    "dcf.loader",
    "dcf.historical",
    "dcf.forecast",
    "dcf.wacc",
    "dcf.terminal",
    "dcf.valuation",
    "dcf.sensitivity",
    "dcf.scenarios",
    "dcf.montecarlo",
    "dcf.peers",
    "dcf.export",
    "dcf.explainer",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str) -> None:
    assert importlib.import_module(name) is not None
