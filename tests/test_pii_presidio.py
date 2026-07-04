"""Presidio PII backend (PII_BACKEND=presidio) and its regex fallback."""

import sys
import types

from app.services.pii_detector import detect_pii


class _FakeResult:
    def __init__(self, entity_type, start, end, score):
        self.entity_type = entity_type
        self.start = start
        self.end = end
        self.score = score


def _install_fake_presidio(monkeypatch, results):
    """Inject fake presidio_analyzer modules returning scripted results."""

    class FakeAnalyzer:
        def analyze(self, text, language, entities=None):
            self.last_entities = entities
            return results

    fake_analyzer = FakeAnalyzer()

    class FakeAnalyzerEngine:
        def __init__(self, nlp_engine=None):
            pass

        def analyze(self, text, language, entities=None):
            return fake_analyzer.analyze(text, language, entities)

    class FakeProvider:
        def __init__(self, nlp_configuration=None):
            pass

        def create_engine(self):
            return object()

    mod = types.ModuleType("presidio_analyzer")
    mod.AnalyzerEngine = FakeAnalyzerEngine
    nlp_mod = types.ModuleType("presidio_analyzer.nlp_engine")
    nlp_mod.NlpEngineProvider = FakeProvider
    monkeypatch.setitem(sys.modules, "presidio_analyzer", mod)
    monkeypatch.setitem(sys.modules, "presidio_analyzer.nlp_engine", nlp_mod)

    # the engine is cached; reset between tests
    from app.services import pii_presidio

    pii_presidio._analyzer.cache_clear()
    return fake_analyzer


def test_presidio_backend_maps_entities(monkeypatch):
    text = "Mail john@example.com now"
    monkeypatch.setenv("PII_BACKEND", "presidio")
    _install_fake_presidio(
        monkeypatch, [_FakeResult("EMAIL_ADDRESS", 5, 21, 0.99)]
    )

    out = detect_pii(text)
    assert out["pii_backend"] == "presidio"
    assert out["total"] == 1
    e = out["entities"][0]
    assert e["type"] == "email"
    assert e["span"] == [5, 21]
    assert e["score"] == 0.99
    assert "@" not in e["value_preview"] or "*" in e["value_preview"]
    assert out["counts"] == {"email": 1}


def test_presidio_threshold_filters_low_scores(monkeypatch):
    monkeypatch.setenv("PII_BACKEND", "presidio")
    monkeypatch.setenv("PII_PRESIDIO_THRESHOLD", "0.8")
    _install_fake_presidio(
        monkeypatch,
        [
            _FakeResult("EMAIL_ADDRESS", 0, 5, 0.95),
            _FakeResult("PERSON", 6, 10, 0.4),
        ],
    )

    out = detect_pii("abcde fghi")
    assert out["total"] == 1
    assert out["types_present"] == ["email"]


def test_presidio_types_filter_translates_to_entities(monkeypatch):
    monkeypatch.setenv("PII_BACKEND", "presidio")
    fake = _install_fake_presidio(
        monkeypatch, [_FakeResult("EMAIL_ADDRESS", 0, 5, 0.9)]
    )

    detect_pii("abcde", types=["email", "phone"])
    assert fake.last_entities == ["EMAIL_ADDRESS", "PHONE_NUMBER"]


def test_presidio_unavailable_falls_back_to_regex(monkeypatch):
    # No fake modules installed and presidio import fails -> regex baseline.
    monkeypatch.setenv("PII_BACKEND", "presidio")
    import builtins

    real_import = builtins.__import__

    def _no_presidio(name, *a, **k):
        if name.startswith("presidio_analyzer"):
            raise ImportError("presidio not installed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _no_presidio)
    from app.services import pii_presidio

    pii_presidio._analyzer.cache_clear()

    out = detect_pii("Contact john@example.com")
    assert out["pii_backend"] == "regex"
    assert out["counts"].get("email") == 1


def test_default_backend_is_regex(monkeypatch):
    monkeypatch.delenv("PII_BACKEND", raising=False)
    out = detect_pii("Contact john@example.com")
    assert out["pii_backend"] == "regex"
    assert out["total"] >= 1
