const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const { execFileSync } = require("node:child_process");

const root = path.join(__dirname, "..");
const sourcePath = path.join(root, "src", "index.jsx");
const bundlePath = path.join(root, "dist", "index.js");

function readSource() {
  return fs.readFileSync(sourcePath, "utf8");
}

function createHarness(fetchJSON = async () => ({ items: [], statuses: [] })) {
  const registered = {};
  const context = {
    window: {
      __HERMES_PLUGIN_SDK__: {
        React: {
          createElement(type, props, ...children) {
            if (typeof type === "function") return type({ ...(props || {}), children });
            return { type, props: props || {}, children };
          },
          Fragment: Symbol("Fragment"),
        },
        hooks: {
          useState(initialValue) {
            return [initialValue, () => {}];
          },
          useEffect() {},
          useCallback(callback) {
            return callback;
          },
        },
        components: Object.fromEntries(
          ["Button", "Badge", "Card", "CardHeader", "CardTitle", "CardContent"].map((name) => [
            name,
            (props) => ({ type: name, props: props || {}, children: props?.children || [] }),
          ])
        ),
        fetchJSON,
      },
      __HERMES_PLUGINS__: {
        register(name, page) {
          registered[name] = page;
        },
      },
    },
  };
  context.React = context.window.__HERMES_PLUGIN_SDK__.React;
  vm.createContext(context);
  execFileSync("npm", ["run", "build"], { cwd: root, stdio: "inherit" });
  vm.runInContext(fs.readFileSync(bundlePath, "utf8"), context);
  return { registered };
}

test("registers the TODO plugin", () => {
  const harness = createHarness();
  assert.equal(typeof harness.registered.todo, "function");
});

test("root UI does not expose AI-only transitions", () => {
  const source = readSource();

  assert.ok(!source.includes("Claim next"));
  assert.ok(!source.includes("StatusButtons"));
  assert.ok(!source.includes("/api/plugins/todo/claim-next"));
  assert.ok(!source.includes("/api/plugins/todo/done/"));
});

test("UI exposes only user-owned transition actions", () => {
  const source = readSource();

  assert.ok(source.includes("/api/plugins/todo/cancel/"));
  assert.ok(source.includes("/api/plugins/todo/reject/"));
  assert.ok(source.includes("/api/plugins/todo/accept/"));
  assert.ok(source.includes("/api/plugins/todo/delete"));
  assert.ok(source.includes("Reject"));
  assert.ok(source.includes("Accept"));
  assert.ok(source.includes("Delete"));
});

test("supports accepted state", () => {
  const source = readSource();

  assert.ok(source.includes("accepted: \"Accepted\""));
  assert.ok(source.includes("\"accepted\""));
  assert.ok(source.includes("item.status === \"accepted\""));
});

test("mutations update local state without requiring manual reload", () => {
  const source = readSource();

  assert.ok(source.includes("upsertItem(payload.item)"));
  assert.ok(source.includes("removeItem(options.removeId)"));
  assert.ok(!source.includes(".then(() => load())"));
});

test("polls the TODO API for browser auto-refresh", () => {
  const source = readSource();

  assert.ok(source.includes("setInterval"));
  assert.ok(source.includes("TODO_REFRESH_INTERVAL_MS"));
  assert.ok(source.includes("clearInterval"));
});
