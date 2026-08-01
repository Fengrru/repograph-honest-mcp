"""
Knowledge base of dependency APIs for RepoGraph-Honest.

Loads API signatures from installed packages via ``pydoc`` / AST inspection
and stores them for fast lookup during hallucination checks.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class APISignature:
    name: str
    signature: str = ""
    doc: str = ""
    module: str = ""


class APIKnowledgeBase:
    """Lightweight cache of public API signatures for known packages."""

    def __init__(self):
        self._lock = threading.RLock()
        self.apis: dict[str, APISignature] = {}
        self._loaded_packages: set[str] = set()

    def load_package(self, package_name: str) -> int:
        """Extract public API signatures from an installed package.

        Imports happen outside the lock to avoid blocking concurrent readers,
        but the shared cache is updated under the lock.
        """
        with self._lock:
            if package_name in self._loaded_packages:
                return sum(1 for v in self.apis.values() if v.module.startswith(package_name))
            self._loaded_packages.add(package_name)

        try:
            mod = importlib.import_module(package_name)
        except Exception as e:  # noqa: BLE001
            logger.warning("Cannot import %s: %s", package_name, e)
            with self._lock:
                self._loaded_packages.discard(package_name)
            return 0

        new_apis: dict[str, APISignature] = {}
        seen: set[str] = set()
        count = self._collect_from_module(mod, package_name, package_name, new_apis, seen)

        # Recurse into submodules (one level) to enrich the base.
        try:
            paths = getattr(mod, "__path__", None)
            if paths is not None:
                for info in pkgutil.iter_modules(paths):
                    if info.name.startswith("_"):
                        continue
                    sub = f"{package_name}.{info.name}"
                    try:
                        submod = importlib.import_module(sub)
                    except Exception as e:  # noqa: BLE001
                        logger.debug("Cannot import submodule %s: %s", sub, e)
                        continue
                    count += self._collect_from_module(submod, sub, sub, new_apis, seen)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to enumerate submodules of %s: %s", package_name, e)

        with self._lock:
            self.apis.update(new_apis)

        logger.info("Loaded %d APIs from %s", count, package_name)
        return count

    def _collect_from_module(
        self,
        mod,
        module_name: str,
        api_module: str,
        out: dict[str, APISignature],
        seen: set[str],
    ) -> int:
        """Collect public attributes from a module into *out*.

        Returns the number of newly added signatures.
        """
        count = 0
        try:
            names = dir(mod)
        except Exception as e:  # noqa: BLE001
            logger.warning("dir(%s) failed: %s", module_name, e)
            return 0

        for name in names:
            if name.startswith("_"):
                continue
            full = f"{api_module}.{name}"
            if full in seen:
                continue
            seen.add(full)
            try:
                obj = getattr(mod, name)
                sig = self._signature(obj)
            except Exception:  # noqa: BLE001
                sig = ""
            out[full] = APISignature(name=full, signature=sig, module=api_module)
            count += 1
        return count

    @staticmethod
    def _signature(obj) -> str:
        try:
            import inspect

            return str(inspect.signature(obj))
        except (TypeError, ValueError):
            return ""

    def get(self, name: str) -> APISignature | None:
        with self._lock:
            return self.apis.get(name)

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self.apis

    def search(self, prefix: str, limit: int = 10) -> list[str]:
        with self._lock:
            return [k for k in self.apis if k.startswith(prefix)][:limit]

    def all_names(self) -> set[str]:
        with self._lock:
            return set(self.apis.keys())
