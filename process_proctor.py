#!/usr/bin/env python3
"""Process Proctor test results: load Excel, update CSV DB, generate HTML dashboard.
Usage: python process_proctor.py [--xlsx PATH] [--db PATH] [--html PATH]
"""
import pandas as pd
import numpy as np
import json
import os
import argparse
from datetime import datetime

try:
    from scipy.interpolate import CubicSpline as _CubicSpline
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))

# Excel path from environment variable or default
_DEFAULT_EXCEL = (r'C:\Users\fnicuesa\SRK Consulting'
                  r'\AR M-A610 Rio Tinto - Rincon - Documentos'
                  r'\M-AB20 - RFP SBDF Cell A SD CQA\!WIP\T03 QA'
                  r'\02 Ensayos in-situ\02 Ensayos Proctor'
                  r'\M-AB20-CS-E.V-Muro-Proctor.xlsx')
DEFAULT_XLSX = os.environ.get('EXCEL_PATH', _DEFAULT_EXCEL)

DEFAULT_DB   = os.path.join(SCRIPT_DIR, 'proctor_data', 'proctor_db.csv')
DEFAULT_HTML = os.path.join(SCRIPT_DIR, 'proctor_data', 'proctor_dashboard.html')


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_single_prog(s: str):
    s = s.strip()
    if '+' in s:
        parts = s.split('+', 1)
        try:
            return float(int(parts[0]) * 1000 + int(parts[1]))
        except (ValueError, IndexError):
            return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_progresiva(val):
    if pd.isna(val):
        return None, None
    try:
        v = float(val)
        return v, v
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    if ' a ' in s.lower():
        lo, _, hi = s.lower().partition(' a ')
        return _parse_single_prog(lo.strip()), _parse_single_prog(hi.strip())
    p = _parse_single_prog(s)
    return p, p


def make_test_id(qa_qc: str, nro_ensayo: str) -> str:
    return f"{'TEC' if qa_qc.upper() == 'QA' else 'MIL'}-{nro_ensayo}"


def _safe_str(v) -> str:
    return str(v).strip() if pd.notna(v) else ''


# ---------------------------------------------------------------------------
# Excel loading
# ---------------------------------------------------------------------------

def load_xlsx(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name='Estructural', header=None)
    records = []
    i = 9

    while i < len(df) - 1:
        rd = df.iloc[i]
        rw = df.iloc[i + 1]

        if _safe_str(rd.iloc[9]) != 'Densidad (gr/cm3)':
            i += 1
            continue

        fecha_raw  = rd.iloc[0]
        nro_ensayo = rd.iloc[2]
        material   = rd.iloc[3]
        origen     = rd.iloc[4]
        capa       = rd.iloc[5]
        progresiva = rd.iloc[6]
        gra        = rd.iloc[7]
        qa_qc_raw  = rd.iloc[8]

        d_vals = [rd.iloc[j] for j in range(10, 15)]
        d_max  = rd.iloc[15]
        w_vals = [rw.iloc[j] for j in range(10, 15)]
        w_opt  = rw.iloc[15]

        required = [fecha_raw, nro_ensayo, qa_qc_raw] + d_vals + [d_max] + w_vals + [w_opt]
        if not all(pd.notna(v) and str(v).strip() != '' for v in required):
            i += 2
            continue

        try:
            d      = [float(v) for v in d_vals]
            w      = [float(v) for v in w_vals]
            d_maxf = float(d_max)
            w_optf = float(w_opt)
        except (ValueError, TypeError):
            i += 2
            continue

        qa_qc = _safe_str(qa_qc_raw)
        nro   = _safe_str(nro_ensayo)

        if isinstance(fecha_raw, pd.Timestamp):
            fecha_str = fecha_raw.strftime('%Y-%m-%d')
        else:
            fecha_str = str(fecha_raw).split()[0]

        pr_0, pr_1 = parse_progresiva(progresiva)

        records.append({
            'id':         make_test_id(qa_qc, nro),
            'fecha':      fecha_str,
            'nro_ensayo': nro,
            'material':   _safe_str(material),
            'origen':     _safe_str(origen),
            'capa':       _safe_str(capa),
            'pr_0':       pr_0,
            'pr_1':       pr_1,
            'gra':        _safe_str(gra),
            'qa_qc':      qa_qc,
            'd1': d[0], 'd2': d[1], 'd3': d[2], 'd4': d[3], 'd5': d[4],
            'd_max': d_maxf,
            'w1': w[0], 'w2': w[1], 'w3': w[2], 'w4': w[3], 'w5': w[4],
            'w_opt': w_optf,
        })
        i += 2

    return pd.DataFrame(records) if records else pd.DataFrame()


# ---------------------------------------------------------------------------
# CSV database
# ---------------------------------------------------------------------------

