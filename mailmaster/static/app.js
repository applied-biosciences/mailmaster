const $ = (s) => document.querySelector(s);
const state = { data: null, info: null, active: "Priority", selected: new Set(), pending: null };
const ACC_COLORS = ["#2453d4", "#d93025", "#1a8a5a", "#7a4fd0", "#d4781c", "#1f8fa8", "#b0307a"];
const IMAP_HELP = {
  gmail: 'Gmail needs an <b>app password</b> (2-Step Verification must be on). Create one at <a href="https://myaccount.google.com/apppasswords" target="_blank">myaccount.google.com/apppasswords</a>.',
  icloud: 'iCloud needs an <b>app-specific password</b>. Create one at <a href="https://account.apple.com" target="_blank">account.apple.com</a> → Sign-In and Security → App-Specific Passwords.',
  yahoo: 'Yahoo needs an <b>app password</b>. Create one in Yahoo Account Security → Generate app password.',
  other: "Enter your provider's IMAP and SMTP settings (your email host's help page lists them).",
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cssVar = (c) => `var(--${c.replace(/\s/g, "")})`;

// In-app confirm dialog (works in the desktop window, unlike browser pop-ups)
function askConfirm(message, okLabel = "Continue", danger = false) {
  return new Promise((resolve) => {
    $("#cText").textContent = message;
    $("#cOk").textContent = okLabel;
    $("#cOk").className = danger ? "danger" : "primary";
    $("#confirmModal").classList.remove("hidden");
    const done = (v) => { $("#confirmModal").classList.add("hidden"); $("#cOk").onclick = $("#cCancel").onclick = null; resolve(v); };
    $("#cOk").onclick = () => done(true);
    $("#cCancel").onclick = () => done(false);
  });
}

// Web links open in the person's normal browser (via the local server, so it works in the app window too)
async function openExternal(url) {
  try { await api("/api/open-url", { method: "POST", body: JSON.stringify({ url }) }); }
  catch (e) { window.open(url, "_blank", "noopener"); }
}
document.addEventListener("click", (e) => {
  const a = e.target.closest('a[target="_blank"]');
  if (a && /^https?:/i.test(a.href)) { e.preventDefault(); e.stopPropagation(); openExternal(a.href); }
}, true);

// ---------- clipboard (paste works in the app window and in a browser) ----------
const inAppWindow = () => !!(window.pywebview && window.pywebview.api);
const isMac = /Mac/i.test(navigator.platform || navigator.userAgent);

async function readClipboard() {
  if (inAppWindow() && window.pywebview.api.read_clipboard) return (await window.pywebview.api.read_clipboard()) || "";
  try { return await navigator.clipboard.readText(); }
  catch (e) { toast("Your browser blocked reading the clipboard. Click the field and press " + (isMac ? "Cmd" : "Ctrl") + "+V."); return ""; }
}
async function writeClipboard(text) {
  if (inAppWindow() && window.pywebview.api.write_clipboard) return window.pywebview.api.write_clipboard(text);
  try { await navigator.clipboard.writeText(text); } catch (e) { /* ignore */ }
}
function insertText(el, text) {
  let s = el.value.length, e = el.value.length;
  try { if (el.selectionStart != null) { s = el.selectionStart; e = el.selectionEnd; } } catch (_) { /* email/number inputs */ }
  el.value = el.value.slice(0, s) + text + el.value.slice(e);
  try { el.setSelectionRange(s + text.length, s + text.length); } catch (_) { /* not supported for this input type */ }
  el.dispatchEvent(new Event("input", { bubbles: true }));
}
// In the Mac app window, handle Cmd+V / C / X / A in text boxes ourselves so they always work.
document.addEventListener("keydown", async (e) => {
  if (!inAppWindow() || !isMac || !e.metaKey || e.ctrlKey || e.altKey) return;
  const el = document.activeElement;
  if (!el || !/^(INPUT|TEXTAREA)$/.test(el.tagName)) return;
  const k = e.key.toLowerCase();
  if (!["v", "c", "x", "a"].includes(k)) return;
  e.preventDefault();
  if (k === "a") { el.select(); return; }
  if (k === "v") { insertText(el, (await readClipboard()).replace(/\r?\n$/, "")); return; }
  let sel = "";
  try { sel = el.value.slice(el.selectionStart, el.selectionEnd); } catch (_) { sel = el.value; }
  if (el.type === "password") return;  // never copy passwords out
  await writeClipboard(sel);
  if (k === "x" && sel) insertText(el, "");
}, true);

// "Paste all settings": fills whatever it recognises from copied account details
function parseSettings(text) {
  const out = {}, lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const setHost = (key, v) => { const m = v.match(/^([^\s:/]+)(?::(\d+))?/); if (m) { out[key + "_host"] = m[1]; if (m[2]) out[key + "_port"] = m[2]; } };
  for (const line of lines) {
    const m = line.match(/^([^:=\t]{2,40})\s*[:=\t]\s*(.+)$/);
    if (!m) continue;
    const k = m[1].toLowerCase(), v = m[2].trim();
    if (/imap/.test(k) && /port/.test(k)) out.imap_port = v.replace(/\D/g, "");
    else if (/smtp|outgoing/.test(k) && /port/.test(k)) out.smtp_port = v.replace(/\D/g, "");
    else if (/imap|incoming/.test(k)) setHost("imap", v);
    else if (/smtp|outgoing/.test(k)) setHost("smtp", v);
    else if (/pass(word|code)?|app.?pass/.test(k)) out.password = v;
    else if (/user|login/.test(k)) out.username = v;
    else if (/e-?mail|address|account/.test(k)) out.email = v;
  }
  const email = text.match(/[\w.+-]+@[\w-]+(\.[\w-]+)+/);
  if (!out.email && email) out.email = email[0];
  if (!out.imap_host) { const h = text.match(/\bimap(\.[\w-]+)+/i); if (h) out.imap_host = h[0]; }
  if (!out.smtp_host) { const h = text.match(/\bsmtp(\.[\w-]+)+/i); if (h) out.smtp_host = h[0]; }
  return out;
}

function toast(msg, ms = 4000) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), ms);
}

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", "X-MailMaster": "1", ...(opts.headers || {}) } });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso), now = new Date();
  return d.toDateString() === now.toDateString()
    ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString([], { day: "numeric", month: "short" });
}

