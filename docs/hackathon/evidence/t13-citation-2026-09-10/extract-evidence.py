from pathlib import Path
import compression.zstd as zstd
import hashlib
import json
import re
import urllib.request

repo = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').is_file() and (p / 'pyproject.toml').is_file())
ready = repo.parent / 'competition-product-readiness'
scratch = repo / '.context/t13-citation-live'
output = repo / 'docs/hackathon/evidence/t13-citation-2026-09-10'
output.mkdir(parents=True, exist_ok=True)
root = ready / '.context/dsh-dev/runtime-Cn0Ifc/harness/sessions'

def write(name, value):
    (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def read_session(path, prompt):
    content = path.read_bytes()
    text = zstd.decompress(content).decode()
    assert prompt in text, 'only inspect this evaluation session'
    return [json.loads(line) for line in text.splitlines()], hashlib.sha256(content).hexdigest()

def get(path):
    req = urllib.request.Request(
        'http://127.0.0.1:18083/api/v1/analytics/competition' + path,
        headers={'Authorization': 'Bearer b0-competition-synth-token-32chars'},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)

bindings = {
    'A3': next(root.glob('*/session-e1190317-b53b-4b12-b468-e0185a0ea3e3')),
    'B2': next(root.glob('*/session-e1789576-43a2-402e-b77f-e35f83a9e758')),
}
summary = {}
for case, session in bindings.items():
    request = json.loads((scratch / f'{case}-request.json').read_text())
    rows, digest = read_session(session / 'session.v2.jsonl.zstd', request['prompt'])
    calls, results, messages, usage, packages = [], [], [], [], []
    for row in rows:
        data = row.get('data', {})
        if row['type'] == 'tool/call':
            calls.append({k: data[k] for k in ['callId', 'name', 'arguments']})
        elif row['type'] == 'tool/result':
            for block in data['message']['content']:
                for item in block.get('content', []):
                    if item.get('type') == 'text':
                        try:
                            value = json.loads(item['text'])
                        except ValueError:
                            continue
                        if isinstance(value, dict) and value.get('resource') == 'references/evidence-policy.md':
                            packages.append({k: value[k] for k in ['package_digest', 'content_digest', 'resource']})
                        if isinstance(value, dict) and 'resolved_condition' in value and 'result' in value:
                            results.append(value)
        elif row['type'] == 'assistant/message':
            # Exclude the model's reasoning and request contents.
            text = ''.join(c['text'] for c in data['message']['content'] if c.get('type') == 'text')
            if text:
                messages.append(text)
            if data.get('usage'):
                usage.append(data['usage'])
    assert rows[-1]['type'] == 'turn/end'
    assert results
    assert packages and all(p['package_digest'] == 'ae3b0f92ac34a11c161b246648ca1c3421cce02c208d2704f708715f72cc0713' for p in packages)
    actual_runs = {step['result']['run_id'] for step in results}
    cited_runs = set(re.findall(r'run_diag_[a-z0-9]+', messages[-1]))
    assert cited_runs <= actual_runs
    if 'run_id' in messages[-1]:
        assert cited_runs, 'run_id label without a real returned run id'
    assert 'result_id/run_id=' not in messages[-1].replace(' ', '')
    persisted = []
    for step in results:
        result = step['result']
        assert result['completeness'] == 'COMPLETE' and step['analysis_complete'] is False
        assert result['result_id'] != result['run_id']
        condition = result['resolved_condition']
        assert condition['current_period']['start_date'] == '2026-08-01'
        assert condition['current_period']['end_date'] == '2026-08-31'
        assert condition['comparison_period']['start_date'] == '2025-08-01'
        assert condition['comparison_period']['end_date'] == '2025-08-31'
        assert condition['timezone'] == 'Asia/Shanghai'
        assert condition['sample_mode'] == 'INCLUDE'
        assert condition['sample_channel_ids'] is None
        assert condition['sales_scope']['kind'] == condition['history_scope']['kind'] == 'ALL'
        assert result['result_id'] in messages[-1]
        assert result['facts']['current']['gsv'] == 410
        assert result['facts']['comparison']['gsv'] == 305
        assert result['facts']['difference'] == 105
        assert abs(result['facts']['change_ratio'] - 105 / 305) < 1e-12
        assert result['contains_real_data'] is False
        persisted.append({'capability_id': result['capability_id'], 'result_id': result['result_id'], 'run_id': result['run_id'], 'evidence_digest': result['evidence_digest'], 'data_digest': result['data_digest'], 'filter_hash': result['resolved_condition']['filter_hash']})
    summary[case] = {
        'session_id': session.name,
        'native_log_sha256': digest,
        'turn_reason': rows[-1]['data']['reason'],
        'native_tool_calls': len(calls),
        'computation_calls': len(results),
        'results': persisted,
        'uncached_input_tokens': sum(u.get('inputTokens', 0) for u in usage),
        'cached_input_tokens': sum(u.get('cacheReadTokens', 0) for u in usage),
        'output_tokens': sum(u.get('outputTokens', 0) for u in usage),
        'numeric_and_condition_checks': 'PASS',
        'citation_check': 'PASS: cited run IDs match actual returned IDs; no combined alias',
        'method_packages': packages,
        'fees': 'UNKNOWN: provider billing not queried; these are native usage counters',
    }
    write(f'{case}-request.json', request)
    write(f'{case}-tools.json', {'calls': calls, 'computed_results': results})
    (output / f'{case}-answer.md').write_text(messages[-1] + '\n')
    write(f'{case}-native-summary.json', summary[case])

# Different supported capability IDs are allowed to calculate the same facts.
if summary['A3']['results'][0]['capability_id'] == summary['B2']['results'][0]['capability_id']:
    assert summary['A3']['results'][0]['evidence_digest'] == summary['B2']['results'][0]['evidence_digest']
assert summary['A3']['results'][0]['filter_hash'] == summary['B2']['results'][0]['filter_hash']
assert summary['A3']['results'][0]['data_digest'] == summary['B2']['results'][0]['data_digest']
current = get('/results')
by_id = {item['result_id']: item for item in current['items']}
for case in summary.values():
    for item in case['results']:
        assert item['result_id'] in by_id
        saved = by_id[item['result_id']]
        assert saved['evidence_digest'] == item['evidence_digest']
write('persisted-result-check.json', {'results_after': len(current['items']), 'matched': [r for c in summary.values() for r in c['results']]})
write('verification.json', {'cases': summary, 'overall': 'PASS for these bounded equivalence and citation cases only; full T13 remains PARTIAL'})
print(json.dumps({'cases': list(summary), 'persisted_results': len(current['items']), 'overall': 'bounded cases PASS; full T13 PARTIAL'}, ensure_ascii=False))
