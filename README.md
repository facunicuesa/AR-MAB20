# AR-MAB20 Proctor Test Dashboard

Interactive web dashboard for processing and visualizing Proctor test results from the Rio Tinto Rincón mining project (M-AB20).

**Live Demo**: https://facunics.pythonanywhere.com

## Quick Start

### Local (30 seconds)
```bash
git clone https://github.com/facunicuesa/AR-MAB20.git
cd AR-MAB20
pip install -r requirements.txt
python serve_proctor.py
# Open http://localhost:5000
```

### Online (PythonAnywhere)
Already deployed! Visit: https://facunics.pythonanywhere.com

---

## Features

### 📊 Data Processing
- Load Proctor test data from Excel spreadsheets (`M-AB20-CS-E.V-Muro-Proctor.xlsx`)
- Automatic database updates (incremental or full reset)
- CSV database for persistent storage
- Fallback to CSV database if Excel file unavailable (useful for cloud deployment)

### 📈 Interactive Dashboard
- **Proctor Curves**: Plot W (humidity) vs D (density) for each test
- **Curve Fitting Options**:
  - None (raw points only)
  - Smoothed (Gaussian filter)
  - Cubic Spline interpolation
  - Parabolic (unconstrained, degree 2)
  - Parabolic (vertex constrained at w_opt, d_max)
- **Histograms**:
  - D_max distribution with configurable bins
  - W_opt distribution with configurable bins
- **Smoothed curves** for better visualization

### 🎛️ Advanced Filtering
- **Date Range**: Select "Todas" or pick date range
- **Progressive Range (Pr)**: Filter by chainage/progression
- **Layers (Capas)**: Multi-select dropdown with "Todas" toggle
- **QA/QC Filter**: Show/hide QA tests, QC tests, or both
- **Individual Tests**: Toggle visibility per test via legend
- **Real-time Updates**: All filters work independently and instantly

### 💾 Database Management
- **"Actualizar BD"** button: Incremental update from source Excel
- **"Reemplazar BD"** button: Upload new Excel to reset database
- Automatic dashboard regeneration after each update

### 📤 Export
- **High-resolution PNG exports** (300+ DPI quality)
- Export each plot separately
- Maintain all filter selections in export

---

## Project Structure

```
AR-MAB20/
├── process_proctor.py         # Core data processing & HTML generation
├── serve_proctor.py           # Flask web server
├── update_and_view.py         # CLI tool for local updates
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── .gitignore                 # Git ignore rules
└── proctor_data/
    ├── proctor_db.csv         # Test database (auto-generated, version-controlled)
    └── proctor_dashboard.html # Dashboard HTML (auto-generated, not version-controlled)
```

---

## Installation

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- Git

### Local Setup

1. **Clone repository**
   ```bash
   git clone https://github.com/facunicuesa/AR-MAB20.git
   cd AR-MAB20
   ```

2. **Create virtual environment** (recommended)
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run**
   ```bash
   python serve_proctor.py
   ```
   Open: http://localhost:5000

---

## Usage

### Option 1: Web Server (Recommended)

```bash
python serve_proctor.py
```

Server runs on `http://localhost:5000` with endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | View dashboard HTML |
| `/api/update` | POST | Incremental update from Excel |
| `/api/reset` | POST | Full database reset with file upload |

**Dashboard Features**:
- Interactive plots with hover details
- Real-time filtering
- Export buttons for each plot
- Database management buttons

### Option 2: CLI Tool

```bash
python update_and_view.py
```

Menu-driven interface with options to:
1. Update database (add new tests from Excel)
2. Reset database (replace all tests)
3. View dashboard in default browser

### Option 3: Python API

```python
import pandas as pd
from process_proctor import load_xlsx, update_db, generate_html

# Load from Excel
new_tests_df = load_xlsx("path/to/M-AB20-CS-E.V-Muro-Proctor.xlsx")

# Update CSV database
updated_db = update_db(new_tests_df, "proctor_data/proctor_db.csv")

# Generate HTML dashboard
generate_html(updated_db, "proctor_data/proctor_dashboard.html")
```

---

## Configuration

### Excel File Path

Set the Excel file path via environment variable:

```bash
# Windows
set EXCEL_PATH=C:\Users\...\M-AB20-CS-E.V-Muro-Proctor.xlsx

# Linux/macOS
export EXCEL_PATH=/path/to/M-AB20-CS-E.V-Muro-Proctor.xlsx
```

Or in `.env` file:
```
EXCEL_PATH=/path/to/excel/file.xlsx
```

### Excel Format Requirements

The source Excel file must have:
- Sheet name: `Estructural`
- Columns: `QA/QC`, `Nº Ensayo`, `Fecha`, `Capa`, `Progresiva`, `Granulometría`
- Density points: 5 columns with densidad values
- Humidity points: 5 columns with humedad values
- Optimal values: `Optimo` column with density and humidity

### Server Configuration

```bash
# Set Flask port
export PORT=5000

# Enable debug mode
export FLASK_DEBUG=False
```

---

## Deployment

### PythonAnywhere (Recommended) ✅ Already Deployed