// ---------- accounts ----------
function accColor(id) {
  const i = (state.data?.accounts || []).findIndex((a) => a.id === id);
  return ACC_COLORS[(i < 0 ? 0 : i) % ACC_COLORS.length];
}
function accLabel(id) {
  const a = (state.data?.accounts || []).find((x) => x.id === id);
  return a ? a.email : "";
}
function accShort(id) {
  const a = (state.data?.accounts || []).find((x) => x.id === id);
  return a ? `${a.name}` : "";
}

async function loadAccounts() {
  state.info = await api("/api/accounts");
  const { accounts, msConfigured, demo } = state.info;
  $("#accList").innerHTML = accounts.length ? accounts.map((a, i) => `
    <div class="acc-item">
      <span class="acct" style="--ac:${ACC_COLORS[i % ACC_COLORS.length]}">${esc(a.name)}</span>
      <div class="grow">${esc(a.email)}<small>${a.type === "microsoft" ? "Microsoft sign-in" : "IMAP · " + esc(a.imap_host || "")}${state.data?.errors?.[a.id] ? " · ⚠ " + esc(state.data.errors[a.id]) : ""}</small></div>
      ${demo ? "" : `<button class="small" data-remove="${esc(a.id)}">Remove</button>`}
    </div>`).join("") : `<p class="hint">No accounts yet. Add one below.</p>`;
  $("#msHint").classList.toggle("hidden", msConfigured || demo);
  $("#addMs").classList.toggle("disabled", !msConfigured && !demo);
  return accounts;
}

function openAccounts() { loadAccounts(); $("#accModal").classList.remove("hidden"); }

