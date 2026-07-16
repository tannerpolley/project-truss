#!/usr/bin/env python3
"""Validate the repo's Codex plugin manifest and skill layout."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)

ALLOWED_MANIFEST_KEYS = {
    "id",
    "name",
    "version",
    "description",
    "skills",
    "apps",
    "mcpServers",
    "interface",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a local Codex plugin.")
    parser.add_argument("plugin_path", help="Path to the plugin root directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plugin_root = Path(args.plugin_path).resolve()
    errors = validate_plugin(plugin_root)
    if errors:
        print("Plugin validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Plugin validation passed: {plugin_root}")


def validate_plugin(plugin_root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    manifest = load_json_object(manifest_path, errors)
    if manifest is None:
        return errors

    reject_unknown_fields(manifest, ALLOWED_MANIFEST_KEYS, "plugin.json", errors)
    require_non_empty_string(manifest, "name", "plugin.json", errors)
    version = require_non_empty_string(manifest, "version", "plugin.json", errors)
    if version is not None and SEMVER_RE.fullmatch(version) is None:
        errors.append("plugin.json field `version` must be strict semver")
    require_non_empty_string(manifest, "description", "plugin.json", errors)

    author = manifest.get("author")
    if author is not None:
        if not isinstance(author, dict):
            errors.append("plugin.json field `author` must be an object")
        else:
            reject_unknown_fields(author, {"name", "email", "url"}, "author", errors)
            require_non_empty_string(author, "name", "author", errors)

    skills_value = manifest.get("skills")
    if not isinstance(skills_value, str) or not skills_value.strip():
        errors.append("plugin.json field `skills` must be a non-empty string")
    else:
        skills_path = (plugin_root / skills_value).resolve()
        if not skills_path.is_dir():
            errors.append(f"plugin skills path does not exist: {skills_value}")
        else:
            validate_skill_directories(skills_path, errors)

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("plugin.json field `interface` must be an object")
    else:
        validate_interface(interface, errors)

    return errors


def load_json_object(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append("missing `.codex-plugin/plugin.json`")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"`.codex-plugin/plugin.json` must be valid JSON: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append("`.codex-plugin/plugin.json` must contain a JSON object")
        return None
    return payload


def reject_unknown_fields(payload: dict[str, Any], allowed: set[str], label: str, errors: list[str]) -> None:
    for key in sorted(set(payload) - allowed):
        errors.append(f"{label} field `{key}` is not accepted")


def require_non_empty_string(
    payload: dict[str, Any],
    key: str,
    label: str,
    errors: list[str],
) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} field `{key}` must be a non-empty string")
        return None
    return value.strip()


def validate_interface(interface: dict[str, Any], errors: list[str]) -> None:
    allowed = {
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "websiteURL",
        "privacyPolicyURL",
        "termsOfServiceURL",
        "brandColor",
        "composerIcon",
        "logo",
        "screenshots",
        "defaultPrompt",
        "default_prompt",
    }
    reject_unknown_fields(interface, allowed, "interface", errors)
    for key in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
        require_non_empty_string(interface, key, "interface", errors)
    if "defaultPrompt" not in interface and "default_prompt" not in interface:
        errors.append("interface field `defaultPrompt` or `default_prompt` is required")
    capabilities = interface.get("capabilities")
    if not isinstance(capabilities, list) or not all(isinstance(item, str) and item.strip() for item in capabilities):
        errors.append("interface field `capabilities` must be an array of non-empty strings")


def validate_skill_directories(skills_path: Path, errors: list[str]) -> None:
    skill_dirs = [path for path in skills_path.iterdir() if path.is_dir()]
    if not skill_dirs:
        errors.append("plugin skills path must contain at least one skill directory")
        return
    for skill_dir in sorted(skill_dirs):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"missing skill SKILL.md: {skill_dir.name}")


if __name__ == "__main__":
    main()
