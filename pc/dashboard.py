#!/usr/bin/env python3
"""Dashboard: toont de metingen uit de database in de browser.

Gebruik:
    python dashboard.py                       # http://127.0.0.1:5000
    python dashboard.py --db metingen_demo.db # demo-database bekijken

Standaard alleen bereikbaar op deze computer (127.0.0.1). Met --host 0.0.0.0 ook op
het lokale netwerk. Zet dit nooit open naar internet.

Functionele eisen: F5 (grafiek), F6 (laatste meting + min/max 24 uur), F8 (CSV-export).
"""
import argparse
import csv
import io
from datetime import datetime

# pyright: reportMissingImports=false
from flask import Flask, Response, jsonify, render_template, request

import db


def maak_app(db_pad=db.STANDAARD_DB):
    app = Flask(__name__)
    app.config["DB_PAD"] = db_pad

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/status")
    def api_status():
        """Laatste meting, min/max van 24 uur en hoe oud de laatste meting is."""
        conn = db.verbind(app.config["DB_PAD"])
        try:
            laatste = db.laatste(conn)
            min_max = db.min_max(conn, 24)
        finally:
            conn.close()
        leeftijd = None
        if laatste:
            moment = datetime.strptime(laatste["tijdstempel"], db.TIJDFORMAAT)
            leeftijd = max(0, int((datetime.now() - moment).total_seconds()))
        return jsonify(laatste=laatste, min_max=min_max, leeftijd_s=leeftijd)

    @app.route("/api/verloop")
    def api_verloop():
        """Gemiddelden per tijdvak voor de grafiek. ?uren=24 (1 t/m 168)."""
        uren = request.args.get("uren", default=24, type=int)
        uren = min(max(uren, 1), 168)
        conn = db.verbind(app.config["DB_PAD"])
        try:
            punten = db.verloop(conn, uren)
        finally:
            conn.close()
        return jsonify(uren=uren, punten=punten)

    @app.route("/export.csv")
    def export_csv():
        """F8: alle metingen als CSV (tijdstempel, temperatuur, luchtvochtigheid)."""
        def genereer():
            conn = db.verbind(app.config["DB_PAD"])
            try:
                buffer = io.StringIO()
                schrijver = csv.writer(buffer, lineterminator="\n")
                schrijver.writerow(["tijdstempel", "temperatuur", "luchtvochtigheid"])
                yield buffer.getvalue()
                for rij in db.alle_metingen(conn):
                    buffer.seek(0)
                    buffer.truncate()
                    schrijver.writerow([rij["tijdstempel"], rij["temperatuur"], rij["luchtvochtigheid"]])
                    yield buffer.getvalue()
            finally:
                conn.close()

        naam = datetime.now().strftime("metingen_%Y%m%d_%H%M%S.csv")
        return Response(
            genereer(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={naam}"},
        )

    return app


def main():
    parser = argparse.ArgumentParser(description="Dashboard voor de omgevingsmonitor.")
    parser.add_argument("--db", default=db.STANDAARD_DB, help=f"databasebestand (standaard {db.STANDAARD_DB})")
    parser.add_argument("--host", default="127.0.0.1", help="standaard 127.0.0.1 (alleen deze computer)")
    parser.add_argument("--poort", type=int, default=5000)
    args = parser.parse_args()
    maak_app(args.db).run(host=args.host, port=args.poort, debug=False)


if __name__ == "__main__":
    main()