function showImapForm(p) {
  const preset = state.info.presets[p];
  const f = $("#imapForm");
  f.reset();
  f.provider.value = p;
  $("#imapTitle").textContent = p === "other" ? "Other IMAP account" : preset.label;
  $("#imapHelp").innerHTML = IMAP_HELP[p];
  $("#advanced").open = p === "other";
  f.imap_host.value = preset.imap_host || ""; f.smtp_host.value = preset.smtp_host || "";
  f.imap_port.value = preset.imap_port; f.smtp_port.value = preset.smtp_port;
  $("#pwLabel").textContent = p === "other" ? "Password" : "App password";
  f.password.type = "password"; $("#pwShow").textContent = "Show";
  setHint("#pwSavedHint", "Looks in this computer's saved passwords. You'll be asked to approve.");
  f.classList.remove("hidden");
  f.email.focus();
}

function setHint(sel, text, cls = "") { const h = $(sel); h.textContent = text; h.className = "hint " + cls; }

async function pasteInto(name) {
  const f = $("#imapForm"), el = f[name];
  const text = (await readClipboard()).trim();
  if (!text) return;
  el.value = name === "password" ? text.replace(/\r?\n/g, "") : text.split(/\r?\n/)[0].trim();
  if (name === "email" && !f.username.value) f.username.placeholder = el.value;
  el.focus();
}

async function pasteAll() {
  const text = await readClipboard();
  if (!text.trim()) return toast("The clipboard is empty.");
  const found = parseSettings(text), f = $("#imapForm"), filled = [];
  for (const [k, v] of Object.entries(found)) if (f[k] && v) { f[k].value = v; filled.push(k.replace("_", " ")); }
  if (found.imap_host || found.smtp_host || found.username) $("#advanced").open = true;
  toast(filled.length ? `Filled in: ${filled.join(", ")}.` : "Couldn't recognise any account details in what you copied.", 5000);
}

async function useSavedPassword() {
  const f = $("#imapForm");
  if (!f.email.value) return setHint("#pwSavedHint", "Enter the email address first.", "bad");
  setHint("#pwSavedHint", "Looking… approve the request from your computer if it asks.");
  $("#pwSaved").disabled = true;
  try {
    const r = await api("/api/saved-password", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(f).entries())) });
    if (r.found) { f.password.value = r.password; setHint("#pwSavedHint", r.message, "ok"); }
    else setHint("#pwSavedHint", r.message, "bad");
  } catch (e) { setHint("#pwSavedHint", e.message, "bad"); }
  finally { $("#pwSaved").disabled = false; }
}

// ---------- Microsoft sign-in in the normal browser (reuses existing Microsoft logins) ----------
let msPoll = null;
async function startMsLogin() {
  if (state.info?.demo) return toast("Adding accounts is off in demo mode. Set DEMO_MODE=0 in .env.");
  if (!state.info?.msConfigured) return toast("This copy of MailMaster has no Microsoft app ID. Use an official build from the Releases page.", 6000);
  const before = new Set((state.info.accounts || []).map((a) => a.id));
  try { await api("/api/ms-login/start", { method: "POST", body: "{}" }); }
  catch (e) { return toast("Couldn't start Microsoft sign-in: " + e.message, 6000); }
  $("#msWait").classList.remove("hidden");
  clearInterval(msPoll);
  const started = Date.now();
  msPoll = setInterval(async () => {
    if (Date.now() - started > 10 * 60 * 1000) return stopMsWait();
    try {
      const info = await api("/api/accounts");
      const added = info.accounts.find((a) => !before.has(a.id));
      if (added) { stopMsWait(); toast(`Connected ${added.email}`); await loadAccounts(); load(true); }
    } catch (_) { /* keep waiting */ }
  }, 2000);
}
function stopMsWait() { clearInterval(msPoll); msPoll = null; $("#msWait").classList.add("hidden"); }

// ---------- settings ----------
const limitLabel = (n) => (n === 0 ? "Max (all)" : n.toLocaleString());
async function openSettings() {
  const r = await api("/api/settings");
  const fill = (sel, val) => {
    const opts = [...new Set([...r.choices, val])].sort((a, b) => (a || 1e9) - (b || 1e9));
    $(sel).innerHTML = opts.map((n) => `<option value="${n}" ${n === val ? "selected" : ""}>${limitLabel(n)}</option>`).join("");
  };
  fill("#setInbox", r.settings.max_inbox); fill("#setJunk", r.settings.max_junk); fill("#setDeleted", r.settings.max_deleted);
  $("#setModal").classList.remove("hidden");
}
async function saveSettings() {
  const body = { max_inbox: +$("#setInbox").value, max_junk: +$("#setJunk").value, max_deleted: +$("#setDeleted").value };
  try { await api("/api/settings", { method: "POST", body: JSON.stringify(body) }); $("#setModal").classList.add("hidden"); load(true); }
  catch (e) { toast(e.message); }
}