def update_db(new_df: pd.DataFrame, db_path: str) -> pd.DataFrame:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        existing     = pd.read_csv(db_path)
        existing_ids = set(existing['id'].astype(str))
        to_add       = new_df[~new_df['id'].isin(existing_ids)]
        if len(to_add) > 0:
            combined = pd.concat([existing, to_add], ignore_index=True)
            combined.to_csv(db_path, index=False)
            print(f"  Added {len(to_add)} new test(s). Total: {len(combined)}")
            return combined
        print(f"  No new tests. DB has {len(existing)} test(s).")
        return existing
    new_df.to_csv(db_path, index=False)
    print(f"  Created DB with {len(new_df)} test(s).")
    return new_df


# ---------------------------------------------------------------------------
# Smooth / fitted curves
# ---------------------------------------------------------------------------

def _smooth_curve(w_pts, d_pts, w_opt=None, d_max=None, n=80):
    """Return (w_grid, d_poly4, d_para, d_para_free, d_spline) — all length-n lists.

    Two parabolic fits are computed:
      d_para      — vertex-constrained:  d(w) = d_max − a·(w − w_opt)²
                    single parameter a ≥ 0 found by closed-form least squares.
      d_para_free — unconstrained poly-2 (standard least squares, no vertex
                    constraint); the free parabola best-fitting all 5 points.
    """
    w_arr = np.array(w_pts, dtype=float)
    d_arr = np.array(d_pts, dtype=float)
    order = np.argsort(w_arr)
    w_s, d_s = w_arr[order], d_arr[order]
    w_lin = np.linspace(float(w_s[0]), float(w_s[-1]), n)

    # poly-4 (smoothed)
    d_poly4 = np.polyval(np.polyfit(w_s, d_s, min(4, len(w_s) - 1)), w_lin)

    # constrained parabola: vertex fixed at (w_opt, d_max)
    # d(w) = d_max - a*(w - w_opt)^2   →   minimise Σ(d_i - d_max + a*X_i)^2
    # where X_i = (w_i - w_opt)^2
    # solution: a = Σ[X_i*(d_max - d_i)] / Σ[X_i^2]   (clamped to ≥ 0)
    if w_opt is not None and d_max is not None:
        X   = (w_s - w_opt) ** 2
        den = float(np.dot(X, X))
        a   = float(np.dot(X, (d_max - d_s))) / den if den > 1e-14 else 0.0
        a   = max(a, 0.0)                  # enforce downward-opening parabola
        d_para = d_max - a * (w_lin - w_opt) ** 2
    else:                                  # fallback if optimum unknown
        d_para = np.polyval(np.polyfit(w_s, d_s, min(2, len(w_s) - 1)), w_lin)

    # unconstrained parabola: free poly-2 least squares (no vertex constraint)
    d_para_free = np.polyval(np.polyfit(w_s, d_s, min(2, len(w_s) - 1)), w_lin)

    # cubic spline (requires scipy; falls back to poly-4)
    if _HAS_SCIPY and len(w_s) >= 3:
        d_spline = _CubicSpline(w_s, d_s)(w_lin)
    else:
        d_spline = d_poly4

    r5 = lambda v: [round(x, 5) for x in np.asarray(v).tolist()]
    r6 = lambda v: [round(x, 6) for x in np.asarray(v).tolist()]
    return r5(w_lin), r6(d_poly4), r6(d_para), r6(d_para_free), r6(d_spline)


# ---------------------------------------------------------------------------
# HTML dashboard generation
# ---------------------------------------------------------------------------

def _nanf(v):
    return None if (v is None or (isinstance(v, float) and np.isnan(v))) else float(v)


