/** Local TODO-list plugin for the Hermes dashboard. */

/* eslint-disable no-undef */
const {
  React,
  hooks: { useState, useEffect, useCallback },
  components: { Button, Badge, Card, CardHeader, CardTitle, CardContent },
  fetchJSON,
} = window.__HERMES_PLUGIN_SDK__;

const STATUS_LABELS = {
  open: "Open",
  in_progress: "In Progress",
  done: "Done",
};

function TodoPage() {
  const [data, setData] = useState({ items: [], statuses: [] });
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [progressNotes, setProgressNotes] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchJSON("/api/plugins/todo/list")
      .then((payload) => setData(payload))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const addTodo = useCallback(() => {
    setBusy(true);
    setError(null);
    fetchJSON("/api/plugins/todo/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, notes }),
    })
      .then(() => {
        setTitle("");
        setNotes("");
        load();
      })
      .catch((e) => setError(String(e)))
      .finally(() => setBusy(false));
  }, [title, notes, load]);

  const updateTodo = useCallback(
    (id, patch) => {
      setBusy(true);
      setError(null);
      fetchJSON(`/api/plugins/todo/update/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      })
        .then(() => load())
        .catch((e) => setError(String(e)))
        .finally(() => setBusy(false));
    },
    [load]
  );

  const claimNext = useCallback(() => {
    setBusy(true);
    setError(null);
    fetchJSON("/api/plugins/todo/claim-next", { method: "POST" })
      .then((r) => {
        if (!r.ok) setError("No open TODO item to claim.");
        load();
      })
      .catch((e) => setError(String(e)))
      .finally(() => setBusy(false));
  }, [load]);

  const deleteTodo = useCallback(
    (id) => {
      setBusy(true);
      setError(null);
      fetchJSON("/api/plugins/todo/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      })
        .then(() => load())
        .catch((e) => setError(String(e)))
        .finally(() => setBusy(false));
    },
    [load]
  );

  const items = data?.items ?? [];
  const grouped = {
    open: items.filter((item) => item.status === "open"),
    in_progress: items.filter((item) => item.status === "in_progress"),
    done: items.filter((item) => item.status === "done"),
  };

  return (
    <div style={{ padding: "1.5rem", maxWidth: "980px" }}>
      <div style={{ display: "flex", gap: "1rem", alignItems: "center", marginBottom: "1rem" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "bold", flex: 1 }}>Local TODO</h2>
        <Button size="sm" variant="outline" onClick={claimNext} disabled={busy}>Claim next</Button>
        <Button size="sm" onClick={load} disabled={loading}>{loading ? "Loading…" : "Refresh"}</Button>
      </div>

      {error && <Alert>{error}</Alert>}

      <Card>
        <CardHeader><CardTitle>Add TODO</CardTitle></CardHeader>
        <CardContent>
          <Input value={title} placeholder="Task title" onChange={(e) => setTitle(e.target.value)} />
          <Textarea value={notes} placeholder="Optional notes" onChange={(e) => setNotes(e.target.value)} />
          <Button size="sm" onClick={addTodo} disabled={busy || !title.trim()}>Add</Button>
        </CardContent>
      </Card>

      <div style={{ height: "1rem" }} />

      {Object.keys(grouped).map((status) => (
        <TodoColumn
          key={status}
          status={status}
          items={grouped[status]}
          updateTodo={updateTodo}
          deleteTodo={deleteTodo}
          progressNotes={progressNotes}
          setProgressNotes={setProgressNotes}
          disabled={busy}
        />
      ))}
    </div>
  );
}

function TodoColumn({ status, items, updateTodo, deleteTodo, progressNotes, setProgressNotes, disabled }) {
  return (
    <Card style={{ marginBottom: "1rem" }}>
      <CardHeader>
        <CardTitle>{STATUS_LABELS[status]} ({items.length})</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p style={{ fontSize: "0.875rem", opacity: 0.6 }}>No items.</p>
        ) : (
          items.map((item) => (
            <div key={item.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", padding: "0.75rem 0" }}>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <Badge>{item.id}</Badge>
                <strong style={{ flex: 1 }}>{item.title}</strong>
                <StatusButtons item={item} updateTodo={updateTodo} disabled={disabled} />
                <Button size="sm" variant="outline" onClick={() => deleteTodo(item.id)} disabled={disabled}>Delete</Button>
              </div>
              {item.notes && <p style={{ margin: "0.5rem 0", opacity: 0.75 }}>{item.notes}</p>}
              {(item.progress || []).length > 0 && (
                <ul style={{ margin: "0.5rem 0", paddingLeft: "1.25rem", fontSize: "0.875rem", opacity: 0.75 }}>
                  {item.progress.map((entry, idx) => <li key={`${item.id}-${idx}`}>{entry.at}: {entry.note}</li>)}
                </ul>
              )}
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                <Input
                  value={progressNotes[item.id] || ""}
                  placeholder="Progress note"
                  onChange={(e) => setProgressNotes((notes) => ({ ...notes, [item.id]: e.target.value }))}
                />
                <Button
                  size="sm"
                  disabled={disabled || !(progressNotes[item.id] || "").trim()}
                  onClick={() => {
                    updateTodo(item.id, { progress_note: progressNotes[item.id] || "" });
                    setProgressNotes((notes) => ({ ...notes, [item.id]: "" }));
                  }}
                >Add note</Button>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function StatusButtons({ item, updateTodo, disabled }) {
  return ["open", "in_progress", "done"].map((status) => (
    <Button
      key={status}
      size="sm"
      variant={item.status === status ? "default" : "outline"}
      disabled={disabled || item.status === status}
      onClick={() => updateTodo(item.id, { status })}
    >
      {STATUS_LABELS[status]}
    </Button>
  ));
}

function Alert({ children }) {
  return <div style={{ padding: "0.75rem", marginBottom: "1rem", borderRadius: "0.375rem", color: "#f87171", background: "rgba(239,68,68,0.1)" }}>{children}</div>;
}

function Input(props) {
  return <input {...props} style={{ width: "100%", padding: "0.5rem", marginBottom: "0.5rem", borderRadius: "0.375rem", border: "1px solid rgba(255,255,255,0.2)", background: "transparent", color: "inherit" }} />;
}

function Textarea(props) {
  return <textarea {...props} rows={3} style={{ width: "100%", padding: "0.5rem", marginBottom: "0.5rem", borderRadius: "0.375rem", border: "1px solid rgba(255,255,255,0.2)", background: "transparent", color: "inherit" }} />;
}

window.__HERMES_PLUGINS__.register("todo", TodoPage);
