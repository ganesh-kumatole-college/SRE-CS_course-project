"""Tests for research paper assets, citations, and structural consistency."""

from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_bibtex_keys_unique() -> None:
    bib_path = _repo_root() / "paper" / "references.bib"
    assert bib_path.exists(), "paper/references.bib must exist"

    text = bib_path.read_text(encoding="utf-8")
    keys = re.findall(r"@\w+\s*{\s*([^,\s]+)\s*,", text)
    assert len(keys) >= 10, f"Expected at least 10 BibTeX entries, got {len(keys)}"
    assert len(keys) == len(set(keys)), f"Duplicate BibTeX keys found: {keys}"


def test_latex_citations_valid() -> None:
    root = _repo_root()
    bib_path = root / "paper" / "references.bib"
    assert bib_path.exists()
    bib_text = bib_path.read_text(encoding="utf-8")
    defined_keys = set(re.findall(r"@\w+\s*{\s*([^,\s]+)\s*,", bib_text))

    sections_dir = root / "paper" / "sections"
    assert sections_dir.is_dir(), "paper/sections directory must exist"

    all_citations: set[str] = set()
    for tex_file in sections_dir.glob("*.tex"):
        content = tex_file.read_text(encoding="utf-8")
        # Extract \cite{key1, key2}
        for match in re.findall(r"\\cite\{([^}]+)\}", content):
            for key in match.split(","):
                clean_key = key.strip()
                if clean_key:
                    all_citations.add(clean_key)

    assert len(all_citations) > 0, "Expected at least one citation in sections/*.tex"
    missing = all_citations - defined_keys
    assert not missing, f"Citations missing from references.bib: {missing}"


def test_referenced_assets_exist() -> None:
    root = _repo_root()
    sections_dir = root / "paper" / "sections"

    for tex_file in list(sections_dir.glob("*.tex")) + [root / "paper" / "main.tex"]:
        content = tex_file.read_text(encoding="utf-8")

        # Check \input{...} (excluding sections/)
        for match in re.findall(r"\\input\{([^}]+)\}", content):
            if match.startswith("sections/"):
                target = root / "paper" / match
            else:
                target = (tex_file.parent / match).resolve()
            if not target.suffix:
                target = target.with_suffix(".tex")
            err_msg = f"{tex_file.name} references non-existent input: {match} ({target})"
            assert target.exists(), err_msg

        # Check \includegraphics{...}
        for match in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", content):
            target = (tex_file.parent / match).resolve()
            err_msg = f"{tex_file.name} references non-existent figure: {match} ({target})"
            assert target.exists(), err_msg


def test_markdown_paper_completeness() -> None:
    paper_md = _repo_root() / "paper" / "paper.md"
    assert paper_md.exists(), "paper/paper.md must exist"
    content = paper_md.read_text(encoding="utf-8")

    assert "# Re-evaluating Graph-Embedding Anomaly Detection" in content
    assert "## Abstract" in content
    assert "## 1. Introduction" in content
    assert "## 2. Background" in content
    assert "## 3. Related Work" in content
    assert "## 4. Approach and Implementation" in content
    assert "## 5. Benchmark Construction" in content
    assert "## 6. Evaluation Setup" in content
    assert "## 7. Results" in content
    assert "## 8. Discussion and Threats to Validity" in content
    assert "## 9. Conclusion and Future Work" in content
    assert "## References" in content

    # Check key empirical claims are reflected
    assert "0.938" in content  # precision
    assert "0.652" in content  # F1
    assert "0.896" in content  # PR-AUC
