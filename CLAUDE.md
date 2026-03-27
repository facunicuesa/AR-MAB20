# CLAUDE.md — AR-MAB20 Proctor Dashboard

## Project Overview

Proctor test results processing and visualization dashboard for **Rio Tinto Rincón** mining project (M-AB20), developed for **SRK Consulting**.

- **Live URL**: https://facunics.pythonanywhere.com
- **GitHub**: https://github.com/facunicuesa/AR-MAB20
- **Local path**: `~/Documents/Git/AR-MAB20`
- **Status**: Production ✅

---

## Architecture

### Files

| File | Purpose |
|------|---------|
| `process_proctor.py` | Core engine: reads Excel, builds CSV DB, generates HTML dashboard |
| `serve_proctor.py` | Flask server with API endpoints (`/`, `/api/update`, `/api/reset`) |
| `update_and_view.py` | CLI tool to update DB and open browser (no server needed) |
| `proctor_data/proctor_db.csv` | CSV database (version-controlled, empty when no tests) |
| `proctor_data/proctor_dashboard.html` | Generated HTML dashboard (NOT version-controlled) |
| `proctor_data/assets/srk_logo.png` | SRK Consulting logo (version-controlled) |

### Key Functions in `process_proctor.py`

- `load_xlsx(path)` → reads Excel sheet `Estructural`, returns DataFrame
- `update_db(new_df, db_path)` → incremental update, skips duplicates by ID
- `generate_html(df, html_path)` → produces standalone self-contained HTML
- `_smooth_curve(w, d, w_opt, d_max)` → returns 5 curve fit arrays
- `main()` → CLI entry point

---

## Data Model

### Test ID Format
`TEC-PRO###` (QA tests) or `MIL-PRO###` (QC tests)

### CSV Schema
```
id, nro_ensayo, material, origen, capa, pr_0, pr_1, gra, qa_qc, fecha,
d1, d2, d3, d4, d5,   ← density points
w1, w2, w3, w4, w5,   ← humidity points
d_max, w_opt
```

### Excel Source
```
Path: C:\Users\fnicuesa\SRK Consulting\AR M-A610 Rio Tinto - Rincon - Documentos\
      M-AB20 - RFP SBDF Cell A SD CQA\!WIP\T03 QA\02 Ensayos in-situ\
      02 Ensayos Proctor\M-AB20-CS-E.V-Muro-Proctor.xlsx
Sheet: Estructural
```

---

## Dashboard Features

### Proctor Curve Plot
- W (humedad %) on X axis, D (densidad seca g/cm³) on Y axis
- 5 curve fitting modes: None / Smoothed / Spline / Parabolic libre / Parabolic centrado
- Parabolic centrado: vertex constrained at (w_opt, d_max), least squares
- QA = solid lines, QC = dashed lines, optimum = star marker

### Filters
- Date range (with "Todos" toggle)
- Progresiva range Pr_0 → Pr_1 (with "Todos" toggle)
- Capas: multi-select dropdown (shows "X seleccionadas")
- QA/QC checkboxes
- Individual test toggle via legend

### Histograms
- D_max distribution
- W_opt distribution
- Configurable bins (number or width)
- Selectable date range

### Export
- High-res PNG for each plot separately

### DB Buttons
- **Actualizar BD**: incremental update from source Excel (requires Flask server)
- **Reemplazar BD**: upload new Excel file to reset DB (requires Flask server)

---

## Workflow

### Local development
```bash
# Update DB + regenerate HTML
python process_proctor.py

# Start local server (http://localhost:5000)
python serve_proctor.py

# CLI tool (no server)
python update_and_view.py
```

### Deploy to PythonAnywhere
```bash
# 1. Push changes locally
git add -A
git commit -m "..."
git push origin main

# 2. Pull on PythonAnywhere (Bash console)
cd /home/facunics/AR-MAB20
git pull origin main

# 3. Regenerate HTML if needed
source /home/facunics/.virtualenvs/proctor-env/bin/activate
python process_proctor.py

# 4. Reload web app (Web tab → Reload button)
```

---

## PythonAnywhere Config

| Setting | Value |
|---------|-------|
| Username | `facunics` |
| Python | 3.11 |
| Virtualenv | `/home/facunics/.virtualenvs/proctor-env` |
| Source code | `/home/facunics/AR-MAB20` |
| WSGI file | `/var/www/facunics_pythonanywhere_com_wsgi.py` |

### WSGI file content
```python
import sys, os
path = '/home/facunics/AR-MAB20'
if path not in sys.path:
    sys.path.append(path)
os.environ['EXCEL_PATH'] = '/home/facunics/AR-MAB20/proctor_data/proctor_db.csv'
from serve_proctor import app as application
from process_proctor import generate_html, DEFAULT_DB, DEFAULT_HTML
if not os.path.exists(DEFAULT_HTML):
    try:
        import pandas as pd
        if os.path.exists(DEFAULT_DB):
            generate_html(pd.read_csv(DEFAULT_DB), DEFAULT_HTML)
    except Exception as e:
        print(f"Could not generate dashboard: {e}")
```

---

## Design / Branding

### SRK Consulting Color Palette
| Color | Hex | Use |
|-------|-----|-----|
| Naranja SRK | `#F37021` | Primary, buttons, accents, card borders, stats |
| Dark | `#2c2c2c` | Header background, body text |
| Grey | `#666666` | Secondary text, labels |
| Cream | `#F3F2E5` | Page background |
| White | `#FFFFFF` | Cards, inputs |

### Logo
Embedded as base64 PNG in HTML header (`proctor_data/assets/srk_logo.png`).
Displayed white (inverted) on dark header via CSS `filter: brightness(0) invert(1)`.

---

## Dependencies
```
pandas>=2.0.0
openpyxl>=3.0.0
numpy>=1.20.0
scipy>=1.7.0
flask>=2.2.0
gunicorn>=20.0.0
```

---

## Important Notes

- The HTML dashboard is a **standalone self-contained file** — all JS/CSS/data embedded inline.
- The Excel file is only accessible locally (Windows path). On PythonAnywhere, the app falls back to the CSV database.
- Always regenerate the HTML after modifying `process_proctor.py`.
- The `proctor_dashboard.html` is in `.gitignore` — only the CSV and Python source are version-controlled.
- `proctor_db.csv` IS version-controlled (empty baseline committed for cloud deployment).