def generate_html(df: pd.DataFrame, html_path: str) -> None:
    tests_js = []
    for _, r in df.iterrows():
        w = [float(r[f'w{i}']) for i in range(1, 6)]
        d = [float(r[f'd{i}']) for i in range(1, 6)]
        w_sm, d_poly4, d_para, d_para_free, d_spline = _smooth_curve(
            w, d, w_opt=float(r['w_opt']), d_max=float(r['d_max'])
        )
        tests_js.append({
            'id':           r['id'],
            'fecha':        r['fecha'],
            'nro_ensayo':   r['nro_ensayo'],
            'material':     r['material'],
            'origen':       r['origen'],
            'capa':         str(r['capa']),
            'pr_0':         _nanf(r['pr_0']),
            'pr_1':         _nanf(r['pr_1']),
            'gra':          r['gra'],
            'qa_qc':        r['qa_qc'],
            'd':            d,
            'd_max':        float(r['d_max']),
            'w':            w,
            'w_opt':        float(r['w_opt']),
            'w_smooth':     w_sm,
            'd_smooth':     d_poly4,
            'd_para':       d_para,       # constrained — vertex at (w_opt, d_max)
            'd_para_free':  d_para_free,  # unconstrained — free poly-2 LSQ
            'd_spline':     d_spline,
        })

    json_data   = json.dumps(tests_js, ensure_ascii=False)
    update_time = datetime.now().strftime('%Y-%m-%d %H:%M')

    dates  = sorted(set(t['fecha'] for t in tests_js))
    pr_all = [t['pr_0'] for t in tests_js if t['pr_0'] is not None] + \
             [t['pr_1'] for t in tests_js if t['pr_1'] is not None]
    capas  = sorted(set(t['capa'] for t in tests_js if t['capa']))

    date_min = dates[0]  if dates  else ''
    date_max = dates[-1] if dates  else ''
    pr_min   = int(min(pr_all)) if pr_all else 0
    pr_max   = int(max(pr_all)) if pr_all else 99999

    # ------------------------------------------------------------------
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Proctor Dashboard \u2014 AR-MAB20</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Arial,sans-serif;background:#f0f2f5;color:#2c3e50}}
/* HEADER */
.hdr{{background:linear-gradient(135deg,#1a2f4a 0%,#2471a3 100%);color:#fff;
  padding:14px 24px;display:flex;justify-content:space-between;align-items:center;
  box-shadow:0 2px 8px rgba(0,0,0,.28);gap:16px;flex-wrap:wrap}}
.hdr h1{{font-size:1.2rem;font-weight:700;letter-spacing:.02em}}
.hdr .sub{{font-size:.73rem;opacity:.72;margin-top:3px}}
.hdr-right{{display:flex;align-items:center;gap:12px;flex-shrink:0}}
.upd{{font-size:.7rem;opacity:.6;text-align:right;white-space:nowrap}}
#upd-status{{font-size:.7rem;color:rgba(255,255,255,.9);white-space:nowrap;max-width:260px;text-align:right}}
/* CONTROLS */
.ctrl{{background:#fff;padding:10px 24px;display:flex;flex-wrap:wrap;gap:18px;
  align-items:flex-end;border-bottom:1px solid #e8edf2;
  box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.ctrl-sub{{background:#f8f9fb;padding:8px 24px;display:flex;flex-wrap:wrap;gap:18px;
  align-items:flex-end;border-bottom:2px solid #e0e6ed;font-size:.78rem}}
.cg{{display:flex;flex-direction:column;gap:4px}}
.cg>label{{font-size:.67rem;font-weight:700;color:#7f8c8d;text-transform:uppercase;letter-spacing:.06em}}
.cr{{display:flex;gap:6px;align-items:center}}
input[type=date],input[type=number]{{border:1px solid #c8d6df;border-radius:4px;
  padding:5px 8px;font-size:.82rem;color:#2c3e50;background:#fff;outline:none;
  transition:border-color .15s}}
input[type=date]:focus,input[type=number]:focus{{border-color:#2471a3}}
input[type=date]:disabled,input[type=number]:disabled{{background:#f4f6f7;color:#aaa;cursor:not-allowed}}
input[type=number]{{width:90px}}
input[type=date]{{width:130px}}
select.ctrl-sel{{border:1px solid #c8d6df;border-radius:4px;padding:5px 8px;
  font-size:.82rem;color:#2c3e50;background:#fff;outline:none;cursor:pointer;
  transition:border-color .15s}}
select.ctrl-sel:focus{{border-color:#2471a3}}
.fname{{font-size:.75rem;color:#7f8c8d;max-width:260px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.chk{{display:flex;gap:12px;align-items:center}}
.cl{{display:flex;align-items:center;gap:4px;cursor:pointer;font-size:.82rem;user-select:none}}
.cl input{{cursor:pointer;width:14px;height:14px}}
.sep{{color:#bdc3c7;font-size:.85rem}}
/* BUTTONS */
.btn{{padding:5px 13px;border:1.5px solid #2471a3;border-radius:4px;background:#fff;
  color:#2471a3;cursor:pointer;font-size:.78rem;font-weight:700;transition:all .18s;white-space:nowrap}}
.btn:hover,.btn.on{{background:#2471a3;color:#fff}}
.btn.rst{{border-color:#aaa;color:#95a5a6}}
.btn.rst:hover{{background:#95a5a6;color:#fff;border-color:#95a5a6}}
.btn.upd{{background:#27ae60;border-color:#27ae60;color:#fff}}
.btn.upd:hover{{background:#1e8449;border-color:#1e8449}}
.btn.upd:disabled{{opacity:.55;cursor:not-allowed;background:#27ae60}}
.btn.exp{{border-color:#e67e22;color:#e67e22;font-size:.72rem;padding:3px 10px}}
.btn.exp:hover{{background:#e67e22;color:#fff}}
.btn.del{{border-color:#c0392b;color:#c0392b}}
.btn.del:hover{{background:#c0392b;color:#fff}}
.btn.del:disabled{{opacity:.4;cursor:not-allowed;background:#fff}}
/* STATS BAR */
.sb{{background:#eaf2fb;padding:7px 24px;display:flex;gap:22px;flex-wrap:wrap;
  border-bottom:1px solid #c8dff0;font-size:.77rem;color:#1a2f4a}}
.sb span{{font-weight:700}}
/* CONTENT */
.content{{padding:14px 20px}}
.card{{background:#fff;border-radius:8px;box-shadow:0 1px 5px rgba(0,0,0,.09);
  margin-bottom:14px;overflow:hidden}}
.card-hdr{{display:flex;justify-content:space-between;align-items:center;
  padding:10px 16px;border-bottom:1px solid #f0f0f0;gap:10px}}
.ctitle{{font-size:.84rem;font-weight:700;color:#1a2f4a}}
.card-tools{{display:flex;gap:8px;align-items:center;flex-shrink:0}}
.bin-ctrl{{display:flex;gap:5px;align-items:center;font-size:.73rem;color:#7f8c8d}}
.bin-ctrl select{{font-size:.73rem;padding:2px 5px;border:1px solid #c8d6df;
  border-radius:4px;color:#2c3e50;background:#fff;cursor:pointer;outline:none}}
.bin-ctrl input{{width:56px;font-size:.73rem;padding:2px 5px;border:1px solid #c8d6df;
  border-radius:4px;color:#2c3e50;background:#fff;outline:none}}
.hrow{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:700px){{.hrow{{grid-template-columns:1fr}}}}
#proctor-plot,#hist-dmax,#hist-wopt{{width:100%}}
</style>
</head>
<body>

<div class="hdr">
  <div>
    <h1>Ensayos Proctor Modificado \u2014 AR-MAB20</h1>
    <div class="sub">RFP SBDF Cell A &middot; Muro &middot; Control de Calidad</div>
  </div>
  <div class="hdr-right">
    <div id="upd-status"></div>
    <button class="btn upd" id="btnupd" onclick="updateDB()">&#8635; Actualizar BD</button>
    <div class="upd">Actualizado: {update_time}</div>
  </div>
</div>

<!-- Main filter controls -->
<div class="ctrl">
  <div class="cg">
    <label>Rango de Fechas</label>
    <div class="cr">
      <input type="date" id="dfrom" value="{date_min}">
      <span class="sep">&mdash;</span>
      <input type="date" id="dto"   value="{date_max}">
      <button class="btn" id="btn-alld" onclick="toggleAll('date')" title="Mostrar todos sin filtrar fechas">Todos</button>
    </div>
  </div>
  <div class="cg">
    <label>Progresiva</label>
    <div class="cr">
      <input type="number" id="prmin" value="{pr_min}" step="50">
      <span class="sep">&mdash;</span>
      <input type="number" id="prmax" value="{pr_max}" step="50">
      <button class="btn" id="btn-allp" onclick="toggleAll('pr')" title="Mostrar todos sin filtrar progresivas">Todos</button>
    </div>
  </div>
  <div class="cg">
    <label>Tipo de Ensayo</label>
    <div class="chk">
      <label class="cl">
        <input type="checkbox" id="chkqa" checked>
        <span style="color:#1f77b4;font-weight:600">QA (TEC)</span>
      </label>
      <label class="cl">
        <input type="checkbox" id="chkqc" checked>
        <span style="color:#d35400;font-weight:600">QC (MIL)</span>
      </label>
    </div>
  </div>
  <div class="cg" style="position:relative;z-index:10">
    <label>Capas</label>
    <div style="position:relative;display:inline-block;width:100%">
      <button class="btn" id="btn-toggle-capas" onclick="toggleCapasDropdown()"
        style="display:flex;align-items:center;justify-content:space-between;width:100%;gap:8px;background:#fff;border:1.5px solid #c8d6df">
        <span id="capas-count" style="flex:1;text-align:left;font-size:.82rem">Capas</span>
        <span style="color:#7f8c8d;font-size:.9rem">▼</span>
      </button>
      <div id="capas-dropdown" style="display:none;position:absolute;top:calc(100% + 4px);left:0;right:0;background:#fff;border:1px solid #c8d6df;border-radius:4px;box-shadow:0 4px 12px rgba(0,0,0,.12);z-index:20;min-width:180px">
        <div style="padding:8px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center">
          <span style="font-weight:600;font-size:.75rem;color:#7f8c8d">CAPAS</span>
          <button class="btn" id="btn-all-capas-inner" onclick="toggleAllCapas()" style="padding:3px 8px;font-size:.68rem;border:1px solid #ddd">Todas</button>
        </div>
        <div id="capas-list" style="display:flex;flex-direction:column;gap:0;max-height:180px;overflow-y:auto;padding:4px"></div>
      </div>
    </div>
  </div>
  <div class="cg">
    <label>Ajuste de Curva</label>
    <select class="ctrl-sel" id="fit-type" onchange="update()">
      <option value="none">Sin ajuste</option>
      <option value="poly4" selected>Suavizado (gr. 4)</option>
      <option value="para">Parab&oacute;lico centrado (v&eacute;rtice = &oacute;ptimo)</option>
      <option value="para_free">Parab&oacute;lico libre (MCO gr. 2)</option>
      <option value="spline">Spline c&uacute;bico</option>
    </select>
  </div>
  <div class="cg">
    <label>Opciones</label>
    <div class="cr">
      <button class="btn on" id="btnleg" onclick="toggleLegend()">Leyenda ON</button>
      <button class="btn rst"            onclick="resetFilters()">Resetear</button>
    </div>
  </div>
</div>

<!-- Excel source / reset controls -->
<div class="ctrl-sub">
  <div class="cg">
    <label>Cargar nuevo Excel (reemplaza BD)</label>
    <div class="cr">
      <input type="file" id="xlsxFile" accept=".xlsx" style="display:none" onchange="onFileSelected()">
      <button class="btn" onclick="document.getElementById('xlsxFile').click()">&#128194; Seleccionar .xlsx</button>
      <span class="fname" id="xlsx-name">&mdash; ning&uacute;n archivo seleccionado</span>
      <button class="btn del" id="btn-reset" onclick="resetFromExcel()" disabled>&#9888; Reemplazar BD</button>
    </div>
  </div>
</div>

<div class="sb">
  <div>Ensayos: <span id="sn">&mdash;</span></div>
  <div>QA: <span id="sqa">&mdash;</span></div>
  <div>QC: <span id="sqc">&mdash;</span></div>
  <div>D<sub>max</sub> prom: <span id="sdmax">&mdash;</span></div>
  <div>&#963;(D<sub>max</sub>): <span id="ssdmax">&mdash;</span></div>
  <div>W<sub>opt</sub> prom: <span id="swopt">&mdash;</span></div>
  <div>&#963;(W<sub>opt</sub>): <span id="sswopt">&mdash;</span></div>
</div>

<div class="content">
  <div class="card">
    <div class="card-hdr">
      <div class="ctitle">Curvas Proctor &mdash; Densidad Seca vs. Humedad
        &nbsp;<small style="font-weight:400;color:#7f8c8d">(QA = l&iacute;nea continua &middot; QC = l&iacute;nea punteada &middot; &#9733; = &oacute;ptimo)</small>
      </div>
      <div class="card-tools">
        <button class="btn exp" onclick="exportPlot('proctor-plot','proctor_curvas')">&#8615; PNG</button>
      </div>
    </div>
    <div id="proctor-plot"></div>
  </div>
  <div class="hrow">
    <div class="card">
      <div class="card-hdr">
        <div class="ctitle">Distribuci&oacute;n D<sub>max</sub> (g/cm&sup3;)</div>
        <div class="card-tools">
          <div class="bin-ctrl">
            <select id="bin-mode-dmax" onchange="update()">
              <option value="count">N&deg; bins</option>
              <option value="size">Ancho</option>
            </select>
            <input type="number" id="bin-val-dmax" value="0" min="0" step="any" placeholder="auto" onchange="update()">
          </div>
          <button class="btn exp" onclick="exportPlot('hist-dmax','proctor_hist_dmax')">&#8615; PNG</button>
        </div>
      </div>
      <div id="hist-dmax"></div>
    </div>
    <div class="card">
      <div class="card-hdr">
        <div class="ctitle">Distribuci&oacute;n W<sub>opt</sub> (%)</div>
        <div class="card-tools">
          <div class="bin-ctrl">
            <select id="bin-mode-wopt" onchange="update()">
              <option value="count">N&deg; bins</option>
              <option value="size">Ancho</option>
            </select>
            <input type="number" id="bin-val-wopt" value="0" min="0" step="any" placeholder="auto" onchange="update()">
          </div>
          <button class="btn exp" onclick="exportPlot('hist-wopt','proctor_hist_wopt')">&#8615; PNG</button>
        </div>
      </div>
      <div id="hist-wopt"></div>
    </div>
  </div>
</div>

<script>
const TESTS = {json_data};

const D_DATE_FROM = '{date_min}';
const D_DATE_TO   = '{date_max}';
const D_PR_MIN    = {pr_min};
const D_PR_MAX    = {pr_max};
const CAPAS_LIST  = {json.dumps(capas, ensure_ascii=False)};

const COLORS = [
  '#1f77b4','#d35400','#27ae60','#c0392b','#8e44ad',
  '#16a085','#f39c12','#2980b9','#7f8c8d','#2ecc71',
  '#e74c3c','#1abc9c','#f1c40f','#9b59b6','#3498db',
  '#e67e22','#95a5a6','#27ae60','#c0392b','#2471a3'
];

const cmap = {{}};
TESTS.forEach((t, i) => {{ cmap[t.id] = COLORS[i % COLORS.length]; }});

let legVis   = true;
let allDates = false;
let allPr    = false;

// --- Filters ---

function getFilters() {{
  const capasChecked = [];
  CAPAS_LIST.forEach(c => {{
    if (document.getElementById('chk-capa-' + c)?.checked) {{
      capasChecked.push(c);
    }}
  }});
  return {{
    df: document.getElementById('dfrom').value,
    dt: document.getElementById('dto').value,
    pm: parseFloat(document.getElementById('prmin').value) || 0,
    px: parseFloat(document.getElementById('prmax').value) || 1e9,
    qa: document.getElementById('chkqa').checked,
    qc: document.getElementById('chkqc').checked,
    capas: capasChecked,
  }};
}}

function filterTests() {{
  const f = getFilters();
  return TESTS.filter(t => {{
    if (!allDates && (t.fecha < f.df || t.fecha > f.dt)) return false;
    const qt = t.qa_qc.trim().toUpperCase();
    if (qt === 'QA' && !f.qa) return false;
    if (qt === 'QC' && !f.qc) return false;
    if (!allPr && t.pr_0 !== null && t.pr_1 !== null) {{
      if (t.pr_0 > f.px || t.pr_1 < f.pm) return false;
    }}
    if (f.capas.length > 0 && !f.capas.includes(t.capa)) return false;
    return true;
  }});
}}

function toggleAll(which) {{
  if (which === 'date') {{
    allDates = !allDates;
    document.getElementById('btn-alld').classList.toggle('on', allDates);
    document.getElementById('dfrom').disabled = allDates;
    document.getElementById('dto').disabled   = allDates;
  }} else {{
    allPr = !allPr;
    document.getElementById('btn-allp').classList.toggle('on', allPr);
    document.getElementById('prmin').disabled = allPr;
    document.getElementById('prmax').disabled = allPr;
  }}
  update();
}}

// --- Hover text ---

function buildHoverCurve(t) {{
  return t.w.map((w, i) =>
    '<b>' + t.id + '</b><br>' +
    'W: ' + w.toFixed(2) + ' %<br>' +
    'D: ' + t.d[i].toFixed(3) + ' g/cm\u00b3<br>' +
    'GRA: ' + t.gra + '<br>' +
    'Fecha: ' + t.fecha + '<br>' +
    'Capa: ' + t.capa + '<br>' +
    'Progresiva: ' + t.pr_0 + (t.pr_0 !== t.pr_1 ? ' \u2013 ' + t.pr_1 : '')
  );
}}

function buildHoverOpt(t) {{
  return '<b>' + t.id + ' \u2014 \u00d3ptimo</b><br>' +
    'W<sub>opt</sub>: ' + t.w_opt.toFixed(2) + ' %<br>' +
    'D<sub>max</sub>: ' + t.d_max.toFixed(3) + ' g/cm\u00b3<br>' +
    'GRA: ' + t.gra + '<br>' +
    'Fecha: ' + t.fecha + '<br>' +
    'Capa: ' + t.capa;
}}

// --- Curve fitting selector ---

function getLineData(t) {{
  const fit = document.getElementById('fit-type').value;
  if (fit === 'poly4')      return {{ w: t.w_smooth, d: t.d_smooth     }};
  if (fit === 'para')       return {{ w: t.w_smooth, d: t.d_para       }};  // constrained
  if (fit === 'para_free')  return {{ w: t.w_smooth, d: t.d_para_free  }};  // free poly-2
  if (fit === 'spline')     return {{ w: t.w_smooth, d: t.d_spline     }};
  return {{ w: t.w, d: t.d }};  // none — original points only
}}

// --- Proctor plot ---

function renderProctor(tests) {{
  const traces = [];
  tests.forEach(t => {{
    const col  = cmap[t.id];
    const isQA = t.qa_qc.trim().toUpperCase() === 'QA';
    const ld   = getLineData(t);
    const isFit = document.getElementById('fit-type').value !== 'none';
    // line (smooth or straight)
    traces.push({{
      x: ld.w, y: ld.d,
      mode: 'lines',
      name: t.id,
      legendgroup: t.id,
      showlegend: true,
      line:      {{ color: col, dash: isQA ? 'solid' : 'dash', width: 2.5 }},
      hoverinfo: 'skip',
    }});
    // original data points (always shown as markers)
    traces.push({{
      x: t.w, y: t.d,
      mode: 'markers',
      name: t.id + ' pts',
      legendgroup: t.id,
      showlegend: false,
      marker: {{ size: isFit ? 6 : 8, color: col, line: {{ color: '#fff', width: 1 }} }},
      text: buildHoverCurve(t),
      hoverinfo: 'text',
    }});
    // optimal star
    traces.push({{
      x: [t.w_opt], y: [t.d_max],
      mode: 'markers',
      name: t.id + '\u2605',
      legendgroup: t.id,
      showlegend: false,
      marker: {{ size: 14, symbol: 'star', color: col,
                 line: {{ color: '#fff', width: 1.5 }} }},
      text: [buildHoverOpt(t)],
      hoverinfo: 'text',
    }});
  }});

  const layout = {{
    xaxis: {{ title: 'Humedad (%)',                gridcolor: '#ecf0f1', zeroline: false }},
    yaxis: {{ title: 'Densidad seca (g/cm\u00b3)', gridcolor: '#ecf0f1', zeroline: false }},
    showlegend: legVis,
    legend: {{
      x: 1.01, y: 1, xanchor: 'left', yanchor: 'top',
      bgcolor: 'rgba(255,255,255,.92)', bordercolor: '#ddd', borderwidth: 1,
      font: {{ size: 11 }},
    }},
    margin: {{ t: 20, r: 200, b: 55, l: 70 }},
    height: 500,
    plot_bgcolor: '#fafbfc',
    paper_bgcolor: '#fff',
    hovermode: 'closest',
  }};
  Plotly.react('proctor-plot', traces, layout, {{responsive: true}});
}}

// --- Histograms ---

function avg(a) {{ return a.length ? a.reduce((s, v) => s + v, 0) / a.length : NaN; }}
function std(a) {{
  if (a.length < 2) return NaN;
  const m = avg(a);
  return Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / (a.length - 1));
}}
function fmt(v, dec) {{ return isNaN(v) ? '\u2014' : v.toFixed(dec); }}

function getBinConfig(modeId, valId) {{
  const mode = document.getElementById(modeId).value;
  const val  = parseFloat(document.getElementById(valId).value);
  if (!val || val <= 0) return {{}};
  return mode === 'size' ? {{ xbins: {{ size: val }} }} : {{ nbinsx: Math.round(val) }};
}}

function renderHist(divId, vals, color, xtitle, modeId, valId) {{
  const mu = avg(vals);
  const shapes = isNaN(mu) ? [] : [{{
    type: 'line', x0: mu, x1: mu, y0: 0, y1: 1, yref: 'paper',
    line: {{ color: '#e74c3c', width: 2, dash: 'dash' }},
  }}];
  const anns = isNaN(mu) ? [] : [{{
    x: mu, y: 1.05, yref: 'paper',
    text: '\u03bc\u202f=\u202f' + mu.toFixed(3),
    showarrow: false, font: {{ color: '#e74c3c', size: 11 }},
    xanchor: 'center',
  }}];
  const binCfg = getBinConfig(modeId, valId);
  const trace  = Object.assign({{
    x: vals, type: 'histogram',
    marker: {{ color, opacity: .72, line: {{ color: '#fff', width: .8 }} }},
    hovertemplate: xtitle + ': %{{x}}<br>Frec: %{{y}}<extra></extra>',
  }}, binCfg);
  Plotly.react(divId,
    [trace],
    {{
      xaxis:        {{ title: xtitle, gridcolor: '#ecf0f1' }},
      yaxis:        {{ title: 'Frecuencia', gridcolor: '#ecf0f1' }},
      margin:       {{ t: 30, r: 20, b: 55, l: 55 }},
      height:       300,
      plot_bgcolor: '#fafbfc',
      paper_bgcolor:'#fff',
      bargap:       .05,
      showlegend:   false,
      shapes, annotations: anns,
    }},
    {{responsive: true}}
  );
}}

// --- Stats bar ---

function updateStats(tests) {{
  const dm = tests.map(t => t.d_max);
  const wo = tests.map(t => t.w_opt);
  const qa = tests.filter(t => t.qa_qc.trim().toUpperCase() === 'QA');
  const qc = tests.filter(t => t.qa_qc.trim().toUpperCase() === 'QC');
  document.getElementById('sn').textContent     = tests.length;
  document.getElementById('sqa').textContent    = qa.length;
  document.getElementById('sqc').textContent    = qc.length;
  document.getElementById('sdmax').textContent  = fmt(avg(dm), 3) + (dm.length ? ' g/cm\u00b3' : '');
  document.getElementById('ssdmax').textContent = fmt(std(dm), 4) + (dm.length > 1 ? ' g/cm\u00b3' : '');
  document.getElementById('swopt').textContent  = fmt(avg(wo), 2) + (wo.length ? ' %' : '');
  document.getElementById('sswopt').textContent = fmt(std(wo), 3) + (wo.length > 1 ? ' %' : '');
}}

// --- Main update ---

function update() {{
  const t = filterTests();
  renderProctor(t);
  renderHist('hist-dmax', t.map(x => x.d_max), '#2471a3', 'D_max (g/cm\u00b3)', 'bin-mode-dmax', 'bin-val-dmax');
  renderHist('hist-wopt', t.map(x => x.w_opt), '#d35400', 'W_opt (%)',           'bin-mode-wopt', 'bin-val-wopt');
  updateStats(t);
}}

// --- Toggles & reset ---

function toggleLegend() {{
  legVis = !legVis;
  const b = document.getElementById('btnleg');
  b.classList.toggle('on', legVis);
  b.textContent = legVis ? 'Leyenda ON' : 'Leyenda OFF';
  Plotly.relayout('proctor-plot', {{'showlegend': legVis}});
}}

function resetFilters() {{
  allDates = false; allPr = false;
  ['btn-alld', 'btn-allp'].forEach(id => document.getElementById(id).classList.remove('on'));
  ['dfrom', 'dto', 'prmin', 'prmax'].forEach(id => document.getElementById(id).disabled = false);
  document.getElementById('dfrom').value    = D_DATE_FROM;
  document.getElementById('dto').value      = D_DATE_TO;
  document.getElementById('prmin').value    = D_PR_MIN;
  document.getElementById('prmax').value    = D_PR_MAX;
  document.getElementById('chkqa').checked  = true;
  document.getElementById('chkqc').checked  = true;
  document.getElementById('fit-type').value = 'poly4';
  update();
}}

// --- Export ---

function exportPlot(divId, filename) {{
  const isProctor = divId === 'proctor-plot';
  Plotly.downloadImage(divId, {{
    format:   'png',
    filename: filename,
    scale:    3,
    width:    isProctor ? 1600 : 1000,
    height:   isProctor ? 900  :  600,
  }});
}}

// --- Update DB from Excel (incremental, requires serve_proctor.py) ---

async function updateDB() {{
  const btn    = document.getElementById('btnupd');
  const status = document.getElementById('upd-status');
  btn.disabled    = true;
  btn.textContent = '\u23f3 Actualizando...';
  status.textContent = '';
  try {{
    const res = await fetch('/api/update', {{ method: 'POST' }});
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    if (data.status === 'error') throw new Error(data.message);
    status.textContent = '\u2713 ' + data.total + ' ensayos \u2014 recargando...';
    setTimeout(() => location.reload(), 800);
  }} catch(e) {{
    const msg = e.message || '';
    if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg === 'HTTP 404') {{
      status.textContent = '\u26a0\ufe0f Inicia: python serve_proctor.py';
    }} else {{
      status.textContent = '\u2717 ' + msg.slice(0, 60);
    }}
    btn.disabled    = false;
    btn.textContent = '\u21bb Actualizar BD';
  }}
}}

// --- Select Excel & replace DB ---

function onFileSelected() {{
  const f = document.getElementById('xlsxFile').files[0];
  document.getElementById('xlsx-name').textContent =
    f ? f.name : '\u2014 ning\u00fan archivo seleccionado';
  document.getElementById('btn-reset').disabled = !f;
}}

async function resetFromExcel() {{
  const file = document.getElementById('xlsxFile').files[0];
  if (!file) return;
  const btn    = document.getElementById('btn-reset');
  const status = document.getElementById('upd-status');
  btn.disabled    = true;
  btn.textContent = '\u23f3 Procesando...';
  status.textContent = '';
  const fd = new FormData();
  fd.append('file', file);
  try {{
    const res = await fetch('/api/reset', {{ method: 'POST', body: fd }});
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    if (data.status === 'error') throw new Error(data.message);
    status.textContent = '\u2713 BD reemplazada \u2014 ' + data.total + ' ensayos \u2014 recargando...';
    setTimeout(() => location.reload(), 800);
  }} catch(e) {{
    const msg = e.message || '';
    if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg === 'HTTP 404') {{
      status.textContent = '\u26a0\ufe0f Inicia: python serve_proctor.py';
    }} else {{
      status.textContent = '\u2717 ' + msg.slice(0, 60);
    }}
    btn.disabled    = false;
    btn.textContent = '\u26a0 Reemplazar BD';
  }}
}}

// --- Build capas dropdown (multi-select) ---

function updateCapasCount() {{
  const checked = CAPAS_LIST.filter(c => document.getElementById('chk-capa-' + c).checked).length;
  const countEl = document.getElementById('capas-count');
  if (checked === CAPAS_LIST.length) {{
    countEl.textContent = 'Todas las capas';
  }} else if (checked === 0) {{
    countEl.textContent = 'Sin capas seleccionadas';
  }} else {{
    countEl.textContent = checked + ' seleccionada' + (checked === 1 ? '' : 's');
  }}
}}

function renderCapas() {{
  const container = document.getElementById('capas-list');
  container.innerHTML = '';
  CAPAS_LIST.forEach(c => {{
    const lbl = document.createElement('label');
    lbl.className = 'cl';
    lbl.style.cssText = 'margin:0;padding:6px 8px;font-size:.82rem;display:flex;align-items:center;gap:6px;cursor:pointer;border-radius:3px;transition:background .1s';
    lbl.onmouseover = () => lbl.style.background = '#f5f5f5';
    lbl.onmouseout = () => lbl.style.background = 'transparent';
    lbl.innerHTML = `
      <input type="checkbox" id="chk-capa-${{c}}" checked style="cursor:pointer;width:16px;height:16px">
      <span>${{c}}</span>
    `;
    container.appendChild(lbl);
    const chk = document.getElementById('chk-capa-' + c);
    chk.addEventListener('change', () => {{
      updateCapasCount();
      update();
    }});
  }});
  updateCapasCount();
}}

function toggleCapasDropdown() {{
  const dropdown = document.getElementById('capas-dropdown');
  const isHidden = dropdown.style.display === 'none';
  dropdown.style.display = isHidden ? 'block' : 'none';
}}

function toggleAllCapas() {{
  const allChecked = CAPAS_LIST.every(c => document.getElementById('chk-capa-' + c).checked);
  CAPAS_LIST.forEach(c => {{
    document.getElementById('chk-capa-' + c).checked = !allChecked;
  }});
  updateCapasCount();
  update();
}}

// --- Init ---
renderCapas();
['dfrom','dto','prmin','prmax','chkqa','chkqc'].forEach(id =>
  document.getElementById(id).addEventListener('change', update)
);

update();
</script>
</body>
</html>"""
    # ------------------------------------------------------------------

    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Dashboard: {html_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description='Process Proctor test results')
    p.add_argument('--xlsx', default=DEFAULT_XLSX, help='Excel file path')
    p.add_argument('--db',   default=DEFAULT_DB,   help='CSV database path')
    p.add_argument('--html', default=DEFAULT_HTML, help='HTML output path')
    args = p.parse_args()

    print("Loading Excel...")
    new_df = load_xlsx(args.xlsx)
    print(f"  Found {len(new_df)} valid test(s) in spreadsheet.")

    if new_df.empty:
        print("No valid tests found. Exiting.")
        return

    print("Updating database...")
    db_df = update_db(new_df, args.db)

    print("Generating dashboard...")
    generate_html(db_df, args.html)

    print("Done.")


if __name__ == '__main__':
    main()
