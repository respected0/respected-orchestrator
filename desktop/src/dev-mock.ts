// Development only (loaded from main.tsx behind `import.meta.env.DEV` and `?mock`): a stand-in for the Tauri bridge so the screens can be
// looked at in a plain browser. The data is a fixture the real engine produced from a synthetic home; it is never part of a production build.
import fixture from '../tests/fixtures/inventory.json';

type Internals = { invoke: (cmd: string, args?: unknown) => Promise<unknown>; transformCallback: () => number; metadata: unknown };

(window as unknown as { __TAURI_INTERNALS__: Internals }).__TAURI_INTERNALS__ = {
  metadata: { currentWindow: { label: 'main' }, currentWebview: { label: 'main', windowLabel: 'main' } },
  transformCallback: () => 0,
  invoke: async (cmd: string) => {
    if (cmd === 'engine_status') return { version: 'mock-fixture', healthy: true };
    if (cmd === 'capability_inventory') return fixture;
    if (cmd.startsWith('plugin:event|')) return 0;
    throw { error: { kind: 'MockUnsupported' }, hint: `mock has no ${cmd}` };
  },
};
