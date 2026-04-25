const assert = require("node:assert/strict");
const test = require("node:test");
const vm = require("node:vm");

async function createHarness(fetchJSON = async () => ({ items: [], statuses: [] })) {
  const state = [];
  let stateIndex = 0;
  const effects = [];
  const registered = {};

  function useState(initialValue) {
    const index = stateIndex;
    if (state.length === index) state.push(initialValue);
    stateIndex += 1;
    return [
      state[index],
      (nextValue) => {
        state[index] = typeof nextValue === "function" ? nextValue(state[index]) : nextValue;
      },
    ];
  }

  function useCallback(callback) {
    return callback;
  }

  function useEffect(callback) {
    effects.push(callback);
  }

  function createElement(type, props, ...children) {
    if (typeof type === "function") {
      const nextProps = { ...(props || {}) };
      if (children.length > 0) nextProps.children = children;
      return type(nextProps);
    }
    return { type, props: props || {}, children };
  }

  const React = { createElement, Fragment: Symbol("Fragment") };
  const component = (name) => function Component(props) {
    const childValues = props?.children === undefined ? [] : Array.isArray(props.children) ? props.children : [props.children];
    return createElement(name, props, ...childValues);
  };

  const context = {
    window: {
      __HERMES_PLUGIN_SDK__: {
        React,
        hooks: { useState, useEffect, useCallback },
        components: {
          Button: component("Button"),
          Badge: component("Badge"),
          Card: component("Card"),
          CardHeader: component("CardHeader"),
          CardTitle: component("CardTitle"),
          CardContent: component("CardContent"),
        },
        fetchJSON,
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
  const fs = require("node:fs");
  const path = require("node:path");
  const { execFileSync } = require("node:child_process");
  const root = path.join(__dirname, "..");
  const bundlePath = path.join(root, "dist", "index.js");
  if (!fs.existsSync(bundlePath)) {
    execFileSync("npm", ["run", "build"], { cwd: root, stdio: "inherit" });
  }
  const bundle = fs.readFileSync(bundlePath, "utf8");
  vm.runInContext(bundle, context);

  function render(name = "todo") {
    stateIndex = 0;
    return registered[name]();
  }

  return { context, registered, render, effects, state };
}

function findAll(node, predicate, matches = []) {
  if (!node || typeof node !== "object") return matches;
  if (predicate(node)) matches.push(node);
  for (const child of allChildren(node)) findAll(child, predicate, matches);
  return matches;
}

function allChildren(node) {
  const children = [...(node.children || [])];
  if (node.props?.children !== undefined) {
    if (Array.isArray(node.props.children)) children.push(...node.props.children);
    else children.push(node.props.children);
  }
  return children;
}

function flattenText(node) {
  if (typeof node === "string") return node;
  if (!node || typeof node !== "object") return "";
  return allChildren(node).map(flattenText).join("");
}

test("registers the TODO plugin", async () => {
  const harness = await createHarness();
  assert.equal(typeof harness.registered.todo, "function");
});

test("loads TODO items from the JSON API", async () => {
  const calls = [];
  const harness = await createHarness(async (path) => {
    calls.push(path);
    return { items: [], statuses: ["open", "in_progress", "done", "cancelled"] };
  });

  harness.render();
  await harness.effects[0]();

  assert.deepEqual(calls, ["/api/plugins/todo/list"]);
  assert.deepEqual(harness.state[0].statuses, ["open", "in_progress", "done", "cancelled"]);
});

test("renders the add form and action buttons", async () => {
  const harness = await createHarness();
  const tree = harness.render();
  const buttons = findAll(tree, (node) => node.type === "Button").map((node) => flattenText(node));
  assert.ok(buttons.some((label) => label.includes("Claim next")));
  assert.ok(buttons.some((label) => label.includes("Refresh") || label.includes("Loading…")));
  assert.ok(buttons.some((label) => label.includes("Add")));
});