async function saveImap(ev) {
  ev.preventDefault();
  const f = $("#imapForm");
  const body = Object.fromEntries(new FormData(f).entries());
  $("#imapSave").disabled = true; $("#imapSave").textContent = "Connecting…";
  try {
    await api("/api/accounts/imap", { method: "POST", body: JSON.stringify(body) });
    f.classList.add("hidden");
    toast(`Connected ${body.email}`);
    await loadAccounts();
    load(true);
  } catch (e) { toast(e.message, 7000); }
  finally { $("#imapSave").disabled = false; $("#imapSave").textContent = "Connect"; }
}

async function removeAccount(id) {
  if (!(await askConfirm(`Remove ${accLabel(id) || "this account"} from MailMaster? Your emails are not touched.`, "Remove", true))) return;
  try { await api(`/api/accounts/${encodeURIComponent(id)}`, { method: "DELETE" }); await loadAccounts(); load(true); }
  catch (e) { toast(e.message); }
}

// ---------- mail ----------
async function load(refresh = false) {
  $("#list").innerHTML = `<div class="empty">${refresh ? "Refreshing" : "Loading"} your mail…</div>`;
  try {
    state.data = await api(`/api/summary${refresh ? "?refresh=1" : ""}`);
    state.selected.clear();
    const f = $("#accountFilter"), cur = f.value;
    f.innerHTML = `<option value="">All accounts (${state.data.accounts.length})</option>` +
      state.data.accounts.map((a) => `<option value="${esc(a.id)}">${esc(a.email)}</option>`).join("");
    f.value = state.data.accounts.some((a) => a.id === cur) ? cur : "";
    const errs = Object.entries(state.data.errors || {});
    $("#errors").innerHTML = errs.map(([id, e]) => `<div class="banner">⚠ ${esc(accLabel(id))}: ${esc(e)}</div>`).join("");
    if (!state.data.accounts.length) {
      $("#list").innerHTML = `<div class="empty">No accounts connected yet.<br><br><button class="primary" id="emptyAdd">Add an account</button></div>`;
      $("#cards").innerHTML = "";
      $("#emptyAdd").onclick = openAccounts;
      openAccounts();
      return;
    }
    render();
  } catch (e) {
    $("#list").innerHTML = `<div class="empty">Could not load mail: ${esc(e.message)}</div>`;
  }
}

function scoped() {
  const acc = $("#accountFilter").value;
  return state.data.items.filter((m) => !acc || m.accountId === acc);
}

function currentItems() {
  const q = $("#search").value.trim().toLowerCase();
  let items = scoped().filter((m) => m.category === state.active);
  if (q) items = items.filter((m) => (m.fromName + " " + m.fromAddress + " " + m.subject).toLowerCase().includes(q));
  return items;
}

function badge(m) {
  return state.data.accounts.length > 1
    ? `<span class="acct" style="--ac:${accColor(m.accountId)}" title="${esc(accLabel(m.accountId))}">${esc(accShort(m.accountId))}</span>` : "";
}

