# plugins/registry.py
import logging
from dataclasses import dataclass, field
from typing import Any

from plugins.contracts import CONTRACTS

log = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    name: str
    version: str
    contract: str
    label: str
    instance: Any
    config: dict = field(default_factory=dict)


class PluginRegistry:
    """Registers plugin instances under their contract, validating duck-typing.

    Built-in implementations are registered the same way external plugins are,
    so e.g. Reddit is "just the first content source".
    """

    def __init__(self) -> None:
        self._by_contract: dict[str, dict[str, PluginInfo]] = {}

    def register(self, info: PluginInfo) -> bool:
        contract_cls = CONTRACTS.get(info.contract)
        if contract_cls is None:
            log.warning("unknown contract %r for plugin %r", info.contract, info.name)
            return False
        try:
            ok = isinstance(info.instance, contract_cls)
        except Exception as e:
            log.warning("plugin %r contract check failed: %s", info.name, e)
            return False
        if not ok:
            log.warning("plugin %r does not satisfy contract %r", info.name, info.contract)
            return False
        bucket = self._by_contract.setdefault(info.contract, {})
        if info.label in bucket:
            log.warning("duplicate plugin label %r under %r — disabling",
                        info.label, info.contract)
            return False
        bucket[info.label] = info
        log.info("registered plugin %r (%s %s)", info.name, info.contract, info.version)
        return True

    def get(self, contract: str, label: str) -> Any | None:
        bucket = self._by_contract.get(contract, {})
        info = bucket.get(label)
        return info.instance if info else None

    def list(self, contract: str) -> list[PluginInfo]:
        return list(self._by_contract.get(contract, {}).values())

    def active(self, contract: str, label: str | None = None) -> Any | None:
        """Return the active instance for a contract, or None.

        If `label` is given, return that specific plugin; otherwise return the
        first registered one (the active-selection UI in Settings will refine
        this in later phases).
        """
        bucket = self._by_contract.get(contract, {})
        if label:
            info = bucket.get(label)
            return info.instance if info else None
        if bucket:
            return next(iter(bucket.values())).instance
        return None
