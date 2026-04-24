/**
 * Pairing management plugin for the Hermes dashboard.
 *
 * Bundled as an IIFE by esbuild inside the Docker build — never committed as
 * a built artifact. Uses window.__HERMES_PLUGIN_SDK__ which the dashboard
 * exposes (React, shadcn/ui components, fetch helper).
 */

/* eslint-disable no-undef */
const {
  React,
  hooks: { useState, useEffect, useCallback },
  components: { Button, Badge, Card, CardHeader, CardTitle, CardContent },
  fetchJSON,
} = window.__HERMES_PLUGIN_SDK__;

function PairingPage() {
  const [data, setData] = useState({ pending: [], approved: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState({});

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchJSON("/api/plugins/pairing/list")
      .then((d) => setData(d))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, [load]);

  const approve = useCallback(
    (platform, code) => {
      const key = `${platform}:${code}`;
      setBusy((b) => ({ ...b, [key]: true }));
      fetchJSON("/api/plugins/pairing/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform, code }),
      })
        .then((r) => {
          if (!r.ok) setError(r.error || "Failed to approve");
          else load();
        })
        .catch((e) => setError(String(e)))
        .finally(() => setBusy((b) => ({ ...b, [key]: false })));
    },
    [load]
  );

  const revoke = useCallback(
    (platform, userId) => {
      const key = `${platform}:${userId}`;
      setBusy((b) => ({ ...b, [key]: true }));
      fetchJSON("/api/plugins/pairing/revoke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform, user_id: userId }),
      })
        .then(() => load())
        .catch((e) => setError(String(e)))
        .finally(() => setBusy((b) => ({ ...b, [key]: false })));
    },
    [load]
  );

  const pending = data?.pending ?? [];
  const approved = data?.approved ?? [];

  return (
    <div style={{ padding: "1.5rem", maxWidth: "900px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "1rem",
          marginBottom: "1.5rem",
        }}
      >
        <h2 style={{ fontSize: "1.25rem", fontWeight: "bold", flex: 1 }}>
          Pairing Management
        </h2>
        <Button onClick={load} disabled={loading} size="sm">
          {loading ? "Loading…" : "Refresh"}
        </Button>
      </div>

      {error && (
        <div
          style={{
            padding: "0.75rem",
            marginBottom: "1rem",
            borderRadius: "0.375rem",
            fontSize: "0.875rem",
            color: "#f87171",
            background: "rgba(239,68,68,0.1)",
          }}
        >
          {error}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Pending Requests ({pending.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {pending.length === 0 ? (
            <p style={{ fontSize: "0.875rem", opacity: 0.6 }}>
              {loading ? "Loading…" : "No pending pairing requests."}
            </p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table
                style={{
                  width: "100%",
                  fontSize: "0.875rem",
                  borderCollapse: "collapse",
                }}
              >
                <thead>
                  <tr
                    style={{
                      borderBottom: "1px solid rgba(255,255,255,0.15)",
                      textAlign: "left",
                    }}
                  >
                    <Th>Platform</Th>
                    <Th>User</Th>
                    <Th>Code</Th>
                    <Th>Age</Th>
                    <Th last />
                  </tr>
                </thead>
                <tbody>
                  {pending.map((p) => {
                    const key = `${p.platform}:${p.code}`;
                    return (
                      <tr
                        key={key}
                        style={{
                          borderBottom: "1px solid rgba(255,255,255,0.08)",
                        }}
                      >
                        <Td>
                          <Badge>{p.platform}</Badge>
                        </Td>
                        <Td>{p.user_name || p.user_id}</Td>
                        <Td mono>{p.code}</Td>
                        <Td muted>{p.age_minutes}m ago</Td>
                        <Td last>
                          <Button
                            size="sm"
                            disabled={!!busy[key]}
                            onClick={() => approve(p.platform, p.code)}
                          >
                            {busy[key] ? "…" : "Approve"}
                          </Button>
                        </Td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <div style={{ height: "1.5rem" }} />

      <Card>
        <CardHeader>
          <CardTitle>Approved Users ({approved.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {approved.length === 0 ? (
            <p style={{ fontSize: "0.875rem", opacity: 0.6 }}>
              {loading ? "Loading…" : "No approved users yet."}
            </p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table
                style={{
                  width: "100%",
                  fontSize: "0.875rem",
                  borderCollapse: "collapse",
                }}
              >
                <thead>
                  <tr
                    style={{
                      borderBottom: "1px solid rgba(255,255,255,0.15)",
                      textAlign: "left",
                    }}
                  >
                    <Th>Platform</Th>
                    <Th>User</Th>
                    <Th last />
                  </tr>
                </thead>
                <tbody>
                  {approved.map((a) => {
                    const key = `${a.platform}:${a.user_id}`;
                    const display = a.user_name
                      ? `${a.user_name} (${a.user_id})`
                      : a.user_id;
                    return (
                      <tr
                        key={key}
                        style={{
                          borderBottom: "1px solid rgba(255,255,255,0.08)",
                        }}
                      >
                        <Td>
                          <Badge>{a.platform}</Badge>
                        </Td>
                        <Td>{display}</Td>
                        <Td last>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={!!busy[key]}
                            onClick={() => revoke(a.platform, a.user_id)}
                          >
                            {busy[key] ? "…" : "Revoke"}
                          </Button>
                        </Td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Small table helpers to reduce repetition
function Th({ children, last }) {
  return (
    <th
      style={{
        padding: last ? "0.5rem 0" : "0.5rem 1rem 0.5rem 0",
        opacity: 0.6,
      }}
    >
      {children}
    </th>
  );
}

function Td({ children, last, mono, muted }) {
  return (
    <td
      style={{
        padding: last ? "0.5rem 0" : "0.5rem 1rem 0.5rem 0",
        ...(mono ? { fontFamily: "monospace", letterSpacing: "0.1em" } : {}),
        ...(muted ? { opacity: 0.6 } : {}),
      }}
    >
      {children}
    </td>
  );
}

window.__HERMES_PLUGINS__.register("pairing", PairingPage);
