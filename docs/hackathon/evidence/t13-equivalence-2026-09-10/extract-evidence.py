from pathlib import Path
import compression.zstd as zstd
import hashlib
import json
import urllib.request

repo = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').is_file() and (p / 'pyproject.toml').is_file())
ready = repo.parent / 'competition-product-readiness'
scratch = repo / '.context/t13-equivalence-live'
output = repo / 'docs/hackathon/evidence/t13-equivalence-2026-09-10'
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
    'A2': next(root.glob('*/session-f7203c55-5893-4912-afb5-5af95dc7b863')),
    'B': next(root.glob('*/session-71832c44-c365-47fe-abae-29b2ee6651b0')),
}
summary = {}
for case, session in bindings.items():
    request = json.loads((scratch / f'{case}-request.json').read_text())
    rows, digest = read_session(session / 'session.v2.jsonl.zstd', request['prompt'])
    calls, results, messages, usage = [], [], [], []
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
        assert result['run_id'] not in messages[-1]
        assert 'result_id/run_id' in messages[-1]
        assert result['facts']['current']['gsv'] == 410
        assert result['facts']['comparison']['gsv'] == 305
        assert result['facts']['difference'] == 105
        assert abs(result['facts']['change_ratio'] - 105 / 305) < 1e-12
        assert result['contains_real_data'] is False
        persisted.append({'result_id': result['result_id'], 'run_id': result['run_id'], 'evidence_digest': result['evidence_digest'], 'data_digest': result['data_digest'], 'filter_hash': result['resolved_condition']['filter_hash']})
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
        'citation_check': 'FAIL: final answer aliases result_id/run_id to result_id although native result has distinct IDs',
        'fees': 'UNKNOWN: provider billing not queried; these are native usage counters',
    }
    write(f'{case}-request.json', request)
    write(f'{case}-tools.json', {'calls': calls, 'computed_results': results})
    (output / f'{case}-answer.md').write_text(messages[-1] + '\n')
    write(f'{case}-native-summary.json', summary[case])

assert summary['A2']['results'][0]['evidence_digest'] == summary['B']['results'][0]['evidence_digest']
assert summary['A2']['results'][0]['filter_hash'] == summary['B']['results'][0]['filter_hash']
assert summary['A2']['results'][0]['data_digest'] == summary['B']['results'][0]['data_digest']
current = get('/results')
by_id = {item['result_id']: item for item in current['items']}
for case in summary.values():
    for item in case['results']:
        assert item['result_id'] in by_id
        saved = by_id[item['result_id']]
        assert saved['evidence_digest'] == item['evidence_digest']
write('persisted-result-check.json', {'results_after': len(current['items']), 'matched': [r for c in summary.values() for r in c['results']]})
write('verification.json', {'cases': summary, 'overall': 'PARTIAL: numeric equivalence passed, citation failed; method correction awaits real rerun'})
write('A-transport-failure.json', {'request': json.loads((scratch / 'A-request.json').read_text()), 'outcome': 'TRANSPORT', 'retry_display': '5/5', 'computed_results': 0, 'error_metadata': json.loads((scratch / 'A-error-metadata.json').read_text()), 'public_ca_connectivity': json.loads((scratch / 'public-connectivity.json').read_text()), 'native_nested_cause': 'not persisted; certificate attribution remains an inference'})
print(json.dumps({'cases': list(summary), 'persisted_results': len(current['items']), 'overall': 'PARTIAL'}, ensure_ascii=False))
