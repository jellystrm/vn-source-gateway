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
.nav-group-label {
  padding: 4px 18px 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: var(--muted);
}
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
.nav-icon { width: 16px; text-align: center; opacity: 0.7; flex-shrink: 0; }
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
.main { margin-left: var(--sidebar-w); margin-top: var(--topbar-h); padding: 24px 28px 48px; max-width: 980px; }
/* Status pills */
.status-bar { display: flex; gap: 10px; margin-bottom: 22px; flex-wrap: wrap; }
.pill { display: flex; align-items: center; gap: 8px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px; padding: 7px 14px; font-size: 13px; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); flex-shrink: 0; }
.pill.ok .dot { background: var(--green); }
.pill-label { color: var(--muted); }
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
.actions { display: flex; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
/* Table */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 9px 10px; text-align: left; border-bottom: 1px solid var(--border); vertical-align: top; overflow-wrap: anywhere; }
th { color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
tr:last-child td { border-bottom: none; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; background: rgba(255,255,255,0.07); color: var(--muted); }
.badge.running { background: rgba(76,175,130,0.15); color: var(--green); }
.badge.error { background: rgba(224,108,117,0.15); color: #e06c75; }
.badge.completed { background: rgba(245,166,35,0.12); color: var(--accent); }
/* Responsive */
@media (max-width: 768px) {
  .sidebar { display: none; }
  .topbar, .main { margin-left: 0; }
  .row, .row.cols-3 { grid-template-columns: 1fr; }
}
"""
