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
  accepted: "Accepted",
  cancelled: "Cancelled",
};

const STATUS_ORDER = ["open", "in_progress", "done", "accepted", "cancelled"];

function TodoPage() {
  const [data, setData] = useState({ items: [], statuses: STATUS_ORDER });
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [progressNotes, setProgressNotes] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return fetchJSON("/api/plugins/todo/list")
      .then((payload) => setData(payload))
      .catch((e) => setError(readError(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const upsertItem = useCallback((item) => {
    if (!item) return;
    setData((current) => {
      const items = current?.items || [];
      const index = items.findIndex((entry) => entry.id === item.id);
      const nextItems = index === -1 ? [...items, item] : items.map((entry) => (entry.id === item.id ? item : entry));
      return { ...(current || {}), items: nextItems };
    });
  }, []);

  const removeItem = useCallback((id) => {
    setData((current) => ({
      ...(current || {}),
      items: (current?.items || []).filter((item) => item.id !== id),
    }));
  }, []);

  const addTodo = useCallback(() => {
    setBusy(true);
    setError(null);
    fetchJSON("/api/plugins/todo/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, notes }),
    })
      .then((payload) => {
        upsertItem(payload.item);
        setTitle("");
        setNotes("");
      })
      .catch((e) => setError(readError(e)))
      .finally(() => setBusy(false));
  }, [title, notes, upsertItem]);

  const updateTodo = useCallback(
    (id, patch) => {
      setBusy(true);
      setError(null);
      return fetchJSON(`/api/plugins/todo/update/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      })
        .then((payload) => upsertItem(payload.item))
        .catch((e) => setError(readError(e)))
        .finally(() => setBusy(false));
    },
    [upsertItem]
  );

  const postAction = useCallback(
    (path, body = {}, options = {}) => {
      setBusy(true);
      setError(null);
      return fetchJSON(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
        .then((payload) => {
          if (options.removeId) removeItem(options.removeId);
          else upsertItem(payload.item);
        })
        .catch((e) => setError(readError(e)))
        .finally(() => setBusy(false));
    },
    [removeItem, upsertItem]
  );

  const deleteTodo = useCallback((id) => postAction("/api/plugins/todo/delete", { id }, { removeId: id }), [postAction]);
  const cancelTodo = useCallback((id, comment) => postAction(`/api/plugins/todo/cancel/${id}`, { progress_note: comment }), [postAction]);
  const rejectTodo = useCallback((id, comment) => postAction(`/api/plugins/todo/reject/${id}`, { progress_note: comment }), [postAction]);
  const acceptTodo = useCallback((id, comment) => postAction(`/api/plugins/todo/accept/${id}`, { progress_note: comment }), [postAction]);

  const items = data?.items ?? [];
  const grouped = Object.fromEntries(STATUS_ORDER.map((status) => [status, items.filter((item) => item.status === status)]));

  return (
    <div style={{ padding: "1.5rem", maxWidth: "980px" }}>
      <div style={{ display: "flex", gap: "1rem", alignItems: "center", marginBottom: "1rem" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "bold", flex: 1 }}>Local TODO</h2>
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

      {STATUS_ORDER.map((status) => (
        <TodoColumn
          key={status}
          status={status}
          items={grouped[status] || []}
          updateTodo={updateTodo}
          deleteTodo={deleteTodo}
          cancelTodo={cancelTodo}
          rejectTodo={rejectTodo}
          acceptTodo={acceptTodo}
          progressNotes={progressNotes}
          setProgressNotes={setProgressNotes}
          disabled={busy}
        />
      ))}
    </div>
  );
}

function TodoColumn({ status, items, updateTodo, deleteTodo, cancelTodo, rejectTodo, acceptTodo, progressNotes, setProgressNotes, disabled }) {
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
            <TodoItem
              key={item.id}
              item={item}
              updateTodo={updateTodo}
              deleteTodo={deleteTodo}
              cancelTodo={cancelTodo}
              rejectTodo={rejectTodo}
              acceptTodo={acceptTodo}
              progressNotes={progressNotes}
              setProgressNotes={setProgressNotes}
              disabled={disabled}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}

function TodoItem({ item, updateTodo, deleteTodo, cancelTodo, rejectTodo, acceptTodo, progressNotes, setProgressNotes, disabled }) {
  const note = progressNotes[item.id] || "";
  const clearNote = () => setProgressNotes((notes) => ({ ...notes, [item.id]: "" }));
  const canCancel = item.status !== "cancelled" && item.status !== "accepted";
  const canDelete = item.status === "cancelled" || item.status === "accepted";

  return (
    <div style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", padding: "0.75rem 0" }}>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <Badge>{item.id}</Badge>
        <Badge>{STATUS_LABELS[item.status] || item.status}</Badge>
        <strong style={{ flex: 1 }}>{item.title}</strong>
        {canCancel && <Button size="sm" variant="outline" onClick={() => cancelTodo(item.id, note || "Cancelled by user")} disabled={disabled}>Cancel</Button>}
        {item.status === "done" && <Button size="sm" variant="outline" onClick={() => rejectTodo(item.id, note || "Rejected by user")} disabled={disabled}>Reject</Button>}
        {item.status === "done" && <Button size="sm" variant="outline" onClick={() => acceptTodo(item.id, note || "Accepted by user")} disabled={disabled}>Accept</Button>}
        {canDelete && <Button size="sm" variant="outline" onClick={() => deleteTodo(item.id)} disabled={disabled}>Delete</Button>}
      </div>
      {item.notes && <p style={{ margin: "0.5rem 0", opacity: 0.75 }}>{item.notes}</p>}
      {(item.progress || []).length > 0 && (
        <ul style={{ margin: "0.5rem 0", paddingLeft: "1.25rem", fontSize: "0.875rem", opacity: 0.75 }}>
          {item.progress.map((entry, idx) => <li key={`${item.id}-${idx}`}>{entry.at}: {entry.note}</li>)}
        </ul>
      )}
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
        <Input
          value={note}
          placeholder="Progress note"
          onChange={(e) => setProgressNotes((notes) => ({ ...notes, [item.id]: e.target.value }))}
        />
        <Button
          size="sm"
          disabled={disabled || !note.trim()}
          onClick={() => {
            updateTodo(item.id, { progress_note: note });
            clearNote();
          }}
        >Add note</Button>
      </div>
    </div>
  );
}

function readError(error) {
  if (error && typeof error === "object" && error.message) return error.message;
  return String(error || "Unknown error");
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