function render() {
  const cats = state.data.categories, base = scoped();
  $("#cards").innerHTML = cats.map((c) => `
    <button class="card ${c === state.active ? "active" : ""}" style="--c:${cssVar(c)}" data-cat="${esc(c)}">
      <div class="n">${base.filter((m) => m.category === c).length}</div><div class="l">${esc(c)}</div>
    </button>`).join("");

  const inTrash = state.active === "Deleted Mail";
  $("#permWrap").classList.toggle("hidden", inTrash);
  const items = currentItems();
  const grouped = $("#groupBy").checked;

  if (!items.length) {
    $("#list").innerHTML = `<div class="empty">Nothing in ${esc(state.active)} 🎉</div>`;
  } else if (grouped) {
    const bySender = {};
    items.forEach((m) => (bySender[m.fromAddress] ||= []).push(m));
    $("#list").innerHTML = Object.values(bySender).sort((a, b) => b.length - a.length).map((ms) => {
      const m = ms[0], allSel = ms.every((x) => state.selected.has(x.id));
      const accs = [...new Set(ms.map((x) => x.accountId))];
      return `<div class="row group-head">
        <input type="checkbox" data-group="${esc(m.fromAddress)}" ${allSel ? "checked" : ""}>
        <div class="from">${esc(m.fromName)}<small>${esc(m.fromAddress)}</small></div>
        <div class="body"><div class="subj">${ms.length} email${ms.length > 1 ? "s" : ""} ${accs.map((a) => badge({ accountId: a })).join(" ")}</div><div class="prev">Latest: ${esc(m.subject)}</div></div>
        <div class="meta">
          ${ms.find((x) => x.unsubscribe) ? `<button class="small" data-unsub="${esc(ms.find((x) => x.unsubscribe).id)}">Unsubscribe</button>` : ""}
          <button class="small danger" data-delgroup="${esc(m.fromAddress)}">Delete all</button>
        </div></div>`;
    }).join("");
  } else {
    $("#list").innerHTML = items.map((m) => `
      <div class="row ${m.isRead ? "" : "unread"}">
        <input type="checkbox" data-id="${esc(m.id)}" ${state.selected.has(m.id) ? "checked" : ""}>
        <div class="from" title="${esc(m.fromAddress)}">${esc(m.fromName)}<small>${esc(m.fromAddress)}</small></div>
        <div class="body"><div class="subj">${esc(m.subject)}</div><div class="prev">${esc(m.preview)}</div>
          <div class="reason">${badge(m)} ${esc(m.reason)}</div></div>
        <div class="meta">
          ${m.unsubscribe ? `<button class="small" data-unsub="${esc(m.id)}">Unsubscribe</button>` : ""}
          ${m.webLink ? `<a class="btn small" href="${esc(m.webLink)}" target="_blank" rel="noopener">Open</a>` : ""}
          <button class="small" data-del="${esc(m.id)}" title="Delete">🗑</button>
          <span class="date">${fmtDate(m.received)}</span>
        </div></div>`).join("");
  }
  syncToolbar();
}

const selectedItems = () => currentItems().filter((m) => state.selected.has(m.id));
const unsubSenders = (items) => [...new Set(items.filter((m) => m.unsubscribe).map((m) => m.fromAddress))];

function syncToolbar() {
  const items = currentItems(), sel = selectedItems(), n = sel.length;
  const word = state.active === "Deleted Mail" ? "Delete forever" : "Delete";
  $("#deleteSel").disabled = n === 0;
  $("#deleteSel").textContent = n ? `${word} (${n})` : word;
  $("#selectAll").checked = items.length > 0 && n === items.length;
  // Bulk unsubscribe: shown wherever list emails are present (always in Mailing List)
  const canUnsub = items.some((m) => m.unsubscribe);
  const senders = unsubSenders(sel);
  $("#unsubSel").classList.toggle("hidden", !(canUnsub || state.active === "Mailing List"));
  $("#unsubSel").disabled = senders.length === 0;
  $("#unsubSel").textContent = senders.length ? `Unsubscribe (${senders.length} sender${senders.length > 1 ? "s" : ""})` : "Unsubscribe";
}

async function del(ids) {
  if (!ids.length) return;
  const fromTrash = ids.every((id) => findMsg(id)?.category === "Deleted Mail");
  const permanent = $("#permanent").checked || fromTrash;
  if (!(await askConfirm(`${ids.length} email${ids.length > 1 ? "s" : ""} will be ${permanent ? "permanently deleted. This can't be undone." : "moved to Deleted Mail."}`, permanent ? "Delete forever" : "Delete", true))) return;
  try {
    const r = await api("/api/delete", { method: "POST", body: JSON.stringify({ ids, permanent }) });
    applyChanges(r);
    toast(`Deleted ${r.deleted.length}.` + (r.errors.length ? ` Problems: ${r.errors.join("; ")}` : ""), r.errors.length ? 8000 : 3500);
  } catch (e) { toast("Delete failed: " + e.message); }
}

