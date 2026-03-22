# AR-MAB20 Proctor Test Dashboard

Interactive web dashboard for processing and visualizing Proctor test results from Rio Tinto Rincon mining project.

## Features

✅ **Data Processing**
- Load Proctor test data from Excel spreadsheets
- Automatic database updates (incremental or reset)
- CSV database for persistent storage

✅ **Interactive Dashboard**
- Dynamic Proctor curve plots (W vs D)
- Customizable curve fits: None, Smoothed, Spline, Parabolic (free & centered)
- Histogram analysis for D_max and W_opt
- Configurable bin widths and date ranges

✅ **Advanced Filtering**
- Filter by date range
- Filter by progressive range (Pr_0, Pr_1)
- Filter by layer (Capa) with multi-select dropdown
- Toggle QA/QC tests on/off
- Individual test visibility control

✅ **Export**
- High-resolution PNG exports of each plot
- Download plots separately or in batch

## Project Structure

```
AR-MAB20/
├── process_proctor.py      # Core data processing engine
├── serve_proctor.py         # Flask web server
├── update_and_view.py       # CLI tool for local updates
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── .gitignore              # Git ignore rules
└── proctor_data/
    ├── proctor_db.csv      # Test database (generated)
    └── proctor_dashboard.html  # Dashboard (generated)
```

## Installation

### Local Setup (Windows/macOS/Linux)

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/AR-MAB20-Proctor-Dashboard.git
   cd AR-MAB20-Proctor-Dashboard
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

## Usage

### Option 1: Interactive CLI (Recommended for beginners)
```bash
python update_and_view.py
```
Menu-driven interface with options to:
- Update database from Excel
- Reset database
- View dashboard in browser

### Option 2: Web Server
```bash
python serve_proctor.py
```
Server runs on `http://localhost:5000`

Endpoints:
- `GET /` - View dashboard
- `POST /api/update` - Incremental update from Excel
- `POST /api/reset` - Full database reset with file upload

### Option 3: Direct Processing
```python
import pandas as pd
from process_proctor import load_excel_file, update_database, generate_html

# Load from Excel
tests_df = load_excel_file("path/to/excel.xlsx")

# Update database
update_database(tests_df, "proctor_data/proctor_db.csv")

# Generate HTML dashboard
generate_html(tests_df, "proctor_data/proctor_dashboard.html")
```

## Configuration

### Environment Variables

Set these in your environment or `.env` file:

```bash
# Path to source Excel file
EXCEL_PATH=/path/to/M-AB20-CS-E.V-Muro-Proctor.xlsx

# Flask port (optional)
FLASK_PORT=5000

# Debug mode (optional)
FLASK_DEBUG=False
```

### Excel File Location

The script expects test data in a specific Excel format with columns:
- `QA/QC` - Test type (QA/QC)
- `Nº Ensayo` - Test number
- `Fecha` - Date of test
- `Capa` - Layer/level
- `Progresiva` - Progressive distance
- `Granulometría` - Granulometry
- `Densidad` values (5 columns)
- `Humedad` values (5 columns)
- `Optimo` - Optimal values
- And other material/origin columns

## Deployment

### PythonAnywhere (Recommended)

1. **Create PythonAnywhere account**: https://www.pythonanywhere.com
2. **Link GitHub**: Account settings → GitHub integration
3. **Create Web App**: Flask + Python 3.11
4. **Clone repo in bash console**:
   ```bash
   cd /home/YOUR_USERNAME
   git clone https://github.com/YOUR_USERNAME/AR-MAB20-Proctor-Dashboard.git
   ```
5. **Install dependencies**:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.11 proctor-env
   pip install -r requirements.txt
   ```
6. **Configure WSGI file** (`/var/www/YOUR_USERNAME_pythonanywhere_com_wsgi.py`):
   ```python
   import sys
   path = '/home/YOUR_USERNAME/AR-MAB20-Proctor-Dashboard'
   if path not in sys.path:
       sys.path.append(path)
   from serve_proctor import app as application
   ```
7. **Set environment variables** in Web app settings
8. **Reload** web app
9. **Access** at: `https://YOUR_USERNAME.pythonanywhere.com`

### Other Platforms

- **Heroku**: Use `Procfile` with `gunicorn serve_proctor:app`
- **Google Cloud/AWS**: Docker containerization recommended
- **Local Server**: Run `python serve_proctor.py` on always-on machine

## Data Format

### CSV Database Schema

The generated `proctor_db.csv` contains:

| Column | Type | Description |
|--------|------|-------------|
| id | str | Unique test ID (e.g., TEC-PRO200) |
| fecha | date | Test date |
| nro_ensayo | str | Test number |
| material | str | Material type |
| origen | str | Test origin |
| capa | int | Layer number |
| pr_0 | float | Initial progressive distance |
| pr_1 | float | Final progressive distance |
| gra | str | Granulometry code |
| qa_qc | str | QA or QC designation |
| d1-d5 | float | Density measurements |
| d_max | float | Maximum density |
| w1-w5 | float | Moisture measurements |
| w_opt | float | Optimal moisture |

## Technical Details

### Curve Fitting Methods

1. **No Fit** - Plot raw data points only
2. **Smoothed** - Gaussian filter with σ=2
3. **Spline** - Cubic spline interpolation (K=3)
4. **Parabolic (Free)** - Unconstrained polynomial fit (degree 2)
5. **Parabolic (Centered)** - Vertex constrained at (w_opt, d_max)

### Dependencies

- **pandas** - Data manipulation and CSV I/O
- **openpyxl** - Excel file reading
- **numpy** - Numerical operations
- **scipy** - Interpolation and curve fitting
- **flask** - Web server framework
- **gunicorn** - Production WSGI server

## Troubleshooting

### "Excel file not found"
- Check `EXCEL_PATH` environment variable
- Verify file exists and is accessible
- Try uploading file directly in dashboard

### "Module not found"
```bash
pip install -r requirements.txt
```

### "Permission denied" (PythonAnywhere)
- Ensure directory permissions are set correctly
- Check if Excel file path is accessible

### Dashboard not loading
- Check PythonAnywhere error logs
- Verify dependencies installed in correct virtual environment
- Reload web app

## Contributing

Issues and improvements welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit pull request with description

## License

SRK Consulting internal project

## Contact

For questions or support, contact the project team at SRK Consulting.

---

**Last Updated**: March 2026
**Status**: Production
**Python Version**: 3.8+
