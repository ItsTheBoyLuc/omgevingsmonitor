#!/usr/bin/env python3
"""Ontvanger: leest de metingen van de Arduino (USB-serial) en slaat ze op in SQLite.

Gebruik:
    python ontvanger.py                      # poort automatisch zoeken
    python ontvanger.py --poort COM3         # Windows, vaste poort
    python ontvanger.py --poort /dev/ttyACM0 # Linux
    python ontvanger.py --simulatie          # zonder Arduino testen (eigen demo-database)

Belangrijk: sluit de Seriele Monitor van de Arduino IDE. Een poort kan maar door
een programma tegelijk gebruikt worden.

Functionele eisen: F3 (ontvangen), F4 (opslaan met tijdstempel), F7 (herstel bij wegvallen).
"""
import argparse
import logging
import math
import random
import sys
import time
from datetime import datetime, timedelta

import db

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pyserial is alleen nodig voor de echte Arduino
    serial = None
    list_ports = None

BAUDRATE = 9600            # gelijk aan de Arduino-sketch
HERSTEL_WACHTTIJD_S = 3    # F7: zo lang wachten voor een nieuwe verbindingspoging
TEMP_BEREIK = (-40.0, 80.0)     # bereik van de DHT22 (de DHT11 zit hier ruim binnen)
VOCHT_BEREIK = (0.0, 100.0)

log = logging.getLogger("ontvanger")


def parse_regel(regel):
    """Zet '21.4,55.0' om naar (21.4, 55.0). Geeft None bij een ongeldige regel."""
    delen = regel.strip().split(",")
    if len(delen) != 2:
        return None
    try:
        temperatuur, luchtvochtigheid = float(delen[0]), float(delen[1])
    except ValueError:
        return None
    if not (math.isfinite(temperatuur) and math.isfinite(luchtvochtigheid)):
        return None
    if not (TEMP_BEREIK[0] <= temperatuur <= TEMP_BEREIK[1]):
        return None
    if not (VOCHT_BEREIK[0] <= luchtvochtigheid <= VOCHT_BEREIK[1]):
        return None
    return temperatuur, luchtvochtigheid


def verwerk_regel(conn, regel):
    """Valideer een ontvangen regel en sla hem op. Geeft True als er iets is opgeslagen."""
    meting = parse_regel(regel)
    if meting is None:
        log.warning("Ongeldige regel genegeerd: %r", regel)
        return False
    db.voeg_toe(conn, *meting)
    log.info("Opgeslagen: %.1f C  %.1f %%", *meting)
    return True


def zoek_poort():
    """Zoek automatisch de poort van de Arduino. Geeft None als er niets is gevonden."""
    if list_ports is None:
        return None
    poorten = list(list_ports.comports())
    sleutels = ("arduino", "ch340", "ch341", "usb serial", "usb-serial", "ftdi", "acm")
    for poort in poorten:
        tekst = f"{poort.description} {poort.manufacturer or ''} {poort.device}".lower()
        if any(s in tekst for s in sleutels):
            return poort.device
    if len(poorten) == 1:
        return poorten[0].device
    return None


def lees_seriel(poort, conn, opener=None, slaap=time.sleep, stop=lambda: False):
    """Lees continu van de seriele poort. F7: bij een fout wachten en opnieuw verbinden."""
    opener = opener or (lambda naam: serial.Serial(naam, BAUDRATE, timeout=2))
    while not stop():
        try:
            naam = poort if poort != "auto" else zoek_poort()
            if not naam:
                log.warning("Geen Arduino gevonden. Opnieuw proberen over %d s...", HERSTEL_WACHTTIJD_S)
                slaap(HERSTEL_WACHTTIJD_S)
                continue
            with opener(naam) as ser:
                log.info("Verbonden met %s", naam)
                slaap(2)  # een Arduino Uno herstart als de poort wordt geopend
                if hasattr(ser, "reset_input_buffer"):
                    ser.reset_input_buffer()
                while not stop():
                    regel = ser.readline().decode("ascii", errors="ignore").strip()
                    if regel:  # lege regel = time-out, gewoon doorgaan
                        verwerk_regel(conn, regel)
        except Exception as fout:  # SerialException, OSError: kabel eruit, poort bezet, enzovoort
            log.warning("Verbinding verbroken of niet beschikbaar (%s). Opnieuw proberen over %d s...",
                        fout, HERSTEL_WACHTTIJD_S)
            slaap(HERSTEL_WACHTTIJD_S)


def simuleer(conn, interval, historie_uren=0):
    """Maak nepmetingen (alleen voor testen en demo's, nooit in de echte database)."""
    def waarden(moment):
        uur = moment.hour + moment.minute / 60 + moment.second / 3600
        temperatuur = 21.2 + 1.4 * math.sin(2 * math.pi * uur / 24) + random.uniform(-0.1, 0.1)
        vocht = 54.5 - 6.5 * math.sin(2 * math.pi * uur / 24) + random.uniform(-0.3, 0.3)
        return round(temperatuur, 1), round(vocht, 1)

    if historie_uren:
        log.info("Historie van %d uur aanmaken (1 meting per minuut)...", historie_uren)
        begin = datetime.now() - timedelta(hours=historie_uren)
        conn.executemany(
            "INSERT INTO metingen (tijdstempel, temperatuur, luchtvochtigheid) VALUES (?, ?, ?)",
            [
                (m.strftime(db.TIJDFORMAAT), *waarden(m))
                for m in (begin + timedelta(minutes=i) for i in range(historie_uren * 60))
            ],
        )
        conn.commit()
    log.info("Simulatie gestart: elke %s s een nepmeting.", interval)
    while True:
        db.voeg_toe(conn, *waarden(datetime.now()))
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Leest Arduino-metingen en slaat ze op in SQLite.")
    parser.add_argument("--poort", default="auto", help="COM3, /dev/ttyACM0 of 'auto' (standaard)")
    parser.add_argument("--db", default=None, help=f"databasebestand (standaard {db.STANDAARD_DB})")
    parser.add_argument("--simulatie", action="store_true", help="nepmetingen maken, geen Arduino nodig")
    parser.add_argument("--interval", type=float, default=3.0, help="seconden tussen nepmetingen")
    parser.add_argument("--historie-uren", type=int, default=0, help="alleen bij simulatie: uren nepgeschiedenis")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    pad = args.db or ("metingen_demo.db" if args.simulatie else db.STANDAARD_DB)
    conn = db.verbind(pad)
    log.info("Database: %s", pad)

    try:
        if args.simulatie:
            simuleer(conn, args.interval, args.historie_uren)
        else:
            if serial is None:
                sys.exit("pyserial ontbreekt. Installeer met: pip install -r requirements.txt")
            lees_seriel(args.poort, conn)
    except KeyboardInterrupt:
        log.info("Gestopt.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
