"""Gedeelde databasefuncties voor de ontvanger en het dashboard (SQLite).

Alle queries gebruiken parameters (?), zodat SQL-injectie niet mogelijk is.
"""
import sqlite3
from datetime import datetime, timedelta

STANDAARD_DB = "metingen.db"
TIJDFORMAAT = "%Y-%m-%d %H:%M:%S"

SCHEMA = """
CREATE TABLE IF NOT EXISTS metingen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tijdstempel TEXT NOT NULL,
    temperatuur REAL NOT NULL,
    luchtvochtigheid REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metingen_tijdstempel ON metingen (tijdstempel);
"""


def verbind(pad=STANDAARD_DB):
    """Open de database. WAL zorgt dat het dashboard kan lezen terwijl de ontvanger schrijft."""
    conn = sqlite3.connect(pad, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def nu():
    return datetime.now().strftime(TIJDFORMAAT)


def _grens(uren):
    return (datetime.now() - timedelta(hours=uren)).strftime(TIJDFORMAAT)


def voeg_toe(conn, temperatuur, luchtvochtigheid, tijdstempel=None):
    """F4: sla een meting met tijdstempel op."""
    conn.execute(
        "INSERT INTO metingen (tijdstempel, temperatuur, luchtvochtigheid) VALUES (?, ?, ?)",
        (tijdstempel or nu(), temperatuur, luchtvochtigheid),
    )
    conn.commit()


def laatste(conn):
    """De nieuwste meting, of None als er nog niets is."""
    rij = conn.execute(
        "SELECT tijdstempel, temperatuur, luchtvochtigheid FROM metingen ORDER BY tijdstempel DESC, id DESC LIMIT 1"
    ).fetchone()
    return dict(rij) if rij else None


def min_max(conn, uren=24):
    """F6: minimum en maximum van de afgelopen `uren` uur."""
    rij = conn.execute(
        """SELECT COUNT(*) AS aantal,
                  MIN(temperatuur) AS temp_min, MAX(temperatuur) AS temp_max,
                  MIN(luchtvochtigheid) AS vocht_min, MAX(luchtvochtigheid) AS vocht_max
           FROM metingen WHERE tijdstempel >= ?""",
        (_grens(uren),),
    ).fetchone()
    return dict(rij)


def verloop(conn, uren=24, max_punten=500):
    """F5: gemiddelde per tijdvak, zodat de grafiek nooit veel meer dan max_punten punten krijgt."""
    seconden = max(1, -(-uren * 3600 // max_punten))  # naar boven afronden
    rijen = conn.execute(
        """SELECT MIN(tijdstempel) AS tijdstempel,
                  AVG(temperatuur) AS temperatuur,
                  AVG(luchtvochtigheid) AS luchtvochtigheid
           FROM metingen WHERE tijdstempel >= ?
           GROUP BY CAST(strftime('%s', tijdstempel) AS INTEGER) / ?
           ORDER BY MIN(tijdstempel)""",
        (_grens(uren), seconden),
    ).fetchall()
    return [
        {
            "tijdstempel": r["tijdstempel"],
            "temperatuur": round(r["temperatuur"], 2),
            "luchtvochtigheid": round(r["luchtvochtigheid"], 2),
        }
        for r in rijen
    ]


def alle_metingen(conn):
    """F8: alle metingen op volgorde van tijd (voor de CSV-export)."""
    return conn.execute(
        "SELECT tijdstempel, temperatuur, luchtvochtigheid FROM metingen ORDER BY id"
    )
