#!/usr/bin/env python3
"""Lightweight local server for the Proctor dashboard.

Usage:
    pip install flask           # one-time setup
    python serve_proctor.py     # then open  http://localhost:5000

Endpoints:
    GET  /            — serve the dashboard HTML
    POST /api/update  — incremental update (adds new tests from Excel)
    POST /api/reset   — replace DB with uploaded .xlsx file
"""
import os
import sys
import traceback
import tempfile

try:
    from flask import Flask, send_file, jsonify, request
except ImportError:
    sys.exit(
        "\n  Flask is not installed.\n"
        "  Run:  pip install flask\n"
        "  Then re-run this script.\n"
    )

from process_proctor import (
    load_xlsx,
    update_db,
    generate_html,
    DEFAULT_XLSX,
    DEFAULT_DB,
    DEFAULT_HTML,
)

app = Flask(__name__, static_folder=None)


@app.route('/')
def index():
    if not os.path.exists(DEFAULT_HTML):
        return (
            "<h3>Dashboard not found.</h3>"
            "<p>Run <code>python process_proctor.py</code> first, then refresh.</p>",
            404,
        )
    return send_file(DEFAULT_HTML)


@app.route('/api/update', methods=['POST'])
def api_update():
    """Incremental update — reads DEFAULT_XLSX, adds tests not yet in DB."""
    try:
        print("[update] Reading Excel ...")
        new_df = load_xlsx(DEFAULT_XLSX)
        print(f"[update] Found {len(new_df)} valid test(s).")
        db_df  = update_db(new_df, DEFAULT_DB)
        generate_html(db_df, DEFAULT_HTML)
        print(f"[update] Done. Total: {len(db_df)} test(s).")
        return jsonify({'status': 'ok', 'total': len(db_df)})
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(exc)}), 500


@app.route('/api/reset', methods=['POST'])
def api_reset():
    """Replace DB — accepts an uploaded .xlsx file, wipes existing DB, rebuilds."""
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400

    uploaded = request.files['file']
    if not uploaded.filename.lower().endswith('.xlsx'):
        return jsonify({'status': 'error', 'message': 'File must be .xlsx'}), 400

    tmp_path = None
    try:
        # Save upload to a temp file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            tmp_path = tmp.name
            uploaded.save(tmp_path)

        print(f"[reset] Reading uploaded file: {uploaded.filename}")
        new_df = load_xlsx(tmp_path)
        print(f"[reset] Found {len(new_df)} valid test(s).")

        # Wipe existing DB
        if os.path.exists(DEFAULT_DB):
            os.remove(DEFAULT_DB)
            print("[reset] Existing DB removed.")

        db_df = update_db(new_df, DEFAULT_DB)
        generate_html(db_df, DEFAULT_HTML)
        print(f"[reset] Done. Total: {len(db_df)} test(s).")
        return jsonify({'status': 'ok', 'total': len(db_df)})

    except Exception as exc:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(exc)}), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n  Proctor Dashboard -> http://localhost:{port}")
    print("  Press Ctrl+C to stop.\n")
    app.run(debug=False, host='127.0.0.1', port=port)