Live at: https://facunics.pythonanywhere.com

For new deployments:

1. Create account at https://www.pythonanywhere.com
2. Clone repo in Bash console:
   ```bash
   cd /home/YOUR_USERNAME
   git clone https://github.com/facunicuesa/AR-MAB20.git
   cd AR-MAB20
   ```
3. Create virtual environment:
   ```bash
   python3.11 -m venv ~/.virtualenvs/proctor-env
   source ~/.virtualenvs/proctor-env/bin/activate
   pip install -r requirements.txt
   ```
4. Configure WSGI file in Web settings:
   ```python
   import sys, os
   path = '/home/YOUR_USERNAME/AR-MAB20'
   if path not in sys.path:
       sys.path.append(path)
   os.environ['EXCEL_PATH'] = '/home/YOUR_USERNAME/AR-MAB20/proctor_data/proctor_db.csv'
   from serve_proctor import app as application
   ```
5. Set Virtualenv to: `/home/YOUR_USERNAME/.virtualenvs/proctor-env`
6. Reload web app
7. Access at: `https://YOUR_USERNAME.pythonanywhere.com`

**Note**: On PythonAnywhere, the app loads from the CSV database since Excel files are stored locally on Windows. Update the DB using the dashboard buttons.

### Other Platforms

- **Heroku**: Use `gunicorn serve_proctor:app` with Procfile
- **Docker**: Containerize with `python:3.11-slim`
- **Local Server**: Run on always-on Windows machine with `python serve_proctor.py`
- **AWS/Google Cloud**: Deploy as serverless function or App Engine

---

## Data Format

### CSV Database Schema

Generated in `proctor_data/proctor_db.csv`:

```
id           | Test ID (e.g., TEC-PRO200, MIL-PRO201)
d            | Density points [d1, d2, d3, d4, d5] (list as JSON)
w            | Humidity points [w1, w2, w3, w4, w5] (list as JSON)
d_max        | Maximum density (from Optimo)
w_opt        | Optimal humidity (from Optimo)
fecha        | Test date (format: M/D/YYYY)
capa         | Layer number
pr_0         | Initial progressive distance
pr_1         | Final progressive distance
gra          | Granulometry code (e.g., GRA150)
qa_qc        | QA or QC designation
```

### Test ID Format

Format: `[QA/QC PREFIX]-[TEST NUMBER]`

- **QA tests**: `TEC-PRO###` (from "QA" column)
- **QC tests**: `MIL-PRO###` (from "QC" column)

Example: `TEC-PRO200`, `MIL-PRO201`

---

## Technical Details

### Curve Fitting Methods

All methods use least-squares optimization:

1. **No Fit** - Raw data points only, no interpolation
2. **Smoothed** - Gaussian filter (σ=2) applied to smooth noisy data
3. **Spline** - Cubic spline interpolation, smooth continuous curve
4. **Parabolic (Free)** - Unconstrained polynomial fit (degree 2)
   - `y = ax² + bx + c`
   - Vertex can be anywhere
5. **Parabolic (Centered)** - Constrained parabola
   - Vertex fixed at (w_opt, d_max)
   - Better for geotechnical interpretation

### Dependencies

```
pandas>=2.0.0          # Data manipulation
openpyxl>=3.0.0        # Excel reading
numpy>=1.20.0          # Numerical computing
scipy>=1.7.0           # Scientific computing (interpolation, optimization)
flask>=2.2.0           # Web framework
gunicorn>=20.0.0       # Production WSGI server (PythonAnywhere)
matplotlib>=3.5.0      # Plotting (used internally)
```

### Performance Notes

- Dashboard regeneration: ~100ms for 10 tests
- Plot rendering: Real-time (WebGL-accelerated in modern browsers)
- Database operations: <50ms for CRUD
- Memory usage: ~50MB with 100 tests

---

## Troubleshooting

### "Excel file not found"
**Cause**: Source Excel not accessible (common on cloud servers)
**Solution**:
- Upload file via "Reemplazar BD" button in dashboard
- Or set correct path in `EXCEL_PATH` environment variable
- App automatically falls back to CSV database if Excel unavailable

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt --upgrade
```

### "Dashboard not loading" (PythonAnywhere)
1. Check error log in Web settings
2. Verify virtual environment is set correctly
3. Ensure `proctor_db.csv` exists (create empty one if needed)
4. Click "Reload" button

### Plots not rendering
- Ensure JavaScript is enabled
- Try hard refresh: `Ctrl+Shift+R`
- Check browser console for errors (F12)

### Export button not working
- Check browser console (F12) for errors
- Verify browser allows downloads
- Try different export format

---

## Contributing

Issues and feature requests welcome!

1. Fork repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature/your-feature`
5. Submit pull request

---

## License

Internal SRK Consulting project. All rights reserved.

---

## Contact

**Project**: AR M-A610 Rio Tinto - Rincón
**Client**: Rio Tinto
**Organization**: SRK Consulting
**Status**: Production

For support or questions, contact the project team.

---

**Last Updated**: March 22, 2026
**Version**: 1.0
**Python**: 3.8+
**Status**: ✅ Production Ready
