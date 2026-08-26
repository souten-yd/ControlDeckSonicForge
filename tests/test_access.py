from sonicforge.access import local_access_mode, peer_is_trusted


def test_trusted_network_accepts_loopback_private_and_tailscale(monkeypatch):
    monkeypatch.setenv("SONICFORGE_LOCAL_ACCESS", "trusted-network")
    assert local_access_mode() == "trusted-network"
    assert peer_is_trusted(peer_host="127.0.0.1", bind_host="0.0.0.0")
    assert peer_is_trusted(peer_host="192.168.68.57", bind_host="0.0.0.0")
    assert peer_is_trusted(peer_host="10.0.0.3", bind_host="0.0.0.0")
    assert peer_is_trusted(peer_host="100.64.12.3", bind_host="0.0.0.0")
    assert not peer_is_trusted(peer_host="8.8.8.8", bind_host="0.0.0.0")


def test_loopback_bind_remains_usable_with_non_ip_test_adapter(monkeypatch):
    monkeypatch.setenv("SONICFORGE_LOCAL_ACCESS", "trusted-network")
    assert peer_is_trusted(peer_host="testclient", bind_host="127.0.0.1")


def test_strict_and_open_modes_are_explicit(monkeypatch):
    monkeypatch.setenv("SONICFORGE_LOCAL_ACCESS", "strict")
    assert peer_is_trusted(peer_host="127.0.0.1", bind_host="127.0.0.1")
    assert not peer_is_trusted(peer_host="192.168.1.10", bind_host="0.0.0.0")

    monkeypatch.setenv("SONICFORGE_LOCAL_ACCESS", "open")
    assert peer_is_trusted(peer_host="8.8.8.8", bind_host="0.0.0.0")
