import pytest

import db
import ontvanger

serial = pytest.importorskip("serial")


@pytest.fixture
def conn(tmp_path):
    verbinding = db.verbind(str(tmp_path / "test.db"))
    yield verbinding
    verbinding.close()


def aantal(conn):
    return conn.execute("SELECT COUNT(*) FROM metingen").fetchone()[0]


# ---- parse_regel: validatie van wat de Arduino stuurt (F2, F3) ----------------------------

@pytest.mark.parametrize("regel, verwacht", [
    ("21.4,55.0", (21.4, 55.0)),
    ("21.40,55.00\r\n", (21.4, 55.0)),      # newline / carriage return erachter
    ("  -5.5,0.0  ", (-5.5, 0.0)),
    ("80,100", (80.0, 100.0)),              # randen van het bereik
    ("-40,0", (-40.0, 0.0)),
])
def test_geldige_regels(regel, verwacht):
    assert ontvanger.parse_regel(regel) == verwacht


@pytest.mark.parametrize("regel", [
    "", "abc", "21.4", "21.4,", ",55.0", "21.4,55.0,1",   # verkeerde vorm
    "nan,55.0", "21.4,nan", "inf,55.0", "21.4,-inf",       # geen echte getallen
    "80.1,50", "-40.1,50", "21.4,100.1", "21.4,-0.1",       # buiten het bereik
    "21,4;55,0",                                            # verkeerde scheidingstekens
])
def test_ongeldige_regels(regel):
    assert ontvanger.parse_regel(regel) is None


# ---- verwerk_regel: alleen geldige metingen worden opgeslagen (F4) -------------------------

def test_geldige_regel_wordt_opgeslagen(conn):
    assert ontvanger.verwerk_regel(conn, "21.4,55.0") is True
    rij = db.laatste(conn)
    assert (rij["temperatuur"], rij["luchtvochtigheid"]) == (21.4, 55.0)
    assert len(rij["tijdstempel"]) == 19   # YYYY-MM-DD HH:MM:SS


def test_ongeldige_regel_wordt_niet_opgeslagen(conn):
    assert ontvanger.verwerk_regel(conn, "abc") is False
    assert aantal(conn) == 0


# ---- F7: herstel als de verbinding wegvalt -------------------------------------------------

class NepSeriele:
    """Doet alsof het een seriele poort is. Elk item is bytes (een regel) of een fout."""

    def __init__(self, items, stop):
        self.items, self.stop = list(items), stop

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def reset_input_buffer(self):
        pass

    def readline(self):
        if not self.items:
            self.stop["nu"] = True
            return b""
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_herstel_na_wegvallen_kabel(conn):
    stop = {"nu": False}
    verbindingen = [
        NepSeriele([b"21.4,55.0\n", serial.SerialException("kabel eruit")], stop),  # valt weg
        NepSeriele([b"rommel\n", b"22.0,50.0\n"], stop),                            # herstelt
    ]
    pogingen, slaap_tijden = [], []

    def opener(naam):
        pogingen.append(naam)
        return verbindingen.pop(0)

    ontvanger.lees_seriel("COM3", conn, opener=opener, slaap=slaap_tijden.append, stop=lambda: stop["nu"])

    assert pogingen == ["COM3", "COM3"]                       # er is opnieuw verbonden
    assert ontvanger.HERSTEL_WACHTTIJD_S in slaap_tijden      # en eerst even gewacht
    assert [r[0] for r in conn.execute("SELECT temperatuur FROM metingen ORDER BY id")] == [21.4, 22.0]


def test_herstel_als_poort_er_niet_is(conn):
    stop = {"nu": False}
    pogingen = []

    def opener(naam):
        pogingen.append(1)
        if len(pogingen) < 3:
            raise serial.SerialException("could not open port")
        return NepSeriele([b"20.0,40.0\n"], stop)

    ontvanger.lees_seriel("COM9", conn, opener=opener, slaap=lambda s: None, stop=lambda: stop["nu"])

    assert len(pogingen) == 3          # twee keer mislukt, derde keer gelukt
    assert aantal(conn) == 1
