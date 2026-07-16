"""Lifecycle-state enrichment of engines_status (port-join with aisctl serve)."""

from __future__ import annotations

from asiai.collectors import snapshot as snap


def _detected(url: str, name: str = "llamacpp") -> dict:
    return {
        "name": name,
        "url": url,
        "reachable": True,
        "version": "b123",
        "models": [{"name": "m.gguf"}],
        "vram_total": 1,
    }


class TestMergeLifecycleStates:
    def test_no_serve_keeps_statuses_untouched(self, monkeypatch):
        monkeypatch.setattr(snap, "_fetch_lifecycle_states", lambda: None)
        statuses = [_detected("http://localhost:8090")]
        out = snap._merge_lifecycle_states(statuses)
        assert out == statuses
        assert "state" not in out[0]

    def test_port_join_adds_state_and_engine_id(self, monkeypatch):
        monkeypatch.setattr(
            snap,
            "_fetch_lifecycle_states",
            lambda: [
                {
                    "name": "llamacpp-aux-1",
                    "display": "llama.cpp aux #1 (port 8090)",
                    "port": 8090,
                    "state": "running",
                    "model": "Qwen3-4B.gguf",
                }
            ],
        )
        out = snap._merge_lifecycle_states([_detected("http://localhost:8090")])
        assert out[0]["state"] == "running"
        # The manifest name is the write-funnel identifier: an action from
        # this card must target llamacpp-aux-1, never the detection alias.
        assert out[0]["engine_id"] == "llamacpp-aux-1"
        assert out[0]["display_hint"].startswith("llama.cpp aux")
        assert out[0]["model"] == "Qwen3-4B.gguf"  # propagated from the node

    def test_unmatched_manifest_appended_as_stopped_entry(self, monkeypatch):
        monkeypatch.setattr(
            snap,
            "_fetch_lifecycle_states",
            lambda: [
                {"name": "ollama", "display": "Ollama", "port": 11434, "state": "stopped"},
                {"name": "tq-vision", "display": "TQ vision", "port": 8093, "state": "disabled"},
            ],
        )
        out = snap._merge_lifecycle_states([])
        assert [(e["name"], e["state"]) for e in out] == [
            ("tq-vision", "disabled"),
            ("ollama", "stopped"),
        ]
        for e in out:
            assert e["reachable"] is False
            assert e["models"] == []
            assert e["engine_id"] == e["name"]
            assert "model" in e  # None when the node reports none

    def test_mixed_join_and_append(self, monkeypatch):
        monkeypatch.setattr(
            snap,
            "_fetch_lifecycle_states",
            lambda: [
                {"name": "llamacpp-aux-1", "display": "aux1", "port": 8090, "state": "running"},
                {"name": "ollama", "display": "Ollama", "port": 11434, "state": "stopped"},
            ],
        )
        out = snap._merge_lifecycle_states([_detected("http://localhost:8090")])
        assert len(out) == 2
        assert out[0]["engine_id"] == "llamacpp-aux-1"
        assert out[1]["name"] == "ollama"

    def test_bad_port_entries_ignored(self, monkeypatch):
        monkeypatch.setattr(
            snap,
            "_fetch_lifecycle_states",
            lambda: [
                {"name": "weird", "display": "?", "port": "not-a-port", "state": "stopped"},
                {"name": "zero", "display": "?", "port": 0, "state": "stopped"},
            ],
        )
        out = snap._merge_lifecycle_states([_detected("http://localhost:8090")])
        assert len(out) == 1  # nothing joined, nothing appended


class TestFetchLifecycleStates:
    def test_no_loopback_token_returns_none(self, monkeypatch):
        from asiai.auth import loopback

        monkeypatch.setattr(loopback, "read_token", lambda: None)
        assert snap._fetch_lifecycle_states() is None

    def test_unreachable_serve_returns_none(self, monkeypatch, tmp_path):
        from asiai.auth import loopback

        monkeypatch.setattr(loopback, "read_token", lambda: "aint_test")
        # TEST-NET port that refuses immediately on loopback
        monkeypatch.setattr(snap, "AISCTL_SERVE_URL", "http://127.0.0.1:9")
        assert snap._fetch_lifecycle_states() is None


class TestSharedPortIdentity:
    """Two manifests on ONE port is a documented install pattern (a preset
    taking over a production slot, the standby keeping its port). The merge
    must never let the standby's manifest overwrite the verified identity of
    the process actually answering — the fleet used to caption the mtplx
    production slot as 'llamacpp'."""

    ENTRIES = [
        {
            "name": "llamacpp",
            "display": "llama.cpp (main)",
            "port": 8080,
            "state": "stopped",
            "model": "standby.gguf",
        },
        {
            "name": "mtplx",
            "display": "MTPLX (Hermes agent)",
            "port": 8080,
            "state": "running",
            "model": "qwen-mtplx.gguf",
        },
    ]

    def test_detected_engine_joins_its_coherent_manifest(self, monkeypatch):
        monkeypatch.setattr(snap, "_fetch_lifecycle_states", lambda: list(self.ENTRIES))
        out = snap._merge_lifecycle_states([_detected("http://localhost:8080", name="mtplx")])
        card = out[0]
        assert card["engine_id"] == "mtplx"  # identity kept, not clobbered
        assert card["state"] == "running"
        assert card.get("port_conflict") is None
        # the cold standby still shows up, with its own lifecycle state
        standby = [e for e in out[1:] if e["engine_id"] == "llamacpp"]
        assert len(standby) == 1
        assert standby[0]["state"] == "stopped"
        assert standby[0]["reachable"] is False

    def test_family_prefix_still_matches(self, monkeypatch):
        """Detection names every llama-server 'llamacpp'; the aux manifest
        must still be allowed to refine it (pre-existing behavior)."""
        monkeypatch.setattr(
            snap,
            "_fetch_lifecycle_states",
            lambda: [
                {
                    "name": "llamacpp-aux-1",
                    "display": "aux 1",
                    "port": 8090,
                    "state": "running",
                    "model": "m.gguf",
                }
            ],
        )
        out = snap._merge_lifecycle_states([_detected("http://localhost:8090", name="llamacpp")])
        assert out[0]["engine_id"] == "llamacpp-aux-1"

    def test_no_coherent_manifest_flags_conflict_and_keeps_identity(self, monkeypatch):
        monkeypatch.setattr(
            snap,
            "_fetch_lifecycle_states",
            lambda: [
                {
                    "name": "llamacpp",
                    "display": "llama.cpp (main)",
                    "port": 8080,
                    "state": "stopped",
                    "model": "standby.gguf",
                }
            ],
        )
        out = snap._merge_lifecycle_states([_detected("http://localhost:8080", name="mtplx")])
        card = out[0]
        assert card["port_conflict"] is True
        assert "engine_id" not in card  # verified identity untouched
        assert card.get("state") is None or card.get("state") != "stopped"
        # the incoherent manifest is NOT swallowed: it renders as its own entry
        assert [e["engine_id"] for e in out[1:]] == ["llamacpp"]
