"""Normalize local AWS-managed IAM policy snapshots."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import math
import os
import re
import stat
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote

SHA256_HEX_LENGTH = 64


class NormalizationError(ValueError):
    """Raised when an input snapshot cannot be normalized without data loss."""


def _json_bytes(value: Any, *, pretty: bool = False) -> bytes:
    options: dict[str, Any] = {
        "ensure_ascii": False,
        "allow_nan": False,
        "sort_keys": True,
    }
    if pretty:
        text = json.dumps(value, indent=2, **options) + "\n"
    else:
        text = json.dumps(value, separators=(",", ":"), **options)
    return text.encode("utf-8")


def _reject_json_constant(value: str) -> None:
    raise NormalizationError(f"non-standard JSON number {value!r} is not permitted")


def _parse_json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise NormalizationError("JSON number is outside the supported finite range")
    return number


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        parts = value.split(":", 5)
        if len(parts) == 6 and parts[0] == "arn" and re.fullmatch(r"\d{12}", parts[4]):
            parts[4] = "REDACTED"
            return ":".join(parts)
        return value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    return value


def _as_string_list(value: Any, field: str) -> list[str]:
    values = [value] if isinstance(value, str) else value
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(item, str) or not item for item in values)
    ):
        raise NormalizationError(f"{field} must be a non-empty string or list of non-empty strings")
    return values


def _normalize_statement(source: Any, policy_id: str, index: int) -> dict[str, Any]:
    location = f"policy {policy_id!r}, statement {index}"
    if not isinstance(source, dict):
        raise NormalizationError(f"{location} must be a JSON object")

    statement = _redact(source)
    raw_hash = hashlib.sha256(_json_bytes(statement)).hexdigest()
    effect = statement.get("Effect")
    if effect not in ("Allow", "Deny"):
        raise NormalizationError(f"{location} must have Effect 'Allow' or 'Deny'")

    for positive, negative in (("Action", "NotAction"), ("Resource", "NotResource")):
        present = [field for field in (positive, negative) if field in statement]
        if len(present) != 1:
            raise NormalizationError(
                f"{location} must contain exactly one of {positive} or {negative}"
            )
        field = present[0]
        values = _as_string_list(statement[field], f"{location} {field}")
        if field in ("Action", "NotAction"):
            values = [item.lower() for item in values]
        statement[field] = values

    statement["raw_hash"] = raw_hash
    return statement


def _default_policy_document(policy: Any, policy_id: str) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise NormalizationError(f"policy {policy_id!r} must be a JSON object")

    default_id = policy.get("DefaultVersionId")
    if not isinstance(default_id, str) or not default_id:
        raise NormalizationError(f"policy {policy_id!r} has no DefaultVersionId")

    versions = policy.get("PolicyVersionList")
    if not isinstance(versions, list) or not versions:
        raise NormalizationError(f"policy {policy_id!r} has no PolicyVersionList")
    default_markers = [
        version
        for version in versions
        if isinstance(version, dict) and version.get("IsDefaultVersion") is True
    ]
    matching_versions = [
        version
        for version in versions
        if isinstance(version, dict) and version.get("VersionId") == default_id
    ]
    if len(default_markers) != 1 or len(matching_versions) != 1:
        raise NormalizationError(
            f"policy {policy_id!r} must have exactly one unambiguous default version"
        )
    default_version = default_markers[0]
    if default_version.get("VersionId") != default_id:
        raise NormalizationError(
            f"policy {policy_id!r} DefaultVersionId does not match its default marker"
        )

    document = default_version.get("Document")
    if isinstance(document, str):
        try:
            document = json.loads(
                document,
                parse_constant=_reject_json_constant,
                parse_float=_parse_json_float,
            )
        except ValueError:
            try:
                document = json.loads(
                    unquote(document),
                    parse_constant=_reject_json_constant,
                    parse_float=_parse_json_float,
                )
            except ValueError as error:
                raise NormalizationError(
                    f"policy {policy_id!r} default-version Document is not valid JSON"
                ) from error
    if not isinstance(document, dict):
        raise NormalizationError(
            f"policy {policy_id!r} default-version Document must be a JSON object"
        )

    redacted_document = _redact(document)
    source_statements = redacted_document.get("Statement")
    if isinstance(source_statements, dict):
        source_statements = [source_statements]
    if not isinstance(source_statements, list) or not source_statements:
        raise NormalizationError(
            f"policy {policy_id!r} document Statement must be a non-empty object or list"
        )
    redacted_document["Statement"] = [
        _normalize_statement(statement, policy_id, index)
        for index, statement in enumerate(source_statements)
    ]
    return redacted_document


def _normalize_policy(policy: Any) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise NormalizationError("each entry in Policies must be a JSON object")
    arn = policy.get("PolicyArn")
    if not isinstance(arn, str) or not arn:
        raise NormalizationError("each policy must have a non-empty PolicyArn")
    policy_id = _redact(arn)
    return {
        "policy_id": policy_id,
        "org": None,
        "source": "aws_managed",
        "document": _default_policy_document(policy, policy_id),
    }


def normalize_snapshot(snapshot: Any) -> list[dict[str, Any]]:
    """Normalize Policies from an authorization-details-shaped JSON object."""
    if not isinstance(snapshot, dict):
        raise NormalizationError("snapshot root must be a JSON object")
    policies = snapshot.get("Policies")
    if not isinstance(policies, list) or not policies:
        raise NormalizationError("snapshot must contain a non-empty Policies list")

    records = [_normalize_policy(policy) for policy in policies]
    records.sort(key=lambda record: record["policy_id"])
    ids = [record["policy_id"] for record in records]
    if len(ids) != len(set(ids)):
        raise NormalizationError("snapshot contains duplicate policy IDs after ARN redaction")
    return records


def _validate_metadata(
    source_url: str, revision: str, snapshot_date: str, license_name: str
) -> None:
    for name, value in (
        ("source URL", source_url),
        ("revision", revision),
        ("license", license_name),
    ):
        if not value.strip():
            raise NormalizationError(f"{name} must not be empty")
    try:
        parsed_date = date.fromisoformat(snapshot_date)
    except ValueError as error:
        raise NormalizationError("snapshot date must use ISO YYYY-MM-DD format") from error
    if parsed_date.isoformat() != snapshot_date:
        raise NormalizationError("snapshot date must use ISO YYYY-MM-DD format")


def _statistics(records: list[dict[str, Any]]) -> dict[str, Any]:
    policy_action_counts: list[int] = []
    statement_count = 0
    action_pattern_count = 0
    wildcard_count = 0
    services: dict[str, int] = {}

    for record in records:
        policy_patterns = 0
        statements = record["document"]["Statement"]
        statement_count += len(statements)
        for statement in statements:
            for field in ("Action", "NotAction"):
                for pattern in statement.get(field, []):
                    policy_patterns += 1
                    action_pattern_count += 1
                    if "*" in pattern:
                        wildcard_count += 1
                    if ":" in pattern:
                        service = pattern.split(":", 1)[0]
                        if service:
                            services[service] = services.get(service, 0) + 1
        policy_action_counts.append(policy_patterns)

    return {
        "policy_count": len(records),
        "statement_count": statement_count,
        "action_pattern_count": action_pattern_count,
        "wildcard_action_pattern_count": wildcard_count,
        "wildcard_action_pattern_share": wildcard_count / action_pattern_count,
        "action_patterns_per_policy": {
            "min": min(policy_action_counts),
            "median": statistics.median(policy_action_counts),
            "mean": statistics.mean(policy_action_counts),
            "max": max(policy_action_counts),
        },
        "services": dict(sorted(services.items())),
    }


def _manifest(
    source_url: str,
    revision: str,
    snapshot_date: str,
    license_name: str,
    input_bytes: bytes,
    policy_bytes: bytes,
    policy_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source_url": source_url,
        "source_revision": revision,
        "snapshot_date": snapshot_date,
        "license": license_name,
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "policies_sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "policy_count": policy_count,
    }


def _open_output_directory(path: Path) -> int:
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(path.anchor, directory_flags)
    try:
        for component in path.parts[1:]:
            try:
                child = os.open(component, directory_flags, dir_fd=descriptor)
            except FileNotFoundError:
                try:
                    os.mkdir(component, dir_fd=descriptor)
                except FileExistsError:
                    pass
                try:
                    child = os.open(component, directory_flags, dir_fd=descriptor)
                except OSError as error:
                    if error.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise NormalizationError(
                            "output directory components must be real directories, "
                            f"not symlinks: {component}"
                        ) from error
                    raise
            except OSError as error:
                if error.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise NormalizationError(
                        "output directory components must be real directories, "
                        f"not symlinks: {component}"
                    ) from error
                raise
            os.close(descriptor)
            descriptor = child
        result = descriptor
        descriptor = -1
        return result
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _write_output(
    name: str,
    content: bytes,
    directory_fd: int,
    expected_identity: tuple[int, int] | None,
) -> None:
    flags = os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    if expected_identity is None:
        flags |= os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(name, flags, 0o666, dir_fd=directory_fd)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise NormalizationError(f"refusing symlink output path: {name}") from error
        if error.errno in (errno.ENOENT, errno.EEXIST):
            raise NormalizationError(f"output path changed during validation: {name}") from error
        raise
    try:
        output_stat = os.fstat(descriptor)
        if not stat.S_ISREG(output_stat.st_mode):
            raise NormalizationError(f"output path must be a regular file: {name}")
        if (
            expected_identity is not None
            and (output_stat.st_dev, output_stat.st_ino) != expected_identity
        ):
            raise NormalizationError(f"output path changed during validation: {name}")
        os.ftruncate(descriptor, 0)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(content)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def normalize_file(
    input_path: Path,
    output_path: Path,
    source_url: str,
    revision: str,
    snapshot_date: str,
    license_name: str,
) -> None:
    """Validate a local snapshot and write deterministic outputs beside output_path."""
    _validate_metadata(source_url, revision, snapshot_date, license_name)
    input_bytes = input_path.read_bytes()
    try:
        snapshot = json.loads(
            input_bytes.decode("utf-8"),
            parse_constant=_reject_json_constant,
            parse_float=_parse_json_float,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise NormalizationError(f"input file is not valid UTF-8 JSON: {error}") from error

    records = normalize_snapshot(snapshot)
    policy_bytes = b"".join(_json_bytes(record) + b"\n" for record in records)
    stats_bytes = _json_bytes(_statistics(records), pretty=True)
    manifest_bytes = _json_bytes(
        _manifest(
            source_url,
            revision,
            snapshot_date,
            license_name,
            input_bytes,
            policy_bytes,
            len(records),
        ),
        pretty=True,
    )

    output_path = Path(os.path.abspath(output_path))
    stats_path = output_path.with_name("policy_stats.json")
    manifest_path = output_path.with_name("source_manifest.json")
    destinations = (output_path, stats_path, manifest_path)
    resolved_destinations = [path.resolve() for path in destinations]
    if len(set(resolved_destinations)) != len(destinations):
        raise NormalizationError("output path conflicts with a generated sibling output")
    if input_path.resolve() in resolved_destinations:
        raise NormalizationError("output paths must not overwrite the input snapshot")

    input_stat = input_path.stat()
    protected_inodes = {(input_stat.st_dev, input_stat.st_ino)}
    output_identities: dict[str, tuple[int, int] | None] = {}
    output_directory_fd = _open_output_directory(output_path.parent)
    try:
        for path in destinations:
            try:
                output_stat = os.stat(
                    path.name,
                    dir_fd=output_directory_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                output_identities[path.name] = None
                continue
            if stat.S_ISLNK(output_stat.st_mode):
                raise NormalizationError(f"refusing symlink output path: {path}")
            if not stat.S_ISREG(output_stat.st_mode):
                raise NormalizationError(f"output path must be a regular file: {path}")
            identity = (output_stat.st_dev, output_stat.st_ino)
            if identity in protected_inodes:
                raise NormalizationError(
                    f"output paths must not share an inode with input or another output: {path}"
                )
            protected_inodes.add(identity)
            output_identities[path.name] = identity

        for path, content in (
            (output_path, policy_bytes),
            (manifest_path, manifest_bytes),
            (stats_path, stats_bytes),
        ):
            _write_output(
                path.name,
                content,
                output_directory_fd,
                output_identities[path.name],
            )
    finally:
        os.close(output_directory_fd)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="input_path", type=Path, required=True)
    parser.add_argument("--out", dest="output_path", type=Path, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--license", dest="license_name", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    try:
        normalize_file(
            args.input_path,
            args.output_path,
            args.source_url,
            args.revision,
            args.snapshot_date,
            args.license_name,
        )
    except (NormalizationError, OSError) as error:
        print(f"normalize: error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
