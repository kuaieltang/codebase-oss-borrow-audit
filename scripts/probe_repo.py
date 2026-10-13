#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only repo probe for Step 1 of codebase-oss-borrow-audit.

Answers three questions without reading the whole repo:
  1. LOC ranking      - where does the code actually live?
  2. Directory tree   - what shape is this project?
  3. Entry candidates - which files sit on the extraction / core path?

Pure standard library, nothing written, nothing imported from the target.

Usage:
    python probe_repo.py <repo_path> [--top N] [--tree-depth N]
    python probe_repo.py <repo_path> --loc-only
    python probe_repo.py <repo_path> --no-entry --no-tree
"""

import argparse
import os
import re
import sys
from collections import defaultdict

SKIP_DIRS = {
    ".git", ".svn", ".hg", ".idea", ".vscode", ".gradle", ".mypy_cache",
    ".pytest_cache", ".dart_tool", ".next", ".nuxt", ".terraform",
    "node_modules", "__pycache__", "venv", ".venv", "env", "virtualenv",
    "dist", "build", "out", "target", "bin", "obj", "coverage", "vendor",
    "Pods", "DerivedData", ".cxx", "CMakeFiles",
}

SKIP_SUFFIX = (
    ".min.js", ".map", ".lock", ".pyc", ".class", ".o", ".a", ".so",
    ".dll", ".exe", ".wasm", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".svg", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".pdf", ".zip",
    ".gz", ".tar", ".7z", ".mp3", ".mp4", ".wav", ".avi",
)

DEFAULT_EXTS = {
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue",
    ".go", ".rs", ".java", ".kt", ".kts", ".swift", ".rb", ".php",
    ".cs", ".c", ".h", ".cc", ".cpp", ".hpp", ".hs", ".scala",
    ".sql", ".sh", ".yaml", ".yml", ".json", ".toml", ".html", ".css",
    ".md", ".gradle",
}

MAX_FILE_BYTES = 400_000

# Keyword -> what part of a pipeline it usually marks.
ENTRY_KEYWORDS = {
    "extract": ("extract", "predicate", "grounding", "evidence", "match"),
    "parse": ("parse", "decode", "deserialize", "from_json", "to_json"),
    "prompt": ("prompt", "system", "schema", "instruction", "few_shot"),
    "model": ("llm", "openai", "deepseek", "client", "complete", "inference"),
    "persist": ("save", "write", "insert", "upsert", "merge", "replace", "repository", "dao"),
    "sync": ("sync", "pipeline", "orchestrat", "run_extraction", "dispatch"),
    "merge": ("mergerecords", "merge_record", "dedup", "reconcile"),
    "normalize": ("normaliz", "canonical", "resolve_alias", "alias"),
}

# One alternation per group keeps the scan at O(lines x groups) instead of O(lines x words).
KEYWORD_SETS = [
    (group_name, re.compile("|".join(re.escape(w) for w in words), re.IGNORECASE))
    for group_name, words in ENTRY_KEYWORDS.items()
]


class Stat:
    def __init__(self):
        self.lines = 0
        self.hits = 0
        self.groups = set()
        self.sample_lines = []


def iter_source_files(root, wanted_exts):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            if name.endswith(SKIP_SUFFIX):
                continue
            _, ext = os.path.splitext(name)
            if ext.lower() not in wanted_exts:
                continue
            full = os.path.join(dirpath, name)
            yield full


def rel(root, path):
    r = os.path.relpath(path, root)
    return r.replace("\\", "/")


def count_lines(full):
    try:
        with open(full, "rb") as fh:
            chunk = fh.read(MAX_FILE_BYTES)
    except OSError:
        return 0
    if b"\x00" in chunk:
        return 0
    try:
        return chunk.decode("utf-8", errors="ignore").count("\n") + 1
    except UnicodeDecodeError:
        return 0


def scan_keywords(full):
    try:
        with open(full, "rb") as fh:
            raw = fh.read(MAX_FILE_BYTES)
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    try:
        text = raw.decode("utf-8", errors="ignore")
    except UnicodeDecodeError:
        return None

    stat = Stat()
    lines = text.splitlines()
    stat.lines = len(lines)
    for group_name, pattern in KEYWORD_SETS:
        hits = 0
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                hits += 1
                if hits <= 3 and len(stat.sample_lines) < 12:
                    stat.sample_lines.append((idx, group_name, line.strip()[:110]))
        if hits:
            stat.hits += hits
            stat.groups.add(group_name)
    stat.sample_lines.sort(key=lambda t: t[0])
    return stat


def print_tree(root, max_depth):
    print("\n## Directory tree (depth %d)" % max_depth)
    root_depth = root.rstrip(os.sep).count(os.sep)
    seen_dirs = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        depth = dirpath.rstrip(os.sep).count(os.sep) - root_depth
        if depth >= max_depth:
            dirnames[:] = []
            continue
        if seen_dirs >= 60:
            print("  ... (tree truncated, raise --tree-depth or narrow the path)")
            break
        indent = "  " * depth
        srcs = [f for f in filenames if os.path.splitext(f)[1].lower() in DEFAULT_EXTS]
        marker = "/%d files" % len(srcs) if srcs else ""
        print("%s%s/ %s" % (indent, os.path.basename(dirpath) or root, marker))
        seen_dirs += 1


def main():
    ap = argparse.ArgumentParser(description="Read-only repo probe.")
    ap.add_argument("repo", help="Path to the repository under audit")
    ap.add_argument("--top", type=int, default=20, help="Rows per section (default 20)")
    ap.add_argument("--tree-depth", type=int, default=3, help="Directory tree depth (default 3)")
    ap.add_argument("--ext", default="", help="Comma-separated extension allowlist, e.g. .kt,.py")
    ap.add_argument("--loc-only", action="store_true", help="Only print the LOC ranking")
    ap.add_argument("--no-tree", action="store_true", help="Skip the directory tree")
    ap.add_argument("--no-entry", action="store_true", help="Skip the entry-point scan")
    args = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(args.repo))
    if not os.path.isdir(root):
        sys.exit("Not a directory: %s" % root)

    wanted = DEFAULT_EXTS
    if args.ext:
        wanted = {"." + e.lstrip(".").lower() for e in args.ext.split(",") if e.strip()}

    print("Repo: %s" % root)
    print("Extensions: %s" % (", ".join(sorted(wanted)) if len(wanted) < 12 else "%d types" % len(wanted)))

    files = list(iter_source_files(root, wanted))
    if not files:
        sys.exit("No source files matched. Try widening --ext.")

    loc_rows = []
    stats = {}
    for full in files:
        n = count_lines(full)
        if n:
            loc_rows.append((n, rel(root, full)))
        if not args.no_entry and not args.loc_only:
            st = scan_keywords(full)
            if st:
                stats[full] = st

    loc_rows.sort(reverse=True)
    total = sum(n for n, _ in loc_rows)
    print("\n## LOC ranking (top %d of %d files, %d lines total)" % (min(args.top, len(loc_rows)), len(loc_rows), total))
    for n, name in loc_rows[:args.top]:
        print("%7d  %s" % (n, name))
    if not loc_rows:
        print("  (no countable lines)")

    if not args.no_tree and not args.loc_only:
        print_tree(root, args.tree_depth)

    if not args.no_entry and not args.loc_only:
        ranked = []
        for full, st in stats.items():
            if not st.groups:
                continue
            score = len(st.groups) * 20 + min(st.hits, 60)
            ranked.append((score, full, st))
        ranked.sort(key=lambda t: (-t[0], t[1]))
        print("\n## Entry candidates on the core path (top %d)" % min(args.top, len(ranked)))
        for score, full, st in ranked[:args.top]:
            name = rel(root, full)
            groups = ",".join(sorted(st.groups))
            print("\n[%3d] %s   (%s, %d lines)" % (score, name, groups, st.lines))
            for lineno, group, text in st.sample_lines[:3]:
                print("      :%-5d %-6s %s" % (lineno, group, text))
        if not ranked:
            print("  (no keyword hits -- widen the search or pass different --ext)")

    print("\nHint: read the top-3 LOC files and the top-5 entry candidates before anything else.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
