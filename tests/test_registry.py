# tests/test_registry.py
from plugins.registry import PluginRegistry, PluginInfo


class FakeSource:
    def discover(self, query):
        return []

    def fetch_full(self, story):
        return story


class NotAPlugin:
    pass


def test_register_and_lookup():
    reg = PluginRegistry()
    info = PluginInfo(
        name="fake", version="0.1", contract="content_source",
        label="Fake", instance=FakeSource(), config={},
    )
    assert reg.register(info) is True
    assert reg.get("content_source", "Fake") is info.instance


def test_unknown_contract_rejected():
    reg = PluginRegistry()
    info = PluginInfo(
        name="x", version="0.1", contract="bogus",
        label="X", instance=FakeSource(), config={},
    )
    assert reg.register(info) is False


def test_does_not_satisfy_contract_rejected():
    reg = PluginRegistry()
    info = PluginInfo(
        name="x", version="0.1", contract="llm_provider",
        label="X", instance=NotAPlugin(), config={},
    )
    assert reg.register(info) is False


def test_duplicate_label_disabled():
    reg = PluginRegistry()
    info1 = PluginInfo(name="a", version="0.1", contract="content_source",
                       label="Dup", instance=FakeSource(), config={})
    info2 = PluginInfo(name="b", version="0.1", contract="content_source",
                       label="Dup", instance=FakeSource(), config={})
    assert reg.register(info1) is True
    assert reg.register(info2) is False


def test_active_returns_first_registered():
    reg = PluginRegistry()
    inst = FakeSource()
    reg.register(PluginInfo(name="a", version="0.1", contract="content_source",
                            label="A", instance=inst, config={}))
    assert reg.active("content_source") is inst
    assert reg.active("publisher") is None
