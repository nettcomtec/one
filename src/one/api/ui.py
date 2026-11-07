"""Presentation layer — the Nettcom ONE visual system.

Design point of view: this ERP's one differentiator is an AI agent working
*inside* it. So the dashboard's boldest element is the agent — a dark, gold-lit
command strip — while everything around it stays quiet: clean white surfaces,
a single indigo accent, tabular figures. Headings in Bricolage Grotesque give
the product a voice; Inter carries the data. Gold is reserved for the agent and
appears nowhere else.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

# --------------------------------------------------------------------------- tokens + css
CSS = """
:root{
  --ink:#0D1B2A; --ink-line:#1C2E42; --ink-soft:#8595A8; --ink-soft-2:#5C6B80;
  --bg:#F5F6F8; --card:#FFFFFF; --line:#E9ECF1; --line-soft:#F1F3F6;
  --fg:#121826; --fg-2:#5A6578; --fg-3:#8A94A6;
  --acc:#3B5BDB; --acc-700:#2C46B8; --acc-50:#EEF1FD; --acc-soft:#8FA6F2;
  --gold:#C98A10; --gold-bright:#E6B23D; --gold-bg:#FBF4E3;
  --ok:#1F9D64; --ok-bg:#E7F6EE; --dan:#D64545; --dan-bg:#FBECEC; --dan-line:#F3C9C9;
  --r:16px; --r-sm:11px; --r-pill:9px;
  --sh:0 1px 2px rgba(18,24,38,.05), 0 2px 8px rgba(18,24,38,.04);
  --sh-lift:0 6px 20px rgba(18,24,38,.10);
}
*{box-sizing:border-box}
html,body{margin:0}
body{font-family:Inter,system-ui,sans-serif;background:var(--bg);color:var(--fg);font-size:14px;
  line-height:1.5;-webkit-font-smoothing:antialiased;font-feature-settings:"cv05","ss01"}
.num{font-feature-settings:"tnum";letter-spacing:-.01em}
a{color:var(--acc);text-decoration:none}a:hover{color:var(--acc-700)}
h1,h2,h3{margin:0;font-family:"Bricolage Grotesque",Inter,sans-serif;font-weight:600;letter-spacing:-.02em;color:var(--fg)}
svg{display:block}
::selection{background:var(--acc-50)}

.wrap{display:flex;flex-wrap:wrap;min-height:100vh}

/* ---------- sidebar ---------- */
nav.side{width:248px;flex:0 0 248px;background:var(--ink);color:var(--ink-soft);display:flex;
  flex-direction:column;padding:16px 14px;min-height:100vh;position:sticky;top:0;align-self:flex-start}
.brand{display:flex;align-items:center;gap:11px;padding:6px 8px 20px}
.mark{width:34px;height:34px;border-radius:10px;background:var(--card);color:var(--ink);display:flex;
  align-items:center;justify-content:center;font-family:"Bricolage Grotesque";font-weight:700;font-size:17px}
