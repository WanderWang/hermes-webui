"""Regression coverage for #2305 — new profiles created without clone get bundled skills."""

import pathlib
import sys

import pytest

import api.profiles as profiles


REPO = pathlib.Path(__file__).resolve().parent.parent


class TestProfileCreateSkillSeeding:
    """Verify that create_profile_api seeds bundled skills for fresh profiles."""

    def test_create_profile_api_seeds_skills_when_clone_from_none(self, monkeypatch, tmp_path):
        """Fresh profile (clone_from=None) should call seed_profile_skills."""
        base = tmp_path / ".hermes"
        monkeypatch.setenv("HERMES_BASE_HOME", str(base))
        monkeypatch.delenv("HERMES_HOME", raising=False)

        seed_calls = []

        def fake_seed(profile_dir, quiet=False):
            seed_calls.append((str(profile_dir), quiet))
            # Create a dummy skill file so the profile looks seeded
            skills_dir = pathlib.Path(profile_dir) / "skills"
            skills_dir.mkdir(parents=True, exist_ok=True)
            (skills_dir / "test-skill-2305").mkdir(parents=True, exist_ok=True)
            (skills_dir / "test-skill-2305" / "SKILL.md").write_text(
                "---\nname: test-skill-2305\n---\n", encoding="utf-8"
            )

        # Inject mock hermes_cli.profiles into sys.modules BEFORE any import resolves it.
        # create_profile_api's `from hermes_cli.profiles import seed_profile_skills` is
        # evaluated at call time, so the mock is picked up without reloading api.profiles.
        fake_module = type(sys)("hermes_cli.profiles")
        fake_module.seed_profile_skills = fake_seed
        fake_module.create_profile = lambda *args, **kwargs: None
        monkeypatch.setitem(sys.modules, "hermes_cli.profiles", fake_module)

        if "hermes_cli" not in sys.modules:
            monkeypatch.setitem(sys.modules, "hermes_cli", type(sys)("hermes_cli"))

        result = profiles.create_profile_api("test-seed-2305", clone_from=None)

        assert len(seed_calls) == 1, f"Expected 1 seed call, got {len(seed_calls)}"
        assert "test-seed-2305" in seed_calls[0][0]
        assert seed_calls[0][1] is True  # quiet=True

    def test_create_profile_api_skips_seed_when_clone_from_set(self, monkeypatch, tmp_path):
        """Cloned profile should NOT call seed_profile_skills (skills copied from source)."""
        base = tmp_path / ".hermes"
        (base / "profiles" / "source" / "skills" / "existing-skill").mkdir(parents=True)
        (base / "profiles" / "source" / "skills" / "existing-skill" / "SKILL.md").write_text(
            "---\nname: existing-skill\n---\n", encoding="utf-8"
        )
        monkeypatch.setenv("HERMES_BASE_HOME", str(base))
        monkeypatch.delenv("HERMES_HOME", raising=False)

        seed_calls = []

        def fake_seed(profile_dir, quiet=False):
            seed_calls.append((str(profile_dir), quiet))

        fake_module = type(sys)("hermes_cli.profiles")
        fake_module.seed_profile_skills = fake_seed
        fake_module.create_profile = lambda *args, **kwargs: None
        monkeypatch.setitem(sys.modules, "hermes_cli.profiles", fake_module)

        if "hermes_cli" not in sys.modules:
            monkeypatch.setitem(sys.modules, "hermes_cli", type(sys)("hermes_cli"))

        result = profiles.create_profile_api("test-clone-2305", clone_from="source", clone_config=True)

        assert len(seed_calls) == 0, f"Expected 0 seed calls for cloned profile, got {len(seed_calls)}"

    def test_seed_failure_is_non_fatal(self, monkeypatch, tmp_path):
        """If seed_profile_skills raises, profile creation should still succeed."""
        base = tmp_path / ".hermes"
        monkeypatch.setenv("HERMES_BASE_HOME", str(base))
        monkeypatch.delenv("HERMES_HOME", raising=False)

        def failing_seed(profile_dir, quiet=False):
            raise RuntimeError("Simulated seed failure")

        fake_module = type(sys)("hermes_cli.profiles")
        fake_module.seed_profile_skills = failing_seed
        fake_module.create_profile = lambda *args, **kwargs: None
        monkeypatch.setitem(sys.modules, "hermes_cli.profiles", fake_module)

        if "hermes_cli" not in sys.modules:
            monkeypatch.setitem(sys.modules, "hermes_cli", type(sys)("hermes_cli"))

        # Should not raise
        result = profiles.create_profile_api("test-fail-2305", clone_from=None)

        assert result["name"] == "test-fail-2305"
        assert result["skill_count"] == 0  # Empty because seed failed
