/**
 * Pairing management plugin for the Hermes dashboard.
 *
 * Pure JavaScript — no build step needed. Uses window.__HERMES_PLUGIN_SDK__
 * which the dashboard already exposes (React + shadcn/ui components + fetch
 * helper). This file is served as a static asset to the browser.
 *
 * Backend: api.py (Python/FastAPI), mounted at /api/plugins/pairing/
 *   GET  /list    → { pending: [...], approved: [...] }
 *   POST /approve → { platform, code }
 *   POST /revoke  → { platform, user_id }
 */
(function () {
  var sdk = window.__HERMES_PLUGIN_SDK__;
  var React = sdk.React;
  var useState = sdk.hooks.useState;
  var useEffect = sdk.hooks.useEffect;
  var useCallback = sdk.hooks.useCallback;
  var fetchJSON = sdk.fetchJSON;
  var Button = sdk.components.Button;
  var Badge = sdk.components.Badge;
  var Card = sdk.components.Card;
  var CardHeader = sdk.components.CardHeader;
  var CardTitle = sdk.components.CardTitle;
  var CardContent = sdk.components.CardContent;
  var h = React.createElement;

  function PairingPage() {
    var s1 = useState({ pending: [], approved: [] });
    var data = s1[0]; var setData = s1[1];
    var s2 = useState(true);
    var loading = s2[0]; var setLoading = s2[1];
    var s3 = useState(null);
    var error = s3[0]; var setError = s3[1];
    var s4 = useState({});
    var busy = s4[0]; var setBusy = s4[1];

    var load = useCallback(function () {
      setLoading(true);
      setError(null);
      fetchJSON('/api/plugins/pairing/list')
        .then(function (d) { setData(d); })
        .catch(function (e) { setError(String(e)); })
        .finally(function () { setLoading(false); });
    }, []);

    useEffect(function () {
      load();
      var timer = setInterval(load, 15000);
      return function () { clearInterval(timer); };
    }, [load]);

    var approve = useCallback(function (platform, code) {
      var key = platform + ':' + code;
      setBusy(function (b) { var n = Object.assign({}, b); n[key] = true; return n; });
      fetchJSON('/api/plugins/pairing/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: platform, code: code }),
      })
        .then(function (r) {
          if (!r.ok) { setError(r.error || 'Failed to approve'); }
          else { load(); }
        })
        .catch(function (e) { setError(String(e)); })
        .finally(function () { setBusy(function (b) { var n = Object.assign({}, b); n[key] = false; return n; }); });
    }, [load]);

    var revoke = useCallback(function (platform, userId) {
      var key = platform + ':' + userId;
      setBusy(function (b) { var n = Object.assign({}, b); n[key] = true; return n; });
      fetchJSON('/api/plugins/pairing/revoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: platform, user_id: userId }),
      })
        .then(function () { load(); })
        .catch(function (e) { setError(String(e)); })
        .finally(function () { setBusy(function (b) { var n = Object.assign({}, b); n[key] = false; return n; }); });
    }, [load]);

    var pending = (data && data.pending) || [];
    var approved = (data && data.approved) || [];

    var cellStyle = { padding: '0.5rem 1rem 0.5rem 0' };
    var lastCellStyle = { padding: '0.5rem 0' };
    var headerStyle = Object.assign({}, cellStyle, { opacity: 0.6 });
    var lastHeaderStyle = Object.assign({}, lastCellStyle, { opacity: 0.6 });
    var rowStyle = { borderBottom: '1px solid rgba(255,255,255,0.08)' };
    var headRowStyle = { borderBottom: '1px solid rgba(255,255,255,0.15)', textAlign: 'left' };

    return h('div', { style: { padding: '1.5rem', maxWidth: '900px' } },
      h('div', { style: { display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' } },
        h('h2', { style: { fontSize: '1.25rem', fontWeight: 'bold', flex: 1 } }, 'Pairing Management'),
        h(Button, { onClick: load, disabled: loading, size: 'sm' }, loading ? 'Loading\u2026' : 'Refresh')
      ),

      error && h('div', {
        style: {
          padding: '0.75rem', marginBottom: '1rem', borderRadius: '0.375rem',
          fontSize: '0.875rem', color: '#f87171', background: 'rgba(239,68,68,0.1)',
        },
      }, error),

      h(Card, null,
        h(CardHeader, null,
          h(CardTitle, null, 'Pending Requests (' + pending.length + ')')
        ),
        h(CardContent, null,
          pending.length === 0
            ? h('p', { style: { fontSize: '0.875rem', opacity: 0.6 } },
                loading ? 'Loading\u2026' : 'No pending pairing requests.')
            : h('div', { style: { overflowX: 'auto' } },
                h('table', { style: { width: '100%', fontSize: '0.875rem', borderCollapse: 'collapse' } },
                  h('thead', null,
                    h('tr', { style: headRowStyle },
                      h('th', { style: headerStyle }, 'Platform'),
                      h('th', { style: headerStyle }, 'User'),
                      h('th', { style: headerStyle }, 'Code'),
                      h('th', { style: headerStyle }, 'Age'),
                      h('th', { style: lastHeaderStyle }, '')
                    )
                  ),
                  h('tbody', null,
                    pending.map(function (p) {
                      var key = p.platform + ':' + p.code;
                      return h('tr', { key: key, style: rowStyle },
                        h('td', { style: cellStyle }, h(Badge, null, p.platform)),
                        h('td', { style: cellStyle }, p.user_name || p.user_id),
                        h('td', { style: Object.assign({}, cellStyle, { fontFamily: 'monospace', letterSpacing: '0.1em' }) }, p.code),
                        h('td', { style: Object.assign({}, cellStyle, { opacity: 0.6 }) }, p.age_minutes + 'm ago'),
                        h('td', { style: lastCellStyle },
                          h(Button, {
                            size: 'sm',
                            disabled: !!busy[key],
                            onClick: (function (pf, c) {
                              return function () { approve(pf, c); };
                            }(p.platform, p.code)),
                          }, busy[key] ? '\u2026' : 'Approve')
                        )
                      );
                    })
                  )
                )
              )
        )
      ),

      h('div', { style: { height: '1.5rem' } }),

      h(Card, null,
        h(CardHeader, null,
          h(CardTitle, null, 'Approved Users (' + approved.length + ')')
        ),
        h(CardContent, null,
          approved.length === 0
            ? h('p', { style: { fontSize: '0.875rem', opacity: 0.6 } },
                loading ? 'Loading\u2026' : 'No approved users yet.')
            : h('div', { style: { overflowX: 'auto' } },
                h('table', { style: { width: '100%', fontSize: '0.875rem', borderCollapse: 'collapse' } },
                  h('thead', null,
                    h('tr', { style: headRowStyle },
                      h('th', { style: headerStyle }, 'Platform'),
                      h('th', { style: headerStyle }, 'User'),
                      h('th', { style: lastHeaderStyle }, '')
                    )
                  ),
                  h('tbody', null,
                    approved.map(function (a) {
                      var key = a.platform + ':' + a.user_id;
                      var display = a.user_name
                        ? (a.user_name + ' (' + a.user_id + ')')
                        : a.user_id;
                      return h('tr', { key: key, style: rowStyle },
                        h('td', { style: cellStyle }, h(Badge, null, a.platform)),
                        h('td', { style: cellStyle }, display),
                        h('td', { style: lastCellStyle },
                          h(Button, {
                            size: 'sm',
                            variant: 'outline',
                            disabled: !!busy[key],
                            onClick: (function (pf, uid) {
                              return function () { revoke(pf, uid); };
                            }(a.platform, a.user_id)),
                          }, busy[key] ? '\u2026' : 'Revoke')
                        )
                      );
                    })
                  )
                )
              )
        )
      )
    );
  }

  window.__HERMES_PLUGINS__.register('pairing', PairingPage);
}());
