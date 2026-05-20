CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #1c2028;
  --sidebar-bg: #16191f;
  --card-bg: #252b35;
  --border: #2e3444;
  --text: #d0d4dc;
  --muted: #6e7687;
  --accent: #f5a623;
  --accent-dim: rgba(245,166,35,0.1);
  --green: #4caf82;
  --input-bg: #1a1f2a;
  --input-border: #333b4d;
  --sidebar-w: 218px;
  --topbar-h: 54px;
}
body {
  background: var(--bg);
  color: var(--text);
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 14px;
  line-height: 1.5;
}
/* Sidebar */
.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: var(--sidebar-w);
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  z-index: 200;
  display: flex;
  flex-direction: column;
}
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
  text-decoration: none;
}
.brand-icon {
  width: 30px; height: 30px;
  background: var(--accent);
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 900; color: #16191f;
  flex-shrink: 0;
}
.brand-name { font-size: 14px; font-weight: 700; color: var(--text); letter-spacing: -0.2px; line-height: 1.2; }
.brand-sub { font-size: 11px; color: var(--muted); font-weight: 400; }
.nav-group { padding: 10px 0 4px; }
.nav-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 18px;
  color: #9aa0b0;
  text-decoration: none;
  font-size: 14px;
  border-left: 3px solid transparent;
  transition: color 0.12s, background 0.12s;
}
.nav-item:hover { color: var(--text); background: rgba(255,255,255,0.03); }
.nav-item.active { border-left-color: var(--accent); color: var(--accent); background: var(--accent-dim); font-weight: 600; }
/* Topbar */
.topbar {
  position: fixed;
  top: 0; left: var(--sidebar-w); right: 0;
  height: var(--topbar-h);
  background: var(--sidebar-bg);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 10px;
  z-index: 100;
}
.topbar-title { font-size: 16px; font-weight: 600; color: var(--text); flex: 1; }
.topbar-sub { font-size: 12px; color: var(--muted); font-weight: 400; margin-left: 8px; }
/* Main */
.main { margin-left: var(--sidebar-w); margin-top: var(--topbar-h); padding: 24px 28px 48px; }
.main.constrained { max-width: 980px; }
/* Notice */
.notice {
  background: rgba(245,166,35,0.08);
  border: 1px solid rgba(245,166,35,0.25);
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 18px;
  color: var(--text);
  font-size: 14px;
}
/* Cards */
.card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 14px; scroll-margin-top: calc(var(--topbar-h) + 18px); }
.card-header { padding: 14px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
.card-title { font-size: 15px; font-weight: 600; }
.card-desc { font-size: 12px; color: var(--muted); margin-top: 2px; }
.card-body { padding: 20px; }
.settings-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin: 0 0 16px;
  padding: 8px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.settings-tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 7px 12px;
  color: var(--muted);
  text-decoration: none;
  border: 1px solid transparent;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
}
.settings-tab:hover {
  color: var(--text);
  background: rgba(255,255,255,0.06);
  border-color: rgba(255,255,255,0.05);
}
.settings-tab.active {
  color: #16191f;
  background: var(--accent);
  border-color: var(--accent);
}
/* Form */
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 20px; }
.row.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 13px; font-weight: 500; color: var(--muted); }
input, select, textarea {
  width: 100%;
  background: var(--input-bg);
  border: 1px solid var(--input-border);
  border-radius: 5px;
  color: var(--text);
  padding: 8px 11px;
  font: inherit;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
  -webkit-appearance: none;
}
input:focus, select:focus, textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(245,166,35,0.12); }
input[readonly] { opacity: 0.55; cursor: default; }
select { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%236e7687' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px; }
textarea { min-height: 160px; resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; line-height: 1.6; }
.sep { margin: 18px 0; border: none; border-top: 1px solid var(--border); }
.checks { display: flex; gap: 20px; flex-wrap: wrap; }
.check-item { display: flex; align-items: center; gap: 7px; font-size: 14px; color: var(--text); cursor: pointer; }
.check-item input[type=checkbox] { width: 15px; height: 15px; accent-color: var(--accent); cursor: pointer; }
/* Buttons */
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 5px; font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; border: none; transition: opacity 0.12s, transform 0.08s; }
.btn:active { transform: scale(0.97); }
.btn-primary { background: var(--accent); color: #16191f; }
.btn-primary:hover { opacity: 0.88; }
.btn-ghost { background: rgba(255,255,255,0.06); color: var(--text); border: 1px solid var(--border); }
.btn-ghost:hover { background: rgba(255,255,255,0.1); }
.btn-danger { background: rgba(224,108,117,0.12); color: #e06c75; border: 1px solid rgba(224,108,117,0.35); }
.btn-danger:hover { background: rgba(224,108,117,0.18); }
.btn-small { padding: 5px 9px; font-size: 12px; }
.actions { display: flex; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
.task-actions { display: flex; gap: 6px; flex-wrap: wrap; margin: 0; }
/* Table */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 9px 10px; text-align: left; border-bottom: 1px solid var(--border); vertical-align: top; overflow-wrap: anywhere; }
th { color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
tr:last-child td { border-bottom: none; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; background: rgba(255,255,255,0.07); color: var(--muted); }
.badge.running { background: rgba(76,175,130,0.15); color: var(--green); }
.badge.error { background: rgba(224,108,117,0.15); color: #e06c75; }
.badge.completed { background: rgba(245,166,35,0.12); color: var(--accent); }
/* Pipeline */
.pipeline { display: inline-flex; align-items: center; gap: 0; flex-wrap: nowrap; }
.ps { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 3px; white-space: nowrap; letter-spacing: 0.02em; }
.ps-sep { color: var(--border); font-size: 13px; padding: 0 2px; }
.ps-done    { background: rgba(76,175,130,0.15); color: var(--green); }
.ps-active  { background: rgba(245,166,35,0.2); color: var(--accent); box-shadow: 0 0 0 1px rgba(245,166,35,0.35); }
.ps-pending { background: transparent; color: #444c5e; border: 1px solid #2e3444; }
.ps-error   { background: rgba(224,108,117,0.15); color: #e06c75; box-shadow: 0 0 0 1px rgba(224,108,117,0.3); }
/* Pipeline detail (collapsible) */
.pipe-detail { margin-top: 8px; }
.pipe-detail summary { font-size: 12px; color: var(--muted); cursor: pointer; user-select: none; list-style: none; display: inline-flex; align-items: center; gap: 4px; }
.pipe-detail summary::-webkit-details-marker { display: none; }
.pipe-detail summary::before { content: '›'; display: inline-block; transition: transform 0.15s; }
details[open] .pipe-detail summary::before { transform: rotate(90deg); }
.pipe-steps { margin-top: 8px; display: flex; flex-direction: column; gap: 5px; padding: 10px 12px; background: rgba(0,0,0,0.2); border-radius: 6px; border: 1px solid var(--border); }
.pipe-step { display: flex; align-items: flex-start; gap: 8px; font-size: 12px; }
.pipe-step-icon { width: 16px; text-align: center; flex-shrink: 0; margin-top: 1px; }
.pipe-step-name { color: var(--muted); font-weight: 600; width: 70px; flex-shrink: 0; }
.pipe-step-msg  { color: var(--text); flex: 1; word-break: break-word; }
.pipe-step-msg.err { color: #e06c75; }
.pipe-step-msg.ok  { color: var(--green); }
/* Progress bar */
.pbar { position: relative; width: 200px; height: 18px; background: rgba(255,255,255,0.06); border-radius: 9px; overflow: hidden; flex-shrink: 0; }
.pbar-fill { position: absolute; left: 0; top: 0; height: 100%; background: var(--green); transition: width 0.4s ease; border-radius: 9px; }
.pbar-fill.done { background: var(--accent); }
.pbar-fill.fail { background: #e06c75; }
.pbar-fill.pulse { background: linear-gradient(90deg,var(--green) 0%,rgba(76,175,130,0.5) 50%,var(--green) 100%); background-size: 200% 100%; animation: pulse-slide 1.5s linear infinite; }
@keyframes pulse-slide { 0%{background-position:100% 0} 100%{background-position:-100% 0} }
.pbar-txt { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: var(--text); letter-spacing: 0.04em; }
/* Status dot */
.sdot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--muted); flex-shrink: 0; }
.sdot.ok  { background: var(--green); }
.sdot.err { background: #e06c75; }
.sdot.pending { background: var(--accent); }
/* JDownloader-style dashboard */
.main.dashboard { padding: 10px 14px 14px; }
.jd-wrap {
  display: flex; flex-direction: column;
  height: calc(100vh - var(--topbar-h) - 36px);
  border: 1px solid var(--border); border-radius: 8px;
  overflow: hidden; background: var(--card-bg);
}
.jd-toolbar {
  display: flex; align-items: center; gap: 2px;
  padding: 5px 8px; background: var(--sidebar-bg);
  border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.jd-tb-btn {
  height: 24px; padding: 0 8px;
  border: 1px solid var(--border); border-radius: 3px;
  background: var(--card-bg); cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 12px; font-family: inherit; font-weight: 500;
  color: var(--text); text-decoration: none; flex-shrink: 0; gap: 4px;
}
.jd-tb-btn:hover { background: rgba(255,255,255,0.08); border-color: var(--accent); }
.jd-tb-btn:disabled { opacity: 0.35; cursor: default; }
.jd-tb-sep { width: 1px; height: 16px; background: var(--border); margin: 0 4px; flex-shrink: 0; }
.jd-tabbar {
  display: flex; background: var(--sidebar-bg);
  border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.jd-tab {
  padding: 7px 18px; cursor: pointer;
  font-size: 12px; font-weight: 600;
  border-right: 1px solid var(--border);
  display: flex; align-items: center; gap: 6px;
  user-select: none; white-space: nowrap; color: var(--muted);
  transition: color 0.12s, background 0.12s;
}
.jd-tab:hover { background: rgba(255,255,255,0.03); color: var(--text); }
.jd-tab.active {
  background: var(--card-bg); color: var(--text);
  border-bottom: 2px solid var(--accent); margin-bottom: -1px;
}
.jd-tab .jd-badge {
  background: rgba(255,255,255,0.08); color: var(--muted);
  font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 8px;
}
.jd-tab.active .jd-badge { background: var(--accent-dim); color: var(--accent); }
.jd-pane { flex: 1; overflow: auto; }
.jd-pane .jd-empty {
  color: var(--muted); font-size: 13px;
  padding: 32px 20px; text-align: center;
}
.jd-statusbar {
  background: var(--sidebar-bg); border-top: 1px solid var(--border);
  padding: 4px 14px; font-size: 11px; color: var(--muted);
  display: flex; gap: 0; flex-wrap: wrap; flex-shrink: 0; align-items: center;
}
.jd-sb-row { display: flex; gap: 18px; flex-wrap: wrap; padding: 2px 0; }
.jd-sb-row + .jd-sb-row { border-top: 1px solid var(--border); margin-top: 2px; }
.jd-stat { display: flex; gap: 4px; align-items: center; white-space: nowrap; }
.jd-stat-val { color: var(--text); font-weight: 600; }
/* JD table */
.jd-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.jd-table th {
  background: var(--sidebar-bg); padding: 5px 10px; text-align: left;
  font-size: 10px; font-weight: 600; border-bottom: 1px solid var(--border);
  color: var(--muted); white-space: nowrap;
  position: sticky; top: 0; z-index: 1;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.jd-table td {
  padding: 5px 10px; border-bottom: 1px solid var(--border); vertical-align: middle;
}
.jd-table tr:hover td { background: rgba(255,255,255,0.02); }
.jd-table tr:last-child td { border-bottom: none; }
/* Tree view — package rows and child rows */
.jd-pkg-row { cursor: pointer; user-select: none; }
.jd-pkg-row td { background: rgba(255,255,255,0.015); }
.jd-pkg-row:hover td { background: rgba(255,255,255,0.045); }
.jd-tree-arr { display: inline-block; width: 12px; text-align: center; cursor: pointer; }
.jd-child-r td { background: rgba(0,0,0,0.18); }
.jd-child-r:hover td { background: rgba(0,0,0,0.25); }
/* Responsive */
@media (max-width: 768px) {
  .sidebar { display: none; }
  .topbar, .main { margin-left: 0; }
  .row, .row.cols-3 { grid-template-columns: 1fr; }
  .jd-wrap { height: calc(100vh - var(--topbar-h) - 24px); border-radius: 0; border-left: none; border-right: none; }
}
"""
