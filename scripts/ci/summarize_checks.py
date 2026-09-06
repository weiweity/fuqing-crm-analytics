#!/usr/bin/env python3
"""Summarize per-group JUnit children (pytest's root is <testsuites>)."""
from pathlib import Path
import json
import sys
import xml.etree.ElementTree as ET


def summarize(directory: Path) -> dict:
    result = {key: 0 for key in ('tests', 'failures', 'errors', 'skipped')}
    result['time'] = 0.0
    files = sorted(directory.glob('group-*.xml'))
    for file in files:
        root = ET.parse(file).getroot()
        suites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
        for suite in suites:
            for key in ('tests', 'failures', 'errors', 'skipped'):
                result[key] += int(suite.get(key, '0'))
            result['time'] += float(suite.get('time', '0'))
    result['groups_with_junit'] = len(files)
    summary = directory / 'summary.json'
    result['runner_returncode'] = json.loads(summary.read_text()).get('returncode') if summary.is_file() else None
    return result


if __name__ == '__main__':
    print(json.dumps(summarize(Path(sys.argv[1])), ensure_ascii=False))
