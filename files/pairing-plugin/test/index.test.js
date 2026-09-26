const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const { execFileSync } = require("node:child_process");

const root = path.join(__dirname, "..");
const bundlePath = path.join(root, "dist", "index.js");

execFileSync("npm", ["run", "build"], { cwd: root, stdio: "inherit" });

// Renders the page once with the given list data and returns the element
// tree plus every request the page sent.
function render(data) {
  const requests = [];
  const registered = {};
  const React = {
    createElement(type, props, ...children) {
      if (typeof type === "function") return type({ ...(props || {}), children });
      return { type, props: props || {}, children };
    },
    Fragment: Symbol("Fragment"),
  };
  let call = 0;
  const context = {
    setInterval() {},
    clearInterval() {},
    window: {
      __HERMES_PLUGIN_SDK__: {
        React,
        hooks: {
          // first useState of the page is the list data
          useState(initial) {
            return [call++ === 0 ? data : initial, () => {}];
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
        fetchJSON(url, options) {
          requests.push({ url, body: options?.body ? JSON.parse(options.body) : undefined });
          return new Promise(() => {});
        },
      },
      __HERMES_PLUGINS__: {
        register(name, page) {
          registered[name] = page;
        },
      },
    },
  };
  context.React = React;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(bundlePath, "utf8"), context);
  return { registered, tree: registered.pairing && registered.pairing(), requests };
}

function find(node, predicate, found = []) {
  if (Array.isArray(node)) node.forEach((child) => find(child, predicate, found));
  else if (node && typeof node === "object") {
    if (predicate(node)) found.push(node);
    find(node.children, predicate, found);
  }
  return found;
}

const pendingRequest = {
  platform: "telegram",
  request_id: "0123456789abcdef",
  user_id: "12345",
  user_name: "alice",
  age_minutes: 3,
};

test("registers the pairing plugin", () => {
  assert.equal(typeof render({ pending: [], approved: [] }).registered.pairing, "function");
});

test("approve sends the request id of the pending request", () => {
  const { tree, requests } = render({ pending: [pendingRequest], approved: [] });
  const [approve] = find(tree, (n) => n.type === "Button" && JSON.stringify(n.children).includes("Approve"));

  approve.props.onClick();

  const sent = requests.find((r) => r.url === "/api/plugins/pairing/approve");
  assert.deepEqual(sent.body, { platform: "telegram", request_id: "0123456789abcdef" });
});

test("pending row shows user and age, never a code column", () => {
  const { tree } = render({ pending: [pendingRequest], approved: [] });
  const headers = find(tree, (n) => n.type === "th").map((n) => JSON.stringify(n.children));

  assert.ok(!headers.some((h) => h.includes("Code")));
  assert.ok(JSON.stringify(tree).includes("alice"));
  assert.ok(JSON.stringify(tree).includes('[3,"m ago"]'));
});

test("revoke sends platform and user id", () => {
  const { tree, requests } = render({ pending: [], approved: [{ platform: "discord", user_id: "777", user_name: "bob" }] });
  const [revoke] = find(tree, (n) => n.type === "Button" && JSON.stringify(n.children).includes("Revoke"));

  revoke.props.onClick();

  const sent = requests.find((r) => r.url === "/api/plugins/pairing/revoke");
  assert.deepEqual(sent.body, { platform: "discord", user_id: "777" });
});