function removeLocal(ids) {
  const gone = new Set(ids);
  state.data.items = state.data.items.filter((m) => !gone.has(m.id));
  ids.forEach((i) => state.selected.delete(i));
  render();
}

// Applies a server response: removes deleted emails and swaps in the fresh Deleted Mail list per account.
function applyChanges(r) {
  const gone = new Set(r.deleted || []);
  const trash = r.trash || {};
  state.data.items = state.data.items.filter((m) => !gone.has(m.id) && !(m.category === "Deleted Mail" && trash[m.accountId]));
  Object.values(trash).forEach((list) => state.data.items.push(...list));
  state.data.items.sort((a, b) => (b.received || "").localeCompare(a.received || ""));
  gone.forEach((i) => state.selected.delete(i));
  render();
}

const findMsg = (id) => state.data.items.find((x) => x.id === id);
const fromSender = (addr) => state.data.items.filter((m) => m.fromAddress === addr);

function openUnsub(id) {
  const m = findMsg(id); if (!m) return;
  state.pending = id;
  $("#mWho").textContent = "this sender";
  const how = { "one-click": "instantly (one-click)", email: "by sending a short unsubscribe email from " + accLabel(m.accountId), link: "by opening the sender's unsubscribe page" }[m.unsubscribe];
  $("#mTitle").textContent = `Unsubscribe from ${m.fromName}?`;
  $("#mText").textContent = `MailMaster will unsubscribe you ${how}.`;
  $("#mCount").textContent = fromSender(m.fromAddress).length;
  $("#modal").classList.remove("hidden");
}

function openBulkUnsub() {
  const sel = selectedItems(), senders = unsubSenders(sel);
  if (!senders.length) return toast("None of the selected emails have an unsubscribe option.");
  state.pending = { bulk: sel.map((m) => m.id) };
  $("#mTitle").textContent = `Unsubscribe from ${senders.length} sender${senders.length > 1 ? "s" : ""}?`;
  $("#mText").textContent = "MailMaster will unsubscribe from each one (one-click or email where possible). Senders that need you to confirm on their website will be listed with a link.";
  $("#mCount").textContent = state.data.items.filter((m) => senders.includes(m.fromAddress) && m.category !== "Deleted Mail").length;
  $("#mWho").textContent = "these senders";
  $("#modal").classList.remove("hidden");
}

async function confirmBulkUnsub(ids) {
  $("#unsubSel").disabled = true; $("#unsubSel").textContent = "Unsubscribing…";
  try {
    const r = await api("/api/unsubscribe/bulk", { method: "POST", body: JSON.stringify({ ids, deleteAll: $("#mDeleteAll").checked, permanent: $("#permanent").checked }) });
    applyChanges(r);
    const ok = r.results.filter((x) => x.status === "done").length;
    const links = r.results.filter((x) => x.status === "open_link").length;
    const bad = r.results.filter((x) => x.status === "failed").length;
    $("#bTitle").textContent = `Unsubscribed: ${ok} done` + (links ? `, ${links} need your click` : "") + (bad ? `, ${bad} failed` : "");
    $("#bBody").innerHTML = r.results.map((x) => `
      <div class="acc-item"><div class="grow">${esc(x.name)}<small>${esc(x.sender)}</small></div>
        ${x.status === "done" ? `<span class="res-ok">✓ ${esc(x.message)}</span>`
        : x.status === "open_link" ? `<a class="btn small primary" href="${esc(x.url)}" target="_blank" rel="noopener">Confirm on their site</a>`
        : `<span class="res-bad">✗ ${esc(x.message)}</span>`}</div>`).join("") +
      (r.deleted?.length ? `<p class="hint">Deleted ${r.deleted.length} email(s) from these senders.</p>` : "") +
      (r.errors?.length ? `<p class="res-bad">${esc(r.errors.join("; "))}</p>` : "") +
      (links ? `<p class="hint">${links} sender(s) need one click on their page to finish.</p>` : "") +
      (bad ? `<p class="hint">Failed ones can be retried, or use their "unsubscribe" link inside the email.</p>` : "");
    $("#bulkModal").classList.remove("hidden");
  } catch (e) { toast("Unsubscribe failed: " + e.message); }
  finally { syncToolbar(); }
}

