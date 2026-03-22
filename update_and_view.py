#!/usr/bin/env python3
"""
Quick update & view script for Proctor dashboard.
Loads Excel → Updates/resets database → Regenerates HTML → Opens in browser
"""
import os
import sys
import webbrowser
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("\n  pandas is not installed.\n  Run:  pip install pandas openpyxl\n")

from process_proctor import (
    load_xlsx,
    update_db,
    generate_html,
    DEFAULT_XLSX,
    DEFAULT_DB,
    DEFAULT_HTML,
)

def main():
    print("\n" + "="*60)
    print("  Proctor Dashboard — Update & View")
    print("="*60)

    # Ask user what to do
    print("\nOptions:")
    print("  1) Update database (add new tests from Excel)")
    print("  2) Reset database (replace with fresh Excel data)")
    print("  3) Just view the dashboard")

    choice = input("\nChoice (1/2/3): ").strip()

    if choice in ['1', '2']:
        print(f"\nLoading Excel: {DEFAULT_XLSX}")
        try:
            new_df = load_xlsx(DEFAULT_XLSX)
            print(f"  Found {len(new_df)} valid test(s)")
        except FileNotFoundError:
            print(f"  ❌ Excel file not found: {DEFAULT_XLSX}")
            return
        except Exception as e:
            print(f"  ❌ Error loading Excel: {e}")
            return

        if new_df.empty:
            print("  ❌ No valid tests found in Excel")
            return

        if choice == '2':
            # Reset mode
            if os.path.exists(DEFAULT_DB):
                os.remove(DEFAULT_DB)
                print("  ✓ Existing database removed")

        # Update/create database
        print("Updating database...")
        try:
            db_df = update_db(new_df, DEFAULT_DB)
            print(f"  ✓ Database ready: {len(db_df)} test(s) total")
        except Exception as e:
            print(f"  ❌ Error updating database: {e}")
            return

        # Regenerate HTML
        print("Regenerating dashboard...")
        try:
            generate_html(db_df, DEFAULT_HTML)
            print(f"  ✓ Dashboard: {DEFAULT_HTML}")
        except Exception as e:
            print(f"  ❌ Error generating HTML: {e}")
            return

    # Open in browser
    print(f"\nOpening dashboard...")
    html_path = Path(DEFAULT_HTML).resolve()
    webbrowser.open('file://' + str(html_path))
    print(f"  ✓ Opened in browser")
    print("\n" + "="*60 + "\n")

if __name__ == '__main__':
    main()
