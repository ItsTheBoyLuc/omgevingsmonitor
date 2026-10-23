# Omgevingsmonitor

Arduino Uno + DHT-sensor -> USB -> Python-ontvanger -> SQLite -> Flask-dashboard (Chart.js).

```
arduino/omgevingsmonitor/omgevingsmonitor.ino   sketch voor de Arduino
pc/ontvanger.py     leest de seriele poort, slaat metingen op (F3, F4, F7)
pc/dashboard.py     webpagina met grafiek, min/max en CSV-export (F5, F6, F8)
pc/db.py            SQLite-functies
pc/tests/           automatische tests (pytest)
```

## Installeren (Windows, eenmalig)

```
cd pc
pip install -r requirements.txt
```

## Gebruiken

1. Zet de sketch op de Arduino (Arduino IDE, `DEBUG` op 0). **Sluit daarna de Seriele monitor**; maar een programma tegelijk mag de poort gebruiken.
2. Terminal 1 (laat open):  `python ontvanger.py`  (zoekt de Arduino zelf; of `python ontvanger.py --poort COM3`)
3. Terminal 2 (laat open):  `python dashboard.py`
4. Open http://127.0.0.1:5000 in de browser.

## Zonder Arduino proberen

```
python ontvanger.py --simulatie --historie-uren 24
python dashboard.py --db metingen_demo.db
```

## Tests

```
cd pc
python -m pytest -q
```

## Sensor

DHT11 (blauw): 0-50 C (+-2 C), 20-80 % RH (+-5 %), hele getallen. DHT22 (wit): zet `DHTTYPE` op `DHT22` in de sketch.

Chart.js 4.4.7 (MIT-licentie) staat lokaal in `pc/static/`, dus het dashboard werkt zonder internet.
