import csv
import io
from datetime import datetime, timedelta

import pytest

import dashboard
import db


@pytest.fixture
def client(tmp_path):
    pad = str(tmp_path / "test.db")
    conn = db.verbind(pad)
    nu = datetime.now()
    # drie metingen in de laatste 24 uur en een van 3 dagen geleden
    db.voeg_toe(conn, 20.0, 40.0, (nu - timedelta(hours=2)).strftime(db.TIJDFORMAAT))
    db.voeg_toe(conn, 23.0, 60.0, (nu - timedelta(hours=1)).strftime(db.TIJDFORMAAT))
    db.voeg_toe(conn, 21.5, 50.0, (nu - timedelta(seconds=5)).strftime(db.TIJDFORMAAT))
    db.voeg_toe(conn, 5.0, 90.0, (nu - timedelta(days=3)).strftime(db.TIJDFORMAAT))
    conn.close()
    return dashboard.maak_app(pad).test_client()


def test_status_laatste_meting_en_min_max(client):
    data = client.get("/api/status").get_json()
    assert data["laatste"]["temperatuur"] == 21.5
    assert data["leeftijd_s"] < 60
    mm = data["min_max"]
    assert mm["aantal"] == 3                                   # de meting van 3 dagen geleden telt niet mee
    assert (mm["temp_min"], mm["temp_max"]) == (20.0, 23.0)
    assert (mm["vocht_min"], mm["vocht_max"]) == (40.0, 60.0)


def test_verloop_geeft_punten_op_volgorde(client):
    punten = client.get("/api/verloop?uren=24").get_json()["punten"]
    assert len(punten) == 3
    assert [p["tijdstempel"] for p in punten] == sorted(p["tijdstempel"] for p in punten)


def test_verloop_uren_wordt_begrensd(client):
    assert client.get("/api/verloop?uren=99999").get_json()["uren"] == 168
    assert client.get("/api/verloop?uren=0").get_json()["uren"] == 1


def test_lege_database(tmp_path):
    klant = dashboard.maak_app(str(tmp_path / "leeg.db")).test_client()
    data = klant.get("/api/status").get_json()
    assert data["laatste"] is None and data["leeftijd_s"] is None
    assert data["min_max"]["aantal"] == 0
    assert klant.get("/api/verloop").get_json()["punten"] == []


def test_csv_export(client):
    antwoord = client.get("/export.csv")
    assert antwoord.mimetype == "text/csv"
    assert "attachment" in antwoord.headers["Content-Disposition"]
    rijen = list(csv.reader(io.StringIO(antwoord.get_data(as_text=True))))
    assert rijen[0] == ["tijdstempel", "temperatuur", "luchtvochtigheid"]
    assert len(rijen) == 1 + 4                                  # kop + alle 4 metingen


def test_hoofdpagina_en_chartjs_zijn_lokaal(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/chart.umd.js").status_code == 200