.brand b{color:#fff;font-weight:600;font-size:15px;font-family:"Bricolage Grotesque";display:block;line-height:1.15}
.brand small{font-size:11.5px;color:var(--ink-soft-2)}
.grp{font-size:12px;color:var(--ink-soft-2);padding:16px 10px 7px;font-weight:500}
nav.side a.item{display:flex;align-items:center;gap:12px;padding:9px 11px;border-radius:var(--r-pill);
  color:var(--ink-soft);font-size:13.5px;font-weight:450;transition:background .13s ease,color .13s ease}
nav.side a.item:hover{background:#15283C;color:#D7DEE8}
nav.side a.item svg{width:18px;height:18px;stroke:currentColor;opacity:.9}
nav.side a.item.on{background:#17293D;color:#fff;font-weight:500}
nav.side a.item.on svg{stroke:var(--acc-soft);opacity:1}
.side-foot{margin-top:auto;border-top:1px solid var(--ink-line);padding-top:12px;display:flex;align-items:center;gap:11px;padding-left:8px}
.me{width:32px;height:32px;border-radius:50%;flex:0 0 32px;display:flex;align-items:center;
  justify-content:center;font-size:12px;font-weight:600;color:#fff;background:linear-gradient(135deg,#2E4A7A,#1A2F52)}
.side-foot b{color:#fff;font-size:13px;font-weight:500;line-height:1.25;display:block;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.side-foot a.out{font-size:11.5px;color:var(--ink-soft-2)}.side-foot a.out:hover{color:#D7DEE8}

/* ---------- main ---------- */
main{flex:999 1 560px;min-width:0;display:flex;flex-direction:column}
header.top{height:62px;background:rgba(255,255,255,.82);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);
  display:flex;align-items:center;gap:16px;padding:0 26px;position:sticky;top:0;z-index:8}
.ws{display:flex;align-items:center;gap:9px;font-size:13px;color:var(--fg-2);font-weight:500}
.ws .pin{width:7px;height:7px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 3px var(--ok-bg)}
.search{position:relative;flex:1;max-width:460px}
.search svg{position:absolute;left:13px;top:50%;transform:translateY(-50%);width:16px;height:16px;stroke:var(--fg-3)}
.search input{width:100%;height:40px;border:1px solid var(--line);border-radius:var(--r-sm);padding:0 12px 0 38px;
  font:inherit;font-size:13.5px;background:var(--card);color:var(--fg)}
.search input::placeholder{color:var(--fg-3)}
.search kbd{position:absolute;right:10px;top:50%;transform:translateY(-50%);font:inherit;font-size:11px;color:var(--fg-3);
  border:1px solid var(--line);border-radius:6px;padding:1px 6px;background:var(--bg)}
.spacer{flex:1}
.iconbtn{width:40px;height:40px;border-radius:var(--r-sm);border:1px solid var(--line);background:var(--card);
  display:flex;align-items:center;justify-content:center;cursor:pointer;position:relative}
.iconbtn svg{width:18px;height:18px;stroke:var(--fg-2)}.iconbtn:hover{background:var(--bg)}
.iconbtn .n{position:absolute;top:8px;right:9px;width:7px;height:7px;border-radius:50%;background:var(--dan);border:2px solid var(--card)}

.content{padding:28px 30px 40px;display:flex;flex-direction:column;gap:22px;max-width:1220px;width:100%}
.greet h1{font-size:30px;line-height:1.1}
.greet p{margin:7px 0 0;color:var(--fg-2);font-size:14px}

/* ---------- agent strip (the one bold element) ---------- */
.agent{border-radius:var(--r);padding:22px 24px;color:#EAF0F7;position:relative;overflow:hidden;
  background:radial-gradient(130% 160% at 100% 0%,#17324E 0%,#0D1B2A 55%)}
.agent::after{content:"";position:absolute;inset:0;background:
  radial-gradient(320px 120px at 92% 20%,rgba(230,178,61,.22),transparent 70%);pointer-events:none}
.agent .row{display:flex;align-items:center;gap:16px;position:relative;flex-wrap:wrap}
.agent .orb{width:46px;height:46px;border-radius:13px;flex:0 0 46px;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(135deg,#E6B23D,#C98A10);box-shadow:0 6px 18px rgba(201,138,16,.35)}
.agent .orb svg{width:24px;height:24px;stroke:#2A1E05}
.agent .ttl{font-family:"Bricolage Grotesque";font-weight:600;font-size:16px;color:#fff;display:flex;align-items:center;gap:10px}
.agent .live{font-size:11.5px;font-weight:600;color:#F2C85A;display:inline-flex;align-items:center;gap:6px}
.agent .live i{width:6px;height:6px;border-radius:50%;background:#F2C85A;box-shadow:0 0 0 0 rgba(242,200,90,.6);animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(242,200,90,.5)}70%{box-shadow:0 0 0 7px rgba(242,200,90,0)}100%{box-shadow:0 0 0 0 rgba(242,200,90,0)}}
.agent .sub{font-size:13px;color:#ABBBCD;margin-top:3px}
.agent .acts{display:flex;gap:10px;margin-left:auto}
.btn-gold{height:38px;border:0;border-radius:10px;background:linear-gradient(135deg,#EBB63F,#D29713);
  color:#2A1E05;font:inherit;font-weight:650;font-size:13px;padding:0 16px;cursor:pointer}
.btn-gold:hover{filter:brightness(1.05)}
.btn-ghost{height:38px;border:1px solid #2B4056;border-radius:10px;background:transparent;color:#C7D3E0;
  font:inherit;font-weight:500;font-size:13px;padding:0 16px;cursor:pointer}
.btn-ghost:hover{background:#15283C}
.agent .tasks{display:flex;gap:26px;margin-top:18px;position:relative;flex-wrap:wrap}
.agent .tk{display:flex;flex-direction:column;gap:2px}
.agent .tk .k{font-family:"Bricolage Grotesque";font-weight:600;font-size:22px;color:#fff}
.agent .tk .v{font-size:12px;color:#8FA2B6}
.agent .tk.warn .k{color:#F2C85A}

/* ---------- stat bar (finance cockpit, not card-kit) ---------- */
.stats{display:grid;grid-template-columns:repeat(4,1fr);background:var(--card);border:1px solid var(--line);
  border-radius:var(--r);box-shadow:var(--sh);overflow:hidden}
.stat{padding:18px 20px;border-left:1px solid var(--line-soft)}
.stat:first-child{border-left:0}
.stat .l{font-size:12.5px;color:var(--fg-2);margin-bottom:9px}
.stat .k{font-family:"Bricolage Grotesque";font-weight:600;font-size:25px;line-height:1}
.stat .d{font-size:12px;margin-top:7px;display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
.stat .d svg{width:14px;height:14px;flex:0 0 14px}
.d.up{color:var(--ok)}.d.down{color:var(--dan)}.d.mut{color:var(--fg-3)}

/* ---------- two-column panels ---------- */
.cols{display:grid;grid-template-columns:1.6fr 1fr;gap:20px;align-items:start}
.panel{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--sh)}
.panel .head{display:flex;align-items:center;gap:10px;padding:18px 20px 0}
.panel .head h3{font-size:15.5px}
.panel .head .leg{margin-left:auto;display:flex;gap:14px;font-size:12px;color:var(--fg-2)}
.panel .head .leg span{display:inline-flex;align-items:center;gap:6px}
.panel .head .leg i{width:9px;height:9px;border-radius:3px}
.chart{padding:16px 20px 20px}

/* activity feed */
.feed{padding:8px 8px 10px}
.ev{display:flex;gap:12px;padding:11px 12px;border-radius:12px}
.ev:hover{background:var(--line-soft)}
.ev .dot{width:30px;height:30px;border-radius:9px;flex:0 0 30px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700}
.ev .dot.ai{background:var(--gold-bg);color:var(--gold)}
.ev .dot.me{background:var(--acc-50);color:var(--acc)}
.ev .tx{font-size:13.3px;line-height:1.45}.ev .tx b{font-weight:600}
.ev .tm{font-size:11.5px;color:var(--fg-3);margin-top:2px}

/* ---------- generic card / tables / forms ---------- */
.panel.pad{padding:20px}
.page-h{display:flex;align-items:flex-end;gap:14px;flex-wrap:wrap}
.page-h h1{font-size:23px}.page-h .sub{color:var(--fg-2);font-size:13.5px;margin-top:4px}
.spacer{flex:1}
.pill{font-size:11px;border-radius:999px;padding:3px 10px;font-weight:600;display:inline-flex;align-items:center;gap:5px}
.pill.blue{background:var(--acc-50);color:var(--acc)}.pill.gray{background:#EEF1F5;color:var(--fg-2)}
.table-wrap{overflow:hidden;border-radius:var(--r)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
thead th{text-align:left;color:var(--fg-2);font-size:12.5px;font-weight:500;padding:13px 18px;background:var(--line-soft);border-bottom:1px solid var(--line)}
tbody td{padding:14px 18px;border-top:1px solid var(--line-soft)}
tbody tr:first-child td{border-top:0}tbody tr:hover{background:#FAFBFC}
.u-name{display:flex;align-items:center;gap:11px;font-weight:500}
.u-av{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#5B79E6,#3B5BDB);color:#fff;display:flex;
  align-items:center;justify-content:center;font-size:11.5px;font-weight:600;flex:0 0 32px}

label{font-size:12.5px;color:var(--fg-2);font-weight:500;display:block;margin-bottom:7px}
input[type=text],input[type=email],input[type=password]{height:42px;border:1px solid var(--line);border-radius:var(--r-sm);
  padding:0 13px;font:inherit;font-size:14px;width:100%;color:var(--fg);background:var(--card);transition:border-color .12s,box-shadow .12s}
input::placeholder{color:var(--fg-3)}
input:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(59,91,219,.14)}
.btn{height:42px;border:0;border-radius:var(--r-sm);background:var(--acc);color:#fff;font:inherit;font-size:14px;
  font-weight:600;padding:0 18px;cursor:pointer;transition:background .12s,transform .05s}
.btn:hover{background:var(--acc-700)}.btn:active{transform:translateY(1px)}.btn.block{width:100%;height:46px}
.form-row{display:flex;flex-direction:column;gap:15px}
.err{background:var(--dan-bg);color:var(--dan);border:1px solid var(--dan-line);border-radius:var(--r-sm);
  padding:11px 14px;font-size:13.5px;display:flex;align-items:center;gap:9px}
.err svg{width:16px;height:16px;stroke:var(--dan);flex:0 0 16px}
.card-head{padding:17px 20px;border-bottom:1px solid var(--line);display:flex;align-items:center}
.card-head h3{font-size:15px}

/* ---------- auth (split screen) ---------- */
.auth{display:grid;grid-template-columns:1.05fr .95fr;min-height:100vh}
.auth .brand-pane{background:radial-gradient(130% 120% at 15% 0%,#17324E,#0A1622 60%);color:#EAF0F7;
  padding:46px 48px;display:flex;flex-direction:column;position:relative;overflow:hidden}
.auth .brand-pane::after{content:"";position:absolute;right:-80px;bottom:-80px;width:340px;height:340px;border-radius:50%;
  background:radial-gradient(circle,rgba(230,178,61,.18),transparent 65%)}
.auth .bp-top{display:flex;align-items:center;gap:11px}
.auth .bp-top b{font-family:"Bricolage Grotesque";font-weight:600;font-size:17px;color:#fff}
.auth .bp-mid{margin-top:auto;position:relative}
.auth .bp-mid h2{font-family:"Bricolage Grotesque";font-weight:600;font-size:30px;line-height:1.18;color:#fff;max-width:15ch}
.auth .bp-mid p{color:#A9BACD;font-size:14.5px;line-height:1.6;max-width:34ch;margin:16px 0 0}
.auth .chip{display:inline-flex;align-items:center;gap:8px;margin-top:26px;background:#13293E;border:1px solid #244056;
  border-radius:999px;padding:7px 14px;font-size:12.5px;color:#E9D4A0}
.auth .chip .o{width:16px;height:16px;stroke:#E6B23D}
.auth .form-pane{display:flex;align-items:center;justify-content:center;padding:40px 28px;background:var(--bg)}
.auth .form-box{width:100%;max-width:372px;display:flex;flex-direction:column;gap:20px}
.auth .form-box h1{font-size:22px}.auth .form-box .lead{color:var(--fg-2);font-size:14px;margin-top:5px}
.auth .foot{font-size:12.5px;color:var(--fg-3)}

@media(max-width:920px){.cols{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}
  .stat:nth-child(3){border-left:0}.auth{grid-template-columns:1fr}.auth .brand-pane{display:none}}
@media(max-width:720px){nav.side{width:100%;flex-basis:100%;min-height:0;position:static;flex-direction:row;flex-wrap:wrap}
  .grp{display:none}.side-foot{margin:0}.content{padding:18px 16px}.greet h1{font-size:25px}.stats{grid-template-columns:1fr 1fr}}

/* ---------- inbox (3-pane attendant workspace) ---------- */
.ibx{display:grid;grid-template-columns:336px 1fr 326px;height:calc(100vh - 62px);background:var(--card)}
.ibx svg{width:16px;height:16px}
.col{min-height:0;display:flex;flex-direction:column}.col.list{border-right:1px solid var(--line)}
.col.ctx{border-left:1px solid var(--line);background:#FbFcFe;overflow-y:auto}
.lh{padding:12px 14px 10px;border-bottom:1px solid var(--line)}
.lh .r1{display:flex;align-items:center;gap:10px}.lh h2{font-size:16px}
.lh .live{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--fg-3)}
.lh .live i{width:7px;height:7px;border-radius:50%;background:var(--fg-3)}
.lh .live.on{color:var(--ok)}.lh .live.on i{background:var(--ok);box-shadow:0 0 0 3px var(--ok-bg)}
.filters{display:flex;gap:6px;margin-top:10px;overflow-x:auto}
.filters button{border:0;background:var(--line-soft);color:var(--fg-2);font:inherit;font-size:12px;font-weight:500;padding:5px 11px;border-radius:999px;cursor:pointer;white-space:nowrap}
.filters button.on{background:var(--ink);color:#fff}.filters button b{font-weight:700}
.clist{overflow-y:auto;flex:1}
.ci{display:flex;gap:10px;padding:12px 13px;border-bottom:1px solid var(--line-soft);cursor:pointer;position:relative}
.ci:hover{background:#FAFBFC}.ci.sel{background:var(--acc-50)}.ci.sel::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--acc)}
.ci .av{width:42px;height:42px;border-radius:50%;flex:0 0 42px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600;color:#fff;position:relative;background:linear-gradient(135deg,#5B79E6,#3B5BDB)}
.ci .av .chan{position:absolute;right:-3px;bottom:-3px;width:19px;height:19px;border-radius:50%;border:2px solid var(--card);display:flex;align-items:center;justify-content:center}
.ci .av .chan svg{width:10px;height:10px;stroke:#fff}
.ci .mid{flex:1;min-width:0}.ci .nm{font-weight:600;font-size:13.5px}
.ci .pv{font-size:12.5px;color:var(--fg-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:3px}
.ci .tags{display:flex;gap:4px;margin-top:6px;flex-wrap:wrap}
.tag-chip{font-size:10px;font-weight:600;padding:1.5px 7px;border-radius:5px}
.ci .rt{display:flex;flex-direction:column;align-items:flex-end;gap:6px}.ci .tm{font-size:11px;color:var(--fg-3)}
.ci .badge{background:var(--acc);color:#fff;font-size:10.5px;font-weight:700;min-width:18px;height:18px;border-radius:9px;display:flex;align-items:center;justify-content:center;padding:0 5px}
.list-empty{padding:40px 20px;text-align:center;color:var(--fg-3);font-size:13px;line-height:1.6}
.th{display:flex;flex-direction:column;min-width:0}
.thh{height:62px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px;padding:0 18px}
.thh .who{font-weight:600;font-size:15px;display:flex;align-items:center;gap:8px}
.thh .sub{font-size:12px;color:var(--fg-3);display:flex;align-items:center;gap:6px;margin-top:2px}
.thh .sub svg{width:13px;height:13px;stroke:var(--fg-3)}
.thh .acts{margin-left:auto;display:flex;gap:7px}
.tbtn{height:36px;border:1px solid var(--line);border-radius:9px;background:var(--card);font:inherit;font-size:13px;font-weight:500;color:var(--fg);padding:0 12px;cursor:pointer;display:inline-flex;align-items:center;gap:7px}
.tbtn svg{stroke:var(--fg-2)}.tbtn:hover{background:var(--bg)}.tbtn.accent{background:var(--acc);border-color:var(--acc);color:#fff}.tbtn.accent svg{stroke:#fff}
.msgs{flex:1;overflow-y:auto;padding:18px 24px;display:flex;flex-direction:column;gap:11px;background:#FBFCFD}
.daysep{text-align:center;font-size:11px;color:var(--fg-3);margin:2px 0}.daysep span{background:var(--line-soft);padding:3px 11px;border-radius:999px}
.m{max-width:60%;padding:10px 13px;border-radius:14px;font-size:13.5px;line-height:1.45}
.m .meta{font-size:10.5px;margin-top:5px;opacity:.72;display:flex;align-items:center;gap:5px}.m .meta svg{width:13px;height:13px}
.m.in{align-self:flex-start;background:var(--card);border:1px solid var(--line);border-bottom-left-radius:5px}
.m.out{align-self:flex-end;background:var(--acc);color:#fff;border-bottom-right-radius:5px}.m.out .tick{color:#9FD5FF}
.m.ai{align-self:flex-end;background:linear-gradient(135deg,#1C3350,#0D1B2A);color:#EAF0F7;border-bottom-right-radius:5px;max-width:62%}
.m.ai .tag{color:#E6B23D;font-weight:700;font-size:10px;display:flex;align-items:center;gap:5px;margin-bottom:5px}.m.ai .tag svg{width:12px;height:12px;stroke:#E6B23D}
.m.note{align-self:center;max-width:72%;background:var(--gold-bg);border:1px solid #EBD9A8;color:#6B5312;font-size:12.5px;text-align:center}
.m.hybrid{align-self:flex-start;border:1px dashed #9BB4EA;background:#F3F6FE}.m.hybrid .ht{font-size:10px;font-weight:700;color:var(--acc);display:flex;align-items:center;gap:5px;margin-bottom:4px}.m.hybrid .ht svg{width:12px;height:12px;stroke:var(--acc)}
.thread-empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;color:var(--fg-3)}
.thread-empty svg{width:40px;height:40px;stroke:var(--line)}
.waba{margin:4px 0;background:#FFF7E6;border:1px solid #F3DFA8;border-radius:12px;padding:12px 14px;display:flex;align-items:center;gap:12px}
.waba .ic{width:34px;height:34px;border-radius:9px;background:#FBEFC7;display:flex;align-items:center;justify-content:center;flex:0 0 34px}.waba .ic svg{stroke:#A87B18}
.waba .tx{flex:1;font-size:12.5px;color:#7A5B10}.waba .tx b{color:#5C4306}
.waba button{height:34px;border:0;border-radius:8px;background:#C98A10;color:#fff;font:inherit;font-weight:600;font-size:12.5px;padding:0 13px;cursor:pointer;white-space:nowrap}
.composer{border-top:1px solid var(--line);padding:11px 16px;display:flex;flex-direction:column;gap:9px}
.composer .tools{display:flex;align-items:center;gap:4px}
.composer .seg{display:inline-flex;gap:4px}
.composer .seg button{border:0;background:transparent;font:inherit;font-size:13px;font-weight:600;color:var(--fg-3);padding:5px 10px;border-radius:8px;cursor:pointer}
.composer .seg button.on{background:var(--acc-50);color:var(--acc)}.composer .seg button.on.note{background:var(--gold-bg);color:#8A6A12}
.composer .signed{margin-left:auto;display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--fg-2)}
.composer .inrow{display:flex;gap:10px}
.composer textarea{flex:1;border:1px solid var(--line);border-radius:10px;padding:10px 12px;font:inherit;font-size:14px;resize:none;height:44px;color:var(--fg)}
.composer textarea:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(59,91,219,.12)}
/* context pane */
.cch{padding:16px 16px 14px;border-bottom:1px solid var(--line);text-align:center}
.cch .big{width:58px;height:58px;border-radius:50%;margin:0 auto 9px;background:linear-gradient(135deg,#5B79E6,#3B5BDB);color:#fff;display:flex;align-items:center;justify-content:center;font-size:19px;font-weight:600;font-family:"Bricolage Grotesque"}
.cch .nm{font-weight:600;font-size:15px}.cch .tr{font-size:12px;color:var(--fg-2);margin-top:2px}
.cch .tags{display:flex;gap:5px;justify-content:center;margin-top:9px;flex-wrap:wrap}
.cch .call{margin-top:12px;width:100%;height:36px;border:1px solid var(--ok);background:var(--ok-bg);color:var(--ok);border-radius:9px;font:inherit;font-weight:600;font-size:13px;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:7px}.cch .call svg{stroke:var(--ok)}
.sec{padding:14px 16px;border-bottom:1px solid var(--line)}
.sec h4{font-size:11px;color:var(--fg-3);font-weight:600;letter-spacing:.03em;margin:0 0 11px;text-transform:uppercase;display:flex;align-items:center;gap:6px}
.sec h4 .cnt{background:var(--acc-50);color:var(--acc);border-radius:999px;font-size:10px;padding:0 6px}
.sec h4 .add{margin-left:auto;color:var(--acc);cursor:pointer;font-size:11px;text-transform:none;font-weight:600}
.idrow{display:flex;align-items:center;gap:10px;padding:6px 0;font-size:13px}
.idrow .ic{width:28px;height:28px;border-radius:8px;display:flex;align-items:center;justify-content:center;flex:0 0 28px;background:var(--acc-50)}.idrow .ic svg{width:15px;height:15px;stroke:var(--acc)}
.idrow .v{font-weight:500}.idrow .k{font-size:11.5px;color:var(--fg-3)}
.rec{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;box-shadow:var(--sh);margin-bottom:10px}
.rec .rt{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.rec .rl{font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:5px}
.rec .nm{font-weight:600;font-size:13.5px}.rec .val{font-family:"Bricolage Grotesque";font-weight:600;font-size:15px}
.rec .fields{display:flex;gap:8px;margin-top:9px}
.rec select{flex:1;border:1px solid var(--line);border-radius:8px;padding:6px 9px;font:inherit;font-size:12px;color:var(--fg-2);background:var(--card)}
.sla{margin-top:9px;font-size:11.5px;display:flex;align-items:center;gap:7px;color:var(--warn)}.sla i{width:7px;height:7px;border-radius:50%;background:var(--warn)}
.sla.met{color:var(--ok)}.sla.met i{background:var(--ok)}
.empty-rec{font-size:12.5px;color:var(--fg-3)}
.ai-card{background:radial-gradient(130% 150% at 100% 0%,#17324E,#0D1B2A);border-radius:12px;padding:14px;color:#EAF0F7}
.ai-card .h{display:flex;align-items:center;gap:8px;font-weight:600;font-size:13px;color:#fff}
.ai-card .h .o{width:22px;height:22px;border-radius:7px;background:linear-gradient(135deg,#E6B23D,#C98A10);display:flex;align-items:center;justify-content:center}.ai-card .h .o svg{width:12px;height:12px;stroke:#2A1E05}
.ai-card button{margin-top:11px;width:100%;height:34px;border:0;border-radius:8px;background:linear-gradient(135deg,#EBB63F,#D29713);color:#2A1E05;font:inherit;font-weight:650;font-size:12.5px;cursor:pointer}
@media(max-width:1100px){.ibx{grid-template-columns:300px 1fr}.col.ctx{display:none}}
@media(max-width:820px){.ibx{grid-template-columns:1fr;height:auto}.col.list{border-right:0;border-bottom:1px solid var(--line)}}
"""

_ICONS = {
    "home": '<path d="M3 10.5 12 4l9 6.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "crm": '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0"/><path d="M16 5.5a3 3 0 0 1 0 5.6M21 20a5 5 0 0 0-3.5-4.8"/>',
    "chat": '<path d="M4 5h16v10H9l-4 4z"/><path d="M8 9h8M8 12h5"/>',
    "cart": '<path d="M4 5h2l2.2 10.2a1 1 0 0 0 1 .8h7.6a1 1 0 0 0 1-.8L20 8H7"/><circle cx="10" cy="20" r="1"/><circle cx="18" cy="20" r="1"/>',
    "coin": '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "doc": '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "box": '<path d="M3 8l9-5 9 5v8l-9 5-9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
    "people": '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0M16 5.5a3 3 0 0 1 0 5.6M21 20a5 5 0 0 0-3.5-4.8"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M4.5 7l2.6 1.5M16.9 15.5 19.5 17M4.5 17l2.6-1.5M16.9 8.5 19.5 7"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.4-3.4"/>',
    "bell": '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
    "spark": '<path d="M12 3l1.7 5L19 10l-5.3 2L12 17l-1.7-5L5 10l5.3-2z"/>',
    "bolt": '<path d="M13 3 4 14h6l-1 7 9-11h-6z"/>',
    "warn": '<path d="M12 9v4M12 17h.01M10.3 4 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 4a2 2 0 0 0-3.4 0z"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L20 13l2 5v2a1 1 0 0 1-1 1A17 17 0 0 1 4 5a1 1 0 0 1 1-1z"/>',
    "mail": '<path d="M3 6h18v12H3z"/><path d="m3 7 9 6 9-6"/>',
}


def icon(name: str, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return (
        f'<svg{c} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        f'stroke-linecap="round" stroke-linejoin="round">{_ICONS.get(name, "")}</svg>'
    )


NAV_MAIN = [
    ("/app", "Início", "home"),
    ("/app", "CRM", "crm"),
    ("/app/inbox", "Atendimento", "chat"),
    ("/app", "Vendas", "cart"),
]
NAV_FIN = [
    ("/app", "Financeiro", "coin"),
    ("/app", "Fiscal", "doc"),
    ("/app", "Inventário", "box"),
]
NAV_ADMIN = [("/app/usuarios", "Usuários", "people")]

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,600;12..96,700'
    '&family=Inter:wght@400;450;500;600;650&display=swap" rel="stylesheet">'
)


def _doc(title: str, body: str) -> str:
    return (
        f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>'
        f"{_FONTS}<style>{CSS}</style></head><body>{body}</body></html>"
    )


def greeting(now: datetime | None = None) -> str:
    h = (now or datetime.now(ZoneInfo("America/Sao_Paulo"))).hour
    return "Bom dia" if h < 12 else "Boa tarde" if h < 18 else "Boa noite"


def _nav_section(label: str, items: list, active: str) -> str:
    out = f'<div class="grp">{label}</div>' if label else ""
    for href, lbl, ic in items:
        on = " on" if lbl == active else ""
        out += f'<a class="item{on}" href="{href}">{icon(ic)}<span>{lbl}</span></a>'
    return out


def shell(*, tenant_slug: str, user_email: str, active: str, body: str, full: bool = False) -> str:
    initials = (user_email or "?")[:2].upper()
    side = (
        '<nav class="side">'
        '<div class="brand"><div class="mark">N</div><div><b>Nettcom ONE</b>'
        f"<small>{tenant_slug}</small></div></div>"
        + _nav_section("", NAV_MAIN, active)
        + _nav_section("Finanças", NAV_FIN, active)
        + _nav_section("Administração", NAV_ADMIN, active)
        + '<div class="side-foot"><div class="me">'
        + initials
        + "</div>"
        + f'<div style="flex:1;min-width:0"><b>{user_email}</b>'
        '<a class="out" href="/logout">Sair</a></div>'
        f'<a class="iconbtn" href="/app" style="width:32px;height:32px">{icon("gear")}</a></div></nav>'
    )
    top = (
        '<header class="top">'
        f'<div class="ws"><span class="pin"></span>{tenant_slug}</div>'
        f'<div class="search">{icon("search")}<input placeholder="Buscar ou pedir ao agente…"><kbd>Ctrl K</kbd></div>'
        '<div class="spacer"></div>'
        f'<button class="iconbtn" aria-label="Notificações">{icon("bell")}<span class="n"></span></button>'
        "</header>"
    )
    inner = body if full else f'<div class="content">{body}</div>'
    return _doc(
        "Nettcom ONE",
        f'<div class="wrap">{side}<main>{top}{inner}</main></div>',
    )


# --------------------------------------------------------------------------- dashboard
def _chart() -> str:
    # Faturado (bars) vs recebido (line+area) — six months, illustrative.
    fat = [58, 64, 61, 74, 82, 90]
    rec = [52, 60, 59, 66, 75, 71]
    months = ["Jun", "Jul", "Ago", "Set", "Out", "Nov"]
    W, H, pad = 560, 190, 8
    n = len(fat)
    bw = (W - pad * 2) / n
    bars = ""
    for i, v in enumerate(fat):
        bh = v / 100 * H
        x = pad + i * bw + bw * 0.28
        bars += (
            f'<rect x="{x:.1f}" y="{H - bh:.1f}" width="{bw * 0.44:.1f}" height="{bh:.1f}" '
            f'rx="4" fill="#3B5BDB" opacity="0.9"/>'
        )
    pts = [(pad + i * bw + bw / 2, H - v / 100 * H) for i, v in enumerate(rec)]
    line = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    area = (
        f"M{pts[0][0]:.1f} {H} L"
        + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        + f" L{pts[-1][0]:.1f} {H} Z"
    )
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#fff" stroke="#C98A10" stroke-width="2"/>'
        for x, y in pts
    )
    labels = "".join(f'<span style="flex:1;text-align:center">{m}</span>' for m in months)
    return (
        '<div class="chart">'
        f'<svg viewBox="0 0 {W} {H + 4}" width="100%" height="200" preserveAspectRatio="none" role="img" aria-label="Faturado e recebido nos últimos seis meses">'
        '<defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#E6B23D" stop-opacity="0.22"/><stop offset="1" stop-color="#E6B23D" stop-opacity="0"/>'
        "</linearGradient></defs>"
        f'{bars}<path d="{area}" fill="url(#ag)"/><path d="{line}" fill="none" stroke="#C98A10" stroke-width="2.4"/>{dots}'
        "</svg>"
        f'<div style="display:flex;color:var(--fg-3);font-size:12px;margin-top:8px">{labels}</div>'
        "</div>"
    )


def _feed() -> str:
    evs = [
        (
            "ai",
            "Qualifiquei <b>Clínica Vida Plena</b> pelo WhatsApp e movi para o funil.",
            "há 18 min",
        ),
        ("ai", "Conciliei 31 lançamentos do extrato Bradesco.", "há 1 h"),
        ("me", "Você fechou o contrato da <b>Carmak</b>.", "há 2 h"),
        ("ai", "Emiti 9 NFS-e de serviços recorrentes.", "hoje, 09:12"),
    ]
    rows = ""
    for kind, tx, tm in evs:
        tag = "IA" if kind == "ai" else "AL"
        rows += (
            f'<div class="ev"><div class="dot {kind}">{tag}</div>'
            f'<div><div class="tx">{tx}</div><div class="tm">{tm}</div></div></div>'
        )
    return f'<div class="feed">{rows}</div>'


def dashboard_body(*, tenant_slug: str, users: int, user_name: str = "") -> str:
    name = (user_name or "").split(" ")[0] or "por aqui"
    return f"""
    <div class="greet"><h1>{greeting()}, {name}</h1>
      <p>Um resumo do que está acontecendo no workspace hoje.</p></div>

    <section class="agent" aria-label="Agente ONE">
      <div class="row">
        <div class="orb">{icon("spark")}</div>
        <div>
          <div class="ttl">Agente ONE <span class="live"><i></i>trabalhando</span></div>
          <div class="sub">Cuidando de tarefas repetitivas enquanto você foca no que importa.</div>
        </div>
        <div class="acts">
          <button class="btn-gold">Ver o que fez</button>
          <button class="btn-ghost">Pedir algo</button>
        </div>
      </div>
      <div class="tasks">
        <div class="tk"><span class="k num">14</span><span class="v">tarefas concluídas hoje</span></div>
        <div class="tk warn"><span class="k num">2</span><span class="v">aguardando sua decisão</span></div>
        <div class="tk"><span class="k num">31</span><span class="v">conversas respondidas</span></div>
      </div>
    </section>

    <div class="stats">
      <div class="stat"><div class="l">Receita recorrente</div><div class="k num">R$ 92.450</div>
        <div class="d up">{icon("bolt")}+6,2% no mês</div>
      </div>
      <div class="stat"><div class="l">A receber (30 dias)</div><div class="k num">R$ 61.300</div>
        <div class="d down">R$ 8.200 vencidos</div></div>
      <div class="stat"><div class="l">Tickets abertos</div><div class="k num">17</div>
        <div class="d mut">3 fora do prazo</div></div>
      <div class="stat"><div class="l">Usuários</div><div class="k num">{users}</div>
        <div class="d mut">no workspace</div></div>
    </div>

    <div class="cols">
      <div class="panel">
        <div class="head"><h3>Faturado e recebido</h3>
          <div class="leg"><span><i style="background:#3B5BDB"></i>Faturado</span>
            <span><i style="background:#C98A10"></i>Recebido</span></div></div>
        {_chart()}
      </div>
      <div class="panel">
        <div class="head"><h3>Atividade</h3></div>
        {_feed()}
      </div>
    </div>"""


# --------------------------------------------------------------------------- users page
def users_body(*, users: list[dict], error: bool) -> str:
    rows = ""
    for u in users:
        av = (u["email"] or "?")[:2].upper()
        badge = (
            '<span class="pill blue">Admin</span>'
            if u["is_admin"]
            else '<span class="pill gray">Usuário</span>'
        )
        rows += (
            f'<tr><td><div class="u-name"><span class="u-av">{av}</span>{u["name"] or "—"}</div></td>'
            f'<td style="color:var(--fg-2)">{u["email"]}</td><td>{badge}</td></tr>'
        )
    err = (
        f'<div class="err">{icon("warn")}Esse e-mail já está em uso. Tente outro.</div>'
        if error
        else ""
    )
    return f"""
    <div class="page-h"><div><h1>Usuários</h1><div class="sub">{len(users)} com acesso a este workspace</div></div></div>
    {err}
    <div class="panel"><div class="table-wrap"><table>
      <thead><tr><th>Nome</th><th>E-mail</th><th>Papel</th></tr></thead>
      <tbody>{rows}</tbody></table></div></div>
    <div class="panel">
      <div class="card-head"><h3>Adicionar usuário</h3></div>
      <form method="post" action="/app/usuarios" style="padding:20px;display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:15px;align-items:end">
        <div><label>Nome</label><input type="text" name="full_name" placeholder="Nome completo"></div>
        <div><label>E-mail</label><input type="email" name="email" required placeholder="[email protected]"></div>
        <div><label>Senha</label><input type="password" name="password" minlength="8" required placeholder="mín. 8 caracteres"></div>
        <button class="btn" type="submit">Adicionar</button>
      </form></div>"""


# --------------------------------------------------------------------------- auth (split)
def _brand_pane(line: str) -> str:
    return (
        '<div class="brand-pane"><div class="bp-top"><div class="mark">N</div><b>Nettcom ONE</b></div>'
        '<div class="bp-mid"><h2>O ERP que trabalha junto com você.</h2>'
        f"<p>{line}</p>"
        f'<div class="chip">{icon("spark", "o")} Com um agente de IA cuidando do repetitivo</div></div></div>'
    )


def auth_page(kind: str, inner: str) -> str:
    line = (
        "Atendimento, vendas, financeiro e fiscal num só lugar — "
        "e um agente que adianta o trabalho por você."
    )
    body = (
        '<div class="auth">'
        + _brand_pane(line)
        + '<div class="form-pane"><div class="form-box">'
        + inner
        + '<div class="foot">Nettcom Tecnologia · Novo Hamburgo, RS</div>'
        + "</div></div></div>"
    )
    return _doc(kind + " · Nettcom ONE", body)


def setup_body(*, tenant_slug: str) -> str:
    return f"""<div><h1>Criar superusuário</h1>
    <div class="lead">Primeiro acesso do workspace <b style="color:var(--fg)">{tenant_slug}</b>. Essa conta administra tudo.</div></div>
    <form method="post" action="/setup" class="form-row">
      <div><label>Nome</label><input type="text" name="full_name" required autofocus placeholder="Seu nome"></div>
      <div><label>E-mail</label><input type="email" name="email" required placeholder="[email protected]"></div>
      <div><label>Senha</label><input type="password" name="password" minlength="8" required placeholder="mín. 8 caracteres"></div>
      <button class="btn block" type="submit">Criar conta e entrar</button>
    </form>"""


def login_body(*, error: bool) -> str:
    err = f'<div class="err">{icon("warn")}E-mail ou senha incorretos.</div>' if error else ""
    return f"""<div><h1>Entrar</h1><div class="lead">Bom te ver de novo.</div></div>
    {err}
    <form method="post" action="/login" class="form-row">
      <div><label>E-mail</label><input type="email" name="email" required autofocus placeholder="[email protected]"></div>
      <div><label>Senha</label><input type="password" name="password" required placeholder="Sua senha"></div>
      <button class="btn block" type="submit">Entrar</button>
    </form>"""


# --------------------------------------------------------------------------- inbox
_CHAN_COLOR = {
    "whatsapp": "#25D366",
    "instagram": "#E1306C",
    "messenger": "#0A7CFF",
    "voip": "#3B5BDB",
    "webchat": "#0EA5E9",
    "email": "#8A6A12",
    "internal": "#64708A",
}
_CHAN_ICON = {"voip": "coin", "instagram": "crm", "email": "doc"}

_INBOX_JS = r"""
<script>
(function(){
  const $ = s => document.querySelector(s);
  const listEl = $('#clist'), msgsEl = $('#msgs'), thh = $('#thh'), ctx = $('#ctx'), composer = $('#composer');
  let current = null, curName = null, mode = 'reply';
  const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const initials = s => (s||'?').slice(0,2).toUpperCase();
  const chanColor = {whatsapp:'#25D366',instagram:'#E1306C',voip:'#3B5BDB',webchat:'#0EA5E9',messenger:'#0A7CFF',email:'#8A6A12',internal:'#64708A'};
  const fmtMs = ms => { if(!ms) return ''; try{ return new Date(ms).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'}); }catch(e){ return ''; } };
  const fmtIso = iso => { if(!iso) return ''; try{ return new Date(iso).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'}); }catch(e){ return ''; } };
  const svgp = d => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'+d+'</svg>';
  const spark = svgp('<path d="M12 3l1.7 5L19 10l-5.3 2L12 17l-1.7-5L5 10l5.3-2z"/>');
  const phone = svgp('<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L20 13l2 5v2a1 1 0 0 1-1 1A17 17 0 0 1 4 5a1 1 0 0 1 1-1z"/>');
  const chatIc = svgp('<path d="M4 5h16v10H9l-4 4z"/>');
  const mailIc = svgp('<path d="M3 6h18v12H3z"/><path d="m3 7 9 6 9-6"/>');
  const chanIcon = {whatsapp:chatIc, webchat:chatIc, instagram:chatIc, voip:phone, email:mailIc};
  const ST_PT = {open:'Aberto',pending:'Pendente',on_hold:'Em espera',resolved:'Resolvido',closed:'Fechado'};
  const PR_PT = {low:'Baixa',normal:'Normal',high:'Alta',urgent:'Urgente'};

  async function j(url, opts){ const r = await fetch(url, opts); return r.ok ? r.json() : null; }

  async function loadConversations(){
    const data = await j('/inbox/conversations'); if(!data) return;
    if(!data.length){ listEl.innerHTML = '<div class="list-empty">Nenhuma conversa ainda.<br>Clique em <b>Simular mensagem</b> para ver o fluxo ao vivo, ou conecte um canal.</div>'; return; }
    listEl.innerHTML = data.map(c => {
      const nm = esc(c.partner_name||'Contato');
      return `<div class="ci ${c.id===current?'sel':''}" data-id="${c.id}" data-name="${nm}">
        <div class="av" style="background:linear-gradient(135deg,#5B79E6,#3B5BDB)">${initials(c.partner_name||'?')}</div>
        <div class="mid"><div class="nm">${nm}</div><div class="pv">${c.status==='resolved'?'Resolvida':'Conversa aberta'}</div></div>
        <div class="rt"><span class="tm">${fmtMs(c.last_message_at)}</span>${c.unread?`<span class="badge">${c.unread}</span>`:''}</div>
      </div>`; }).join('');
    listEl.querySelectorAll('.ci').forEach(el => el.onclick = () => openConversation(el.dataset.id, el.dataset.name));
  }

  async function openConversation(id, name){
    current = id; curName = name;
    document.querySelectorAll('.ci').forEach(e=>e.classList.toggle('sel', e.dataset.id===id));
    composer.style.display = 'flex';
    const [msgs, context] = await Promise.all([ j('/inbox/conversations/'+id+'/messages'), j('/inbox/conversations/'+id+'/context') ]);
    renderHead(context); renderMessages(msgs||[]); renderContext(context);
  }

  function renderHead(c){
    const chan = c && c.channel ? c.channel.type : '';
    thh.innerHTML = `<div><div class="who">${esc(curName||'Contato')}</div>
      <div class="sub">${chan?('<span style="color:'+(chanColor[chan]||'#888')+'">●</span> '+chan):''} ${c&&c.conversation?('· '+(c.conversation.status==='resolved'?'resolvida':'aberta')):''}</div></div>
      <div class="acts"><button class="tbtn" id="btnTicket">Novo ticket</button><button class="tbtn" id="btnLead">Criar lead</button><button class="tbtn accent" id="btnResolve">Resolver</button></div>`;
    $('#btnLead').onclick = createLead; $('#btnTicket').onclick = createTicket;
    $('#btnResolve').onclick = async () => { alert('Resolver conversa chega no próximo bloco.'); };
  }

  function bubble(m){
    if(m.type==='note') return `<div class="m note">${esc(m.body)}<div class="meta">nota interna · ${fmtIso(m.at)}</div></div>`;
    if(m.author==='ai') return `<div class="m ai"><span class="tag">${spark}AGENTE ONE</span>${esc(m.body)}<div class="meta">${fmtIso(m.at)}</div></div>`;
    const cls = m.direction==='inbound' ? 'in' : 'out';
    return `<div class="m ${cls}">${esc(m.body)}<div class="meta">${fmtIso(m.at)}</div></div>`;
  }
  function renderMessages(msgs){
    msgsEl.innerHTML = msgs.length ? msgs.map(bubble).join('') : '<div class="thread-empty">Sem mensagens.</div>';
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  function renderContext(c){
    if(!c){ ctx.innerHTML=''; return; }
    const p = c.partner||{}; const tags = (c.tags||[]).map(t=>`<span class="tag-chip" style="background:${t.color}22;color:${t.color}">${esc(t.name)}</span>`).join('');
    const ids = (c.identities||[]).map(i=>`<div class="idrow"><div class="ic">${chanIcon[i.channel_type]||chatIc}</div><div><div class="v">${esc(i.address)}</div><div class="k">${i.channel_type}</div></div></div>`).join('') || '<div class="empty-rec">Nenhum canal ainda.</div>';
    const leads = (c.leads||[]).map(l=>`<div class="rec"><div class="rt"><span class="rl" style="background:var(--acc-50);color:var(--acc)">LEAD</span><span class="val">R$ ${l.value}</span></div><div class="nm">${esc(l.name)}</div><div class="fields"><div style="flex:1;font-size:12px;color:var(--fg-2)">${esc(l.stage||'—')}</div></div></div>`).join('');
    const tickets = (c.tickets||[]).map(t=>{
      const met = t.sla_state==='met'||t.sla_state==='paused';
      return `<div class="rec"><div class="rt"><span class="rl" style="background:#F2E9FB;color:#8A3BD6">TICKET</span><span style="font-size:11px;color:var(--fg-3)">${t.number||''}</span></div>
        <div class="nm">${esc(t.subject)}</div>
        <div class="fields">
          <select data-tk="${t.id}" data-f="status">${opt(['open','pending','on_hold','resolved','closed'],t.status,ST_PT)}</select>
          <select data-tk="${t.id}" data-f="priority">${opt(['low','normal','high','urgent'],t.priority,PR_PT)}</select>
        </div>
        <div class="sla ${met?'met':''}"><i></i>SLA ${t.sla_state}</div></div>`; }).join('');
    const linked = leads+tickets || '<div class="empty-rec">Nada vinculado. Crie um lead ou ticket acima.</div>';
    const win = c.window||{};
    ctx.innerHTML = `
      <div class="cch"><div class="big">${initials(p.name||'?')}</div><div class="nm">${esc(p.name||'Contato')}</div>
        <div class="tr">${esc(p.trade_name||'')}${p.doc?(' · '+p.doc):''}</div>
        <div class="tags">${tags}</div>
        <button class="cch call">${phone} Ligar</button></div>
      <div class="sec"><h4>Vinculados <span class="cnt">${(c.leads.length+c.tickets.length)}</span></h4>${linked}</div>
      <div class="sec"><h4>Canais do contato</h4>${ids}</div>
      <div class="sec" style="border-bottom:0"><h4>Janela do WhatsApp</h4>
        <div class="empty-rec">${win.open?'<span style="color:var(--ok);font-weight:600">● Aberta</span> — você pode responder livremente.':'<span style="color:var(--warn);font-weight:600">● Fechada</span> — fora das 24h, só template aprovado.'}</div></div>`;
    ctx.querySelectorAll('select[data-tk]').forEach(s => s.onchange = async () => {
      const b = {}; b[s.dataset.f] = s.value;
      await fetch('/inbox/tickets/'+s.dataset.tk, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
    });
  }
  function opt(vals, cur, labels){ return vals.map(v=>`<option value="${v}" ${v===cur?'selected':''}>${(labels&&labels[v])||v}</option>`).join(''); }

  // composer
  document.querySelectorAll('.seg button').forEach(b => b.onclick = () => {
    mode = b.dataset.mode;
    document.querySelectorAll('.seg button').forEach(x=>x.classList.remove('on','note'));
    b.classList.add('on'); if(mode==='note') b.classList.add('note');
    $('#msgText').placeholder = mode==='note' ? 'Nota interna (o cliente não vê)…' : 'Escreva uma resposta…';
  });
  $('#sendBtn').onclick = send;
  $('#msgText').addEventListener('keydown', e => { if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); send(); } });
  async function send(){
    const t = $('#msgText'); const body = t.value.trim(); if(!body || !current) return; t.value='';
    const r = await fetch('/inbox/conversations/'+current+'/reply', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({body, note: mode==='note'})});
    if(r.status===409){ t.value = body; showWindowBanner(); return; }  // 24h window closed
    const msgs = await j('/inbox/conversations/'+current+'/messages'); renderMessages(msgs||[]);
  }
  function showWindowBanner(){
    if(document.getElementById('wabaBanner')) return;
    const bar = document.createElement('div'); bar.className='waba'; bar.id='wabaBanner';
    bar.innerHTML = `<div class="ic">${svgp('<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>')}</div>
      <div class="tx"><b>Janela de 24h encerrada.</b> Fora das 24h, o WhatsApp só permite enviar um template aprovado.</div>
      <button id="wabaSend">Enviar template</button>`;
    msgsEl.appendChild(bar); msgsEl.scrollTop = msgsEl.scrollHeight;
    document.getElementById('wabaSend').onclick = pickTemplate;
  }
  async function pickTemplate(){
    const tpls = await j('/inbox/conversations/'+current+'/templates') || [];
    if(!tpls.length){ alert('Nenhum template aprovado neste canal. Cadastre um template no WhatsApp Business.'); return; }
    const names = tpls.map((t,i)=>`${i+1}. ${t.name} — ${t.body.slice(0,50)}`).join('\n');
    const pick = prompt('Escolha um template:\n'+names, '1'); if(!pick) return;
    const t = tpls[parseInt(pick,10)-1]; if(!t) return;
    await fetch('/inbox/conversations/'+current+'/template', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({template_id:t.id})});
    const b = document.getElementById('wabaBanner'); if(b) b.remove();
    const msgs = await j('/inbox/conversations/'+current+'/messages'); renderMessages(msgs||[]);
  }
  async function createLead(){
    if(!current) return; const name = prompt('Nome do lead:', curName); if(!name) return;
    await fetch('/inbox/conversations/'+current+'/lead', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
    renderContext(await j('/inbox/conversations/'+current+'/context'));
  }
  async function createTicket(){
    if(!current) return; const subject = prompt('Assunto do ticket:'); if(!subject) return;
    await fetch('/inbox/conversations/'+current+'/ticket', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({subject})});
    renderContext(await j('/inbox/conversations/'+current+'/context'));
  }

  const sim = $('#simBtn'); if(sim) sim.onclick = async () => { await fetch('/app/inbox/simular', {method:'POST'}); };

  const dot = $('#liveDot');
  function connectWS(){
    const proto = location.protocol==='https:'?'wss':'ws';
    let ws; try{ ws = new WebSocket(proto+'://'+location.host+'/ws'); }catch(e){ return; }
    ws.onopen = () => dot && dot.classList.add('on');
    ws.onclose = () => { dot && dot.classList.remove('on'); setTimeout(connectWS, 3000); };
    ws.onmessage = ev => { let e; try{ e=JSON.parse(ev.data); }catch(_){ return; }
      if(e.kind==='message.new'){ loadConversations();
        if(current && e.conversation_id===current){ j('/inbox/conversations/'+current+'/messages').then(m=>renderMessages(m||[])); } }
      else if(e.kind==='message.status' && current){ j('/inbox/conversations/'+current+'/messages').then(m=>renderMessages(m||[])); } };
  }
  loadConversations(); connectWS();
})();
</script>"""


def inbox_body(*, demo: bool = True) -> str:
    sim = '<button class="tbtn" id="simBtn">Simular mensagem</button>' if demo else ""
    return f"""<div class="ibx">
      <div class="col list">
        <div class="lh"><div class="r1"><h2>Atendimento</h2><span class="live" id="liveDot"><i></i>ao vivo</span></div>
          <div class="filters"><button class="on">Abertos</button><button>Pendentes</button><button>Minhas</button><button>Resolvidas</button></div></div>
        <div class="clist" id="clist"><div class="list-empty">Carregando…</div></div>
      </div>
      <div class="col th">
        <div class="thh" id="thh"><div><div class="who">Selecione uma conversa</div><div class="sub">As mensagens aparecem aqui</div></div>{sim}</div>
        <div class="msgs" id="msgs"><div class="thread-empty">{icon("chat")}<div>Escolha uma conversa à esquerda</div></div></div>
        <div class="composer" id="composer" style="display:none">
          <div class="tools"><div class="seg"><button class="on" data-mode="reply">Responder</button><button data-mode="note">Nota interna</button></div>
            <span class="signed">Assinado <span style="width:34px;height:19px;border-radius:999px;background:var(--acc);position:relative;display:inline-block"><span style="position:absolute;right:2px;top:2px;width:15px;height:15px;border-radius:50%;background:#fff"></span></span></span></div>
          <div class="inrow"><textarea id="msgText" placeholder="Escreva uma resposta…  (Enter envia)"></textarea><button class="btn" id="sendBtn">Enviar</button></div>
        </div>
      </div>
      <div class="col ctx" id="ctx"></div>
    </div>{_INBOX_JS}"""
