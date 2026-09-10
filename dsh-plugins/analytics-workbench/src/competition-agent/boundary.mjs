/**
 * Keep the competition method surface closed after a method call.
 *
 * The native DSH tools remain available in ordinary turns. Once a model has
 * entered this method family, however, a failed method result must not become
 * an excuse to inspect files or run commands. The state is keyed by the live
 * agent and is cleared only when that turn stops, so multiple model steps in
 * one turn remain covered.
 */

import { REGISTERED_TOOLS } from './family.mjs';

const PTC_TRANSPORT = 'run_code';

export function createCompetitionToolBoundary() {
  const enteredAgents = new WeakSet();

  function mark(execution) {
    if (execution?.agent && REGISTERED_TOOLS.includes(execution.name)) {
      enteredAgents.add(execution.agent);
    }
    return undefined;
  }

  function clear(agent) {
    if (agent) enteredAgents.delete(agent);
  }

  function guard(execution) {
    const agent = execution?.agent;
    if (!agent || !enteredAgents.has(agent)) return undefined;
    // PTC is the native transport. Its nested calls still pass through this
    // guard, so only registered competition methods can run inside it.
    if (execution.name === PTC_TRANSPORT || REGISTERED_TOOLS.includes(execution.name)) {
      return undefined;
    }
    return 'competition-growth method boundary: after a competition method call, use only registered competition methods; native filesystem, shell, and other tools are unavailable for this turn';
  }

  return Object.freeze({ mark, clear, guard });
}
