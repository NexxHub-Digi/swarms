"""Server-side configuration, project authentication and fail-closed validation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass
from typing import Mapping

from .workflows import WORKFLOWS

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


class ConfigurationError(RuntimeError):
    """Invalid or missing operator-controlled settings."""


@dataclass(frozen=True)
class Project:
    identifier: str
    key_hash: bytes
    model: str
    workflows: frozenset[str]
    requests_per_minute: int


@dataclass(frozen=True)
class GatewayConfig:
    projects: tuple[Project, ...]
    max_concurrent_runs: int = 2

    def authenticate(self, token: str) -> Project | None:
        # Hash once and compare fixed-length byte digests. Secrets never enter logs.
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        match = None
        for project in self.projects:
            if secrets.compare_digest(digest, project.key_hash):
                match = project
        return match


def load_config(env: Mapping[str, str] | None = None) -> GatewayConfig:
    if env is None:
        env = os.environ
    raw = env.get("NEXX_PROJECTS_JSON", "")
    if not raw:
        raise ConfigurationError("NEXX_PROJECTS_JSON is required")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError("NEXX_PROJECTS_JSON must be valid JSON") from exc
    if not isinstance(data, dict) or not data:
        raise ConfigurationError("At least one configured project is required")

    default_model = env.get("NEXX_DEFAULT_MODEL", "").strip()
    projects: list[Project] = []
    seen_hashes: set[bytes] = set()
    for identifier, entry in data.items():
        if not isinstance(identifier, str) or not _PROJECT_ID.fullmatch(identifier):
            raise ConfigurationError("Invalid project identifier")
        if not isinstance(entry, dict):
            raise ConfigurationError("Each project configuration must be an object")
        if entry.get("enabled", True) is False:
            continue
        token = entry.get("api_key")
        if not isinstance(token, str) or len(token) < 32 or len(token) > 256:
            raise ConfigurationError(f"Project {identifier}: api_key must be 32-256 characters")
        key_hash = hashlib.sha256(token.encode("utf-8")).digest()
        if key_hash in seen_hashes:
            raise ConfigurationError("API keys must be unique to each project")
        seen_hashes.add(key_hash)

        model = entry.get("model", default_model)
        if not isinstance(model, str) or not model.strip() or len(model) > 128:
            raise ConfigurationError(f"Project {identifier}: a server-configured model is required")
        allowed = entry.get("workflows")
        if not isinstance(allowed, list) or not allowed or not all(isinstance(item, str) for item in allowed):
            raise ConfigurationError(f"Project {identifier}: nonempty workflows list required")
        if set(allowed).difference(WORKFLOWS):
            raise ConfigurationError(f"Project {identifier}: unknown workflow")
        rpm = entry.get("requests_per_minute", 10)
        if type(rpm) is not int or rpm < 1 or rpm > 10000:
            raise ConfigurationError(f"Project {identifier}: requests_per_minute must be 1-10000")
        projects.append(Project(identifier, key_hash, model.strip(), frozenset(allowed), rpm))

    if not projects:
        raise ConfigurationError("No enabled projects")
    raw_concurrency = env.get("NEXX_MAX_CONCURRENT_RUNS", "2")
    try:
        concurrency = int(raw_concurrency)
    except (ValueError, TypeError) as exc:
        raise ConfigurationError("NEXX_MAX_CONCURRENT_RUNS must be an integer") from exc
    if concurrency < 1 or concurrency > 64:
        raise ConfigurationError("NEXX_MAX_CONCURRENT_RUNS must be 1-64")
    return GatewayConfig(tuple(projects), concurrency)
