import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once, EventEmitter } from 'node:events';
import { createDiagnosticSink } from './diagnostic-sink.mjs';

test('a real closed stderr consumer is reported once and the supervisor remains alive', async () => {
  const child = spawn(process.execPath, ['--input-type=module', '-e', `
    import {createDiagnosticSink} from ${JSON.stringify(new URL('./diagnostic-sink.mjs', import.meta.url).href)};
    let closures = 0;
    const sink = createDiagnosticSink(process.stderr, () => closures++);
    process.once('message', () => {
      sink.write('diagnostic before consumer closure is observed');
      setTimeout(() => {
        const accepted = sink.write('must not write to the closed pipe');
        process.send({closures, accepted});
        process.disconnect();
      }, 100);
    });
    process.send('ready');
  `], { stdio: ['ignore', 'ignore', 'pipe', 'ipc'] });
  const exited = once(child, 'exit');
  const timer = setTimeout(() => child.kill('SIGKILL'), 5000);
  try {
    assert.deepEqual(await once(child, 'message'), ['ready', undefined]);
    child.stderr.destroy();
    const result = once(child, 'message');
    child.send('write');
    assert.deepEqual((await result)[0], { closures: 1, accepted: false });
    assert.deepEqual(await exited, [0, null]);
  } finally { clearTimeout(timer); if (child.exitCode === null) child.kill(); }
});

test('unexpected synchronous and asynchronous stream errors are not swallowed', () => {
  const stream = new EventEmitter();
  const error = Object.assign(new Error('I/O failure'), {code: 'EIO'});
  stream.write = () => { throw error; };
  const sink = createDiagnosticSink(stream, () => assert.fail('unexpected closure'));
  assert.throws(() => sink.write('data'), error);
  assert.throws(() => stream.emit('error', error), error);
});

test('synchronous EPIPE disables subsequent writes and repeated events remain bounded', () => {
  const stream = new EventEmitter();
  const error = Object.assign(new Error('closed'), {code: 'EPIPE'});
  let writes = 0, closures = 0;
  stream.write = () => { writes++; throw error; };
  const sink = createDiagnosticSink(stream, () => closures++);
  assert.equal(sink.write('first'), false);
  assert.equal(sink.write('second'), false);
  stream.emit('error', error);
  assert.equal(writes, 1);
  assert.equal(closures, 1);
});
