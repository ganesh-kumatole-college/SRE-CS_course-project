import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

from misdet.collect.normalize import (
    NormalizationError,
    main,
    normalize_file,
    normalize_snapshot,
)


def policy(
    arn="arn:aws:iam::aws:policy/Example",
    document=None,
    version_id="v1",
    versions=None,
):
    if document is None:
        document = {
            "Version": "2012-10-17",
            "Statement": {
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": "*",
            },
        }
    if versions is None:
        versions = [
            {
                "VersionId": version_id,
                "IsDefaultVersion": True,
                "Document": document,
            }
        ]
    return {
        "PolicyArn": arn,
        "DefaultVersionId": version_id,
        "PolicyVersionList": versions,
    }


class NormalizeSnapshotTests(unittest.TestCase):
    def test_normalizes_string_statement_values_and_preserves_wildcards(self):
        record = normalize_snapshot({"Policies": [policy()]})[0]
        statement = record["document"]["Statement"][0]
        self.assertEqual(statement["Action"], ["s3:getobject"])
        self.assertEqual(statement["Resource"], ["*"])
        self.assertEqual(record["org"], None)
        self.assertEqual(record["source"], "aws_managed")

    def test_accepts_statement_and_selector_lists(self):
        source = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["S3:GetObject", "s3:*"],
                    "Resource": ["arn:aws:s3:::example/*"],
                },
                {
                    "Effect": "Deny",
                    "NotAction": ["IAM:CreateUser"],
                    "NotResource": ["arn:aws:iam::*:user/*"],
                },
            ],
        }
        statements = normalize_snapshot({"Policies": [policy(document=source)]})[0]["document"][
            "Statement"
        ]
        self.assertEqual(statements[0]["Action"], ["s3:getobject", "s3:*"])
        self.assertEqual(statements[1]["NotAction"], ["iam:createuser"])
        self.assertEqual(statements[1]["NotResource"], ["arn:aws:iam::*:user/*"])

    def test_decodes_url_encoded_document_and_selects_default_version(self):
        alternate = {
            "VersionId": "v0",
            "IsDefaultVersion": False,
            "Document": {"Statement": []},
        }
        current_doc = {
            "Version": "2012-10-17",
            "Statement": {
                "Effect": "Deny",
                "Action": "S3:DeleteObject",
                "Resource": "*",
            },
        }
        current = {
            "VersionId": "v1",
            "IsDefaultVersion": True,
            "Document": quote(json.dumps(current_doc)),
        }
        result = normalize_snapshot({"Policies": [policy(versions=[alternate, current])]})[0]
        self.assertEqual(result["document"]["Statement"][0]["Effect"], "Deny")
        self.assertEqual(result["document"]["Statement"][0]["Action"], ["s3:deleteobject"])

    def test_preserves_conditions_and_principals_with_arn_redaction(self):
        document = {
            "Statement": {
                "Effect": "Allow",
                "Action": "S3:GetObject",
                "Resource": "arn:aws:s3:::bucket/*",
                "Principal": {"AWS": "arn:aws:iam::123456789012:root"},
                "Condition": {
                    "StringEquals": {
                        "aws:PrincipalAccount": "123456789012",
                        "example:Path": "folder:123456789012:private/*",
                    }
                },
            }
        }
        record = normalize_snapshot(
            {
                "Policies": [
                    policy(
                        arn="arn:aws:iam::123456789012:policy/Example",
                        document=document,
                    )
                ]
            }
        )[0]
        statement = record["document"]["Statement"][0]
        self.assertEqual(record["policy_id"], "arn:aws:iam::REDACTED:policy/Example")
        self.assertEqual(statement["Principal"]["AWS"], "arn:aws:iam::REDACTED:root")
        self.assertEqual(
            statement["Condition"]["StringEquals"]["aws:PrincipalAccount"],
            "123456789012",
        )
        self.assertEqual(
            statement["Condition"]["StringEquals"]["example:Path"],
            "folder:123456789012:private/*",
        )

    def test_plain_json_document_keeps_percent_sequences(self):
        document = {
            "Statement": {
                "Effect": "Allow",
                "Action": "S3:GetObject",
                "Resource": "arn:aws:s3:::bucket/a%2Fb",
            }
        }
        record = normalize_snapshot({"Policies": [policy(document=document)]})[0]
        self.assertEqual(
            record["document"]["Statement"][0]["Resource"],
            ["arn:aws:s3:::bucket/a%2Fb"],
        )

    def test_raw_hash_uses_redacted_source_before_action_normalization(self):
        source_statement = {
            "Effect": "Allow",
            "Action": "S3:GetObject",
            "Resource": "arn:aws:s3:::bucket/*",
            "Principal": {"AWS": "arn:aws:iam::123456789012:root"},
        }
        record = normalize_snapshot(
            {"Policies": [policy(document={"Statement": source_statement})]}
        )[0]
        redacted_source = {
            **source_statement,
            "Principal": {"AWS": "arn:aws:iam::REDACTED:root"},
        }
        encoded = json.dumps(
            redacted_source,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(
            record["document"]["Statement"][0]["raw_hash"],
            hashlib.sha256(encoded).hexdigest(),
        )

    def test_sorts_policies_and_rejects_duplicate_ids(self):
        result = normalize_snapshot(
            {
                "Policies": [
                    policy(arn="arn:aws:iam::aws:policy/Z"),
                    policy(arn="arn:aws:iam::aws:policy/A"),
                ]
            }
        )
        self.assertEqual(
            [item["policy_id"] for item in result],
            ["arn:aws:iam::aws:policy/A", "arn:aws:iam::aws:policy/Z"],
        )
        with self.assertRaisesRegex(NormalizationError, "duplicate policy IDs"):
            normalize_snapshot(
                {
                    "Policies": [
                        policy(arn="arn:aws:iam::123456789012:policy/Example"),
                        policy(arn="arn:aws:iam::REDACTED:policy/Example"),
                    ]
                }
            )

    def test_rejects_empty_snapshots_and_statements(self):
        with self.assertRaisesRegex(NormalizationError, "non-empty Policies"):
            normalize_snapshot({"Policies": []})
        with self.assertRaisesRegex(NormalizationError, "non-empty object or list"):
            normalize_snapshot({"Policies": [policy(document={"Statement": []})]})

    def test_rejects_missing_or_ambiguous_default_versions(self):
        with self.assertRaisesRegex(NormalizationError, "no DefaultVersionId"):
            normalize_snapshot({"Policies": [{**policy(), "DefaultVersionId": None}]})
        ambiguous_versions = [
            {
                "VersionId": "v1",
                "IsDefaultVersion": True,
                "Document": {"Statement": []},
            },
            {
                "VersionId": "v2",
                "IsDefaultVersion": True,
                "Document": {"Statement": []},
            },
        ]
        with self.assertRaisesRegex(NormalizationError, "unambiguous default"):
            normalize_snapshot({"Policies": [policy(versions=ambiguous_versions)]})

    def test_rejects_invalid_effect_and_selector_pairs(self):
        invalid_documents = (
            {"Effect": "Allow", "Action": "*", "NotAction": "s3:*", "Resource": "*"},
            {"Effect": "Allow", "Action": [], "Resource": "*"},
            {"Effect": "Pass", "Action": "*", "Resource": "*"},
            {"Effect": "Allow", "Action": "*"},
        )
        for statement in invalid_documents:
            with self.subTest(statement=statement):
                with self.assertRaises(NormalizationError):
                    normalize_snapshot({"Policies": [policy(document={"Statement": statement})]})


class NormalizeFileTests(unittest.TestCase):
    def test_writes_deterministic_records_manifest_and_statistics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "snapshot.json"
            output_path = root / "output" / "policies.jsonl"
            input_bytes = json.dumps({"Policies": [policy()]}, separators=(",", ":")).encode()
            input_path.write_bytes(input_bytes)

            args = (
                input_path,
                output_path,
                "https://example.invalid/policies",
                "abc123",
                "2026-01-02",
                "Example-License",
            )
            normalize_file(*args)
            first_outputs = [
                path.read_bytes()
                for path in (
                    output_path,
                    output_path.with_name("source_manifest.json"),
                    output_path.with_name("policy_stats.json"),
                )
            ]
            normalize_file(*args)
            self.assertEqual(
                first_outputs,
                [
                    path.read_bytes()
                    for path in (
                        output_path,
                        output_path.with_name("source_manifest.json"),
                        output_path.with_name("policy_stats.json"),
                    )
                ],
            )

            manifest = json.loads(first_outputs[1])
            self.assertEqual(manifest["input_sha256"], hashlib.sha256(input_bytes).hexdigest())
            self.assertEqual(
                manifest["policies_sha256"],
                hashlib.sha256(first_outputs[0]).hexdigest(),
            )
            self.assertEqual(manifest["policy_count"], 1)
            stats = json.loads(first_outputs[2])
            self.assertEqual(stats["action_pattern_count"], 1)
            self.assertEqual(stats["wildcard_action_pattern_count"], 0)
            self.assertEqual(stats["services"], {"s3": 1})

    def test_statistics_include_negations_and_wildcard_share(self):
        first_document = {
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["S3:GetObject", "s3:*"],
                    "Resource": "*",
                },
                {
                    "Effect": "Deny",
                    "NotAction": "iam:*",
                    "Resource": "*",
                },
            ]
        }
        second_document = {
            "Statement": {
                "Effect": "Allow",
                "Action": "ec2:Describe*",
                "Resource": "*",
            }
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "snapshot.json"
            input_path.write_text(
                json.dumps(
                    {
                        "Policies": [
                            policy(arn="arn:aws:iam::aws:policy/A", document=first_document),
                            policy(arn="arn:aws:iam::aws:policy/B", document=second_document),
                        ]
                    }
                ),
                encoding="utf-8",
            )
            output_path = root / "policies.jsonl"
            normalize_file(
                input_path,
                output_path,
                "https://example.invalid/policies",
                "abc123",
                "2026-01-02",
                "Example-License",
            )

            stats = json.loads((root / "policy_stats.json").read_text(encoding="utf-8"))
            self.assertEqual(stats["action_pattern_count"], 4)
            self.assertEqual(stats["wildcard_action_pattern_count"], 3)
            self.assertEqual(stats["wildcard_action_pattern_share"], 0.75)
            self.assertEqual(
                stats["action_patterns_per_policy"],
                {
                    "min": 1,
                    "median": 2.0,
                    "mean": 2,
                    "max": 3,
                },
            )
            self.assertEqual(stats["services"], {"ec2": 1, "iam": 1, "s3": 2})

    def test_validation_failure_leaves_existing_outputs_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "snapshot.json"
            output_path = root / "policies.jsonl"
            input_path.write_text('{"Policies":[]}', encoding="utf-8")
            sibling_paths = (
                output_path,
                root / "source_manifest.json",
                root / "policy_stats.json",
            )
            for path in sibling_paths:
                path.write_bytes(b"existing")

            with self.assertRaises(NormalizationError):
                normalize_file(
                    input_path,
                    output_path,
                    "https://example.invalid/policies",
                    "abc123",
                    "2026-01-02",
                    "Example-License",
                )
            self.assertEqual([path.read_bytes() for path in sibling_paths], [b"existing"] * 3)

    def test_rejects_output_overwriting_input(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "snapshot.json"
            input_path.write_text(json.dumps({"Policies": [policy()]}), encoding="utf-8")
            with self.assertRaisesRegex(NormalizationError, "must not overwrite"):
                normalize_file(
                    input_path,
                    input_path,
                    "https://example.invalid/policies",
                    "abc123",
                    "2026-01-02",
                    "Example-License",
                )

    def test_refuses_output_hard_link_to_input_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "snapshot.json"
            input_path.write_text(json.dumps({"Policies": [policy()]}), encoding="utf-8")
            output_path = root / "policies.jsonl"
            output_path.hardlink_to(input_path)
            input_bytes = input_path.read_bytes()

            with self.assertRaisesRegex(NormalizationError, "must not share an inode"):
                normalize_file(
                    input_path,
                    output_path,
                    "https://example.invalid/policies",
                    "abc123",
                    "2026-01-02",
                    "Example-License",
                )

            self.assertEqual(input_path.read_bytes(), input_bytes)
            self.assertEqual(output_path.read_bytes(), input_bytes)
            self.assertFalse((root / "source_manifest.json").exists())
            self.assertFalse((root / "policy_stats.json").exists())

    def test_refuses_hard_linked_generated_output_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "snapshot.json"
            input_path.write_text(json.dumps({"Policies": [policy()]}), encoding="utf-8")
            output_path = root / "policies.jsonl"
            manifest_path = root / "source_manifest.json"
            output_path.write_bytes(b"existing output")
            manifest_path.hardlink_to(output_path)

            with self.assertRaisesRegex(NormalizationError, "must not share an inode"):
                normalize_file(
                    input_path,
                    output_path,
                    "https://example.invalid/policies",
                    "abc123",
                    "2026-01-02",
                    "Example-License",
                )

            self.assertEqual(output_path.read_bytes(), b"existing output")
            self.assertEqual(manifest_path.read_bytes(), b"existing output")
            self.assertFalse((root / "policy_stats.json").exists())

    def test_refuses_symlink_for_each_generated_output(self):
        output_names = ("policies.jsonl", "source_manifest.json", "policy_stats.json")
        for symlink_name in output_names:
            with (
                self.subTest(output=symlink_name),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                root = Path(temporary_directory)
                output_directory = root / "output"
                output_directory.mkdir()
                input_path = root / "snapshot.json"
                input_path.write_text(json.dumps({"Policies": [policy()]}), encoding="utf-8")
                target = root / "unrelated.txt"
                target.write_bytes(b"must remain unchanged")
                (output_directory / symlink_name).symlink_to(target)

                with self.assertRaisesRegex(NormalizationError, "symlink output path"):
                    normalize_file(
                        input_path,
                        output_directory / "policies.jsonl",
                        "https://example.invalid/policies",
                        "abc123",
                        "2026-01-02",
                        "Example-License",
                    )

                self.assertEqual(target.read_bytes(), b"must remain unchanged")
                self.assertTrue((output_directory / symlink_name).is_symlink())
                self.assertEqual(
                    sorted(path.name for path in output_directory.iterdir()),
                    [symlink_name],
                )

    def test_refuses_symlinked_output_directory_without_writing_through_it(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            real_directory = root / "real"
            real_directory.mkdir()
            target = real_directory / "preserve.txt"
            target.write_bytes(b"must remain unchanged")
            alias_directory = root / "alias"
            alias_directory.symlink_to(real_directory, target_is_directory=True)
            input_path = root / "snapshot.json"
            input_path.write_text(json.dumps({"Policies": [policy()]}), encoding="utf-8")

            with self.assertRaisesRegex(
                NormalizationError, "output directory components must be real"
            ):
                normalize_file(
                    input_path,
                    alias_directory / "nested" / "policies.jsonl",
                    "https://example.invalid/policies",
                    "abc123",
                    "2026-01-02",
                    "Example-License",
                )

            self.assertEqual(target.read_bytes(), b"must remain unchanged")
            self.assertEqual(
                sorted(path.name for path in real_directory.iterdir()),
                ["preserve.txt"],
            )

    def test_rejects_overflowing_numbers_in_embedded_policy_documents(self):
        document = (
            '{"Statement":{"Effect":"Allow","Action":"s3:GetObject",'
            '"Resource":"*","Extra":1e9999}}'
        )
        with self.assertRaisesRegex(NormalizationError, "Document is not valid JSON"):
            normalize_snapshot({"Policies": [policy(document=document)]})

    def test_cli_reports_input_errors_with_nonzero_status(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "snapshot.json"
            input_path.write_text("not JSON", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = main(
                    [
                        "--in",
                        str(input_path),
                        "--out",
                        str(root / "policies.jsonl"),
                        "--source-url",
                        "https://example.invalid/policies",
                        "--revision",
                        "abc123",
                        "--snapshot-date",
                        "2026-01-02",
                        "--license",
                        "Example-License",
                    ]
                )
            self.assertEqual(status, 2)
            self.assertIn("input file is not valid UTF-8 JSON", stderr.getvalue())

    def test_cli_rejects_overflowing_numbers_without_changing_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "snapshot.json"
            input_path.write_text(
                '{"Policies":[{"PolicyArn":"arn:aws:iam::aws:policy/Example",'
                '"DefaultVersionId":"v1","PolicyVersionList":[{"VersionId":"v1",'
                '"IsDefaultVersion":true,"Document":{"Statement":{"Effect":"Allow",'
                '"Action":"s3:GetObject","Resource":"*","Extra":1e9999}}}]}]}',
                encoding="utf-8",
            )
            output_paths = (
                root / "policies.jsonl",
                root / "source_manifest.json",
                root / "policy_stats.json",
            )
            for path in output_paths:
                path.write_bytes(b"existing output")

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = main(
                    [
                        "--in",
                        str(input_path),
                        "--out",
                        str(output_paths[0]),
                        "--source-url",
                        "https://example.invalid/policies",
                        "--revision",
                        "abc123",
                        "--snapshot-date",
                        "2026-01-02",
                        "--license",
                        "Example-License",
                    ]
                )

            self.assertEqual(status, 2)
            self.assertIn("input file is not valid UTF-8 JSON", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())
            self.assertEqual(
                [path.read_bytes() for path in output_paths],
                [b"existing output"] * 3,
            )


if __name__ == "__main__":
    unittest.main()