async function confirmUnsub() {
  $("#modal").classList.add("hidden");
  if (state.pending?.bulk) return confirmBulkUnsub(state.pending.bulk);
  const id = state.pending;
  const m = findMsg(id);
  try {
    const r = await api("/api/unsubscribe", { method: "POST", body: JSON.stringify({ id, deleteAll: $("#mDeleteAll").checked, permanent: $("#permanent").checked }) });
    if (r.status === "open_link" && r.url) openExternal(r.url);
    toast(r.message + (r.deleted?.length ? ` Deleted ${r.deleted.length} email(s).` : ""), 5000);
    applyChanges(r);
  } catch (e) { toast("Unsubscribe failed: " + e.message); }
}

// ---------- events ----------
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-cat],[data-del],[data-unsub],[data-delgroup],[data-remove],.addImap");
  if (!t) return;
  if (t.dataset.cat) { state.active = t.dataset.cat; state.selected.clear(); render(); }
  else if (t.dataset.del) del([t.dataset.del]);
  else if (t.dataset.unsub) openUnsub(t.dataset.unsub);
  else if (t.dataset.delgroup) del(currentItems().filter((m) => m.fromAddress === t.dataset.delgroup).map((m) => m.id));
  else if (t.dataset.remove) removeAccount(t.dataset.remove);
  else if (t.classList.contains("addImap")) {
    if (state.info?.demo) return toast("Adding accounts is off in demo mode. Set DEMO_MODE=0 in .env.");
    showImapForm(t.dataset.p);
  }
});
document.addEventListener("change", (e) => {
  const t = e.target;
  if (t.dataset.id) { t.checked ? state.selected.add(t.dataset.id) : state.selected.delete(t.dataset.id); syncToolbar(); }
  else if (t.dataset.group) { currentItems().filter((m) => m.fromAddress === t.dataset.group).forEach((m) => t.checked ? state.selected.add(m.id) : state.selected.delete(m.id)); syncToolbar(); }
});
$("#addMs").addEventListener("click", startMsLogin);
$("#msCancel").addEventListener("click", stopMsWait);
$("#pasteAll").addEventListener("click", pasteAll);
$("#pwSaved").addEventListener("click", useSavedPassword);
$("#pwShow").addEventListener("click", () => { const p = $("#imapForm").password; p.type = p.type === "password" ? "text" : "password"; $("#pwShow").textContent = p.type === "password" ? "Show" : "Hide"; });
document.addEventListener("click", (e) => { const b = e.target.closest("[data-paste]"); if (b) { e.preventDefault(); pasteInto(b.dataset.paste); } });
$("#openSettings").addEventListener("click", openSettings);
$("#setClose").addEventListener("click", () => $("#setModal").classList.add("hidden"));
$("#setCancel").addEventListener("click", () => $("#setModal").classList.add("hidden"));
$("#setSave").addEventListener("click", saveSettings);
$("#selectAll").addEventListener("change", (e) => { currentItems().forEach((m) => e.target.checked ? state.selected.add(m.id) : state.selected.delete(m.id)); render(); });
$("#search").addEventListener("input", render);
$("#groupBy").addEventListener("change", render);
$("#accountFilter").addEventListener("change", () => { state.selected.clear(); render(); });
$("#deleteSel").addEventListener("click", () => del(selectedItems().map((m) => m.id)));
$("#unsubSel").addEventListener("click", openBulkUnsub);
$("#bClose").addEventListener("click", () => $("#bulkModal").classList.add("hidden"));
$("#refresh").addEventListener("click", () => load(true));
$("#openAccounts").addEventListener("click", openAccounts);
$("#accClose").addEventListener("click", () => $("#accModal").classList.add("hidden"));
$("#imapCancel").addEventListener("click", () => $("#imapForm").classList.add("hidden"));
$("#imapForm").addEventListener("submit", saveImap);
$("#mCancel").addEventListener("click", () => $("#modal").classList.add("hidden"));
$("#mOk").addEventListener("click", confirmUnsub);

loadAccounts().then(() => load());
