"""Read-only public visibility inventory; intentionally never print matched bytes.

Not a substitute for reviewing releases, Actions logs, comments and
Third-party app permissions. The historic Git object graph is checked for
high-confidence credential material without disclosing it to CI logs.
"""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys

RULES = {
    "private-key-pem": re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    "github-token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9_]{25,}|github_pat_[A-Za-z0-9_]{25,})"),
    "aws-key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "openai-secret": re.compile(rb"\bsk-[A-Za-z0-9_-]{30,}\b"),
    "google-api-key": re.compile(rb"\bAIza[0-9A-Za-z_-]{32,}\b"),
}
METADATA = {
    "local-network-address": re.compile(rb"\b(?:10\.(?:[0-9]{1,3}\.){2}|192\.168\.(?:[0-9]{1,3}\.)|172\.(?:1[6-9]|2[0-9]|3[01])\.(?:[0-9]{1,3}\.)\b)"),
    "explicit-private-path": re.compile(rb"/mnt/(?:storage|apps|[A-Za-z0-9_-]+)/(?:[A-Za-z0-9_ -]+/){1,}"),
    "email-address": re.compile(rb"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}
TEXT_SUFFIXES={".md",".txt",".py",".yaml",".yml",".json",".sh",".toml",".ini",".cfg",".conf",".env",".js",".html",".xml",".csv",".sql",".log"}
MAX_BLOB=2_000_000


def objects():
    data=subprocess.check_output(["git","rev-list","--objects","--all"],text=True)
    paths={}
    for line in data.splitlines():
        sha,_,name=line.partition(" ")
        if name and Path(name).suffix.lower() in TEXT_SUFFIXES and sha not in paths:
            paths[sha]=name
    return paths


def report():
    paths=objects()
    process=subprocess.Popen(["git","cat-file","--batch"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    counts=Counter(); signals={}
    scanned=0
    try:
        for sha,path in paths.items():
            process.stdin.write((sha+"\n").encode())
            process.stdin.flush()
            header=process.stdout.readline()
            try:
                _object,kind,size_raw=header.strip().split()
                size=int(size_raw)
            except ValueError:
                raise RuntimeError("Git object scan was incomplete")
            if size>MAX_BLOB:
                # Still consume each blob before the next one. Record skipped count.
                process.stdout.read(size+1)
                counts["skipped_oversize_blob"]+=1
                continue
            value=process.stdout.read(size)
            process.stdout.read(1)
            if kind!=b"blob":continue
            scanned+=1
            for name,rx in {**RULES,**METADATA}.items():
                if rx.search(value):
                    counts[name]+=1
                    signals.setdefault(name,[])
                    if len(signals[name])<30:signals[name].append(path)
    finally:
        process.stdin.close()
        process.stdout.close()
        process.terminate()
        process.wait(timeout=10)
    return {
      "scope":"all locally fetched reachable Git objects, current files and historical text blobs",
      "scanned_unique_text_blobs":scanned,
      "pattern_matches_by_rule":dict(counts),
      "example_paths_only":signals,
      "potential_credentials_found":bool(any(counts.get(k) for k in RULES)),
      "metadata_manual_review_required":bool(any(counts.get(k) for k in METADATA)),
      "other_public_surfaces_reviewed":False,
      "warning":"Historic source strings can remain visible after README edits. Review Actions logs, releases, comments and package visibility separately.",
    }


if __name__=="__main__":
    target=Path(sys.argv[1]) if len(sys.argv)>1 else Path("/tmp/bibliothekar-public-inventory.json")
    result=report()
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("Public Git object scan completed:",result["scanned_unique_text_blobs"],"text blobs.")
    print("Credential-pattern classes:",sum(bool(result["pattern_matches_by_rule"].get(k)) for k in RULES))
    print("Private-metadata classes:",sum(bool(result["pattern_matches_by_rule"].get(k)) for k in METADATA))
    print("Public visibility requires a human review of non-source GitHub surfaces.")
