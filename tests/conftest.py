import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "open-local" / "scripts"))
FIX = pathlib.Path(__file__).parent / "fixtures"

from openlocal import net, registry  # noqa: E402


@pytest.fixture(autouse=True)
def own_cache_folder(monkeypatch, tmp_path):
    """Tests never read or write the real ~/.cache."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))


@pytest.fixture
def reg():
    return registry.Registry(registry.build(FIX / "registry"))


class FakeNet:
    """Stands in for the network: a dict of url -> (status, bytes or fixture name)."""

    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, url, **kw):
        self.calls.append(url)
        net.check_url(url)
        if url not in self.pages:
            raise net.FetchError("not found in fake network")
        status, body = self.pages[url]
        if isinstance(body, str):
            body = (FIX / body).read_bytes()
        return net.Response(url, status, {"content-type": "text/html; charset=utf-8"}, body)


@pytest.fixture
def fake_net(monkeypatch):
    def make(pages):
        f = FakeNet(pages)
        monkeypatch.setattr(net, "fetch", f)
        return f
    return make
