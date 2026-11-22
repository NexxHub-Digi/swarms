import json

import pytest

from nexx_gateway.config import ConfigurationError, load_config


def env(projects, **kwargs):
    return {"NEXX_PROJECTS_JSON": json.dumps(projects), "NEXX_DEFAULT_MODEL": "test/model", **kwargs}


def test_project_authentication_is_scoped():
    cfg = load_config(env({
        "nexx-ai": {"api_key": "a" * 48, "workflows": ["research"]},
        "nexx-hotel": {"api_key": "b" * 48, "workflows": ["operations"]},
    }))
    assert cfg.authenticate("a" * 48).identifier == "nexx-ai"
    assert cfg.authenticate("b" * 48).identifier == "nexx-hotel"
    assert cfg.authenticate("wrong") is None


@pytest.mark.parametrize("projects", [
    {},
    {"test": {"api_key": "too-short", "workflows": ["research"]}},
    {"test": {"api_key": "x" * 48, "workflows": ["not-real"]}},
    {"test": {"api_key": "x" * 48, "workflows": []}},
    {"test": {"api_key": "x" * 48, "workflows": ["research"], "requests_per_minute": 0}},
    {"nexx-ai": {"api_key": "x" * 48, "workflows": ["research"]}, "nexx-hotel": {"api_key": "x" * 48, "workflows": ["support"]}},
])
def test_invalid_config_fails_closed(projects):
    with pytest.raises(ConfigurationError):
        load_config(env(projects))


def test_disabled_projects_are_not_authorized():
    cfg = load_config(env({
        "nexx-ai": {"api_key": "a" * 48, "workflows": ["research"]},
        "nexx-eventpass": {"enabled": False},
    }))
    assert cfg.authenticate("b" * 48) is None
    assert len(cfg.projects) == 1
