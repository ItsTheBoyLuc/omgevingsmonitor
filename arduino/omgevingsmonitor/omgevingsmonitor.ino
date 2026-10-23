/*
  Omgevingsmonitor - Arduino-kant
  Leest een DHT-sensor uit en stuurt elke 3 seconden een regel via USB-serial:

      21.0,55.0

  (temperatuur in graden Celsius, komma, luchtvochtigheid in %, newline)

  Bedrading (lees de letters op het sensorplaatje):
      -  (min)       -> GND
      +  (VCC)       -> 5V   (op de Uno: de 5V-pin direct na 3.3V)
      S  (OUT/DATA)  -> pin D2
  Een losse sensor zonder plaatje (4 pinnen) heeft ook een weerstand van 10 kOhm
  nodig tussen VCC en DATA.

  Libraries (Arduino IDE > Hulpmiddelen > Bibliotheken beheren):
    - "DHT sensor library" van Adafruit
    - "Adafruit Unified Sensor" van Adafruit

  WELKE SENSOR? Zet hieronder DHTTYPE op het type dat je hebt:
    - blauw huisje           -> DHT11
    - wit, wat groter huisje -> DHT22

  PROBLEMEN OPSPOREN: zet DEBUG op 1. Dan stuurt de Arduino ook tekstregels
  ("Start", "Geen meting"). Zet DEBUG voor normaal gebruik weer op 0, want
  ontvanger.py verwacht alleen regels in de vorm  21.0,55.0

  Functionele eisen: F1 (elke 3 s meten) en F2 (geen ongeldige waarden versturen).
*/

#include <DHT.h>

#define DHTPIN 2
#define DHTTYPE DHT11          // <-- DHT11 of DHT22
#define DEBUG 0                // 0 = alleen metingen, 1 = ook tekstmeldingen

const unsigned long INTERVAL_MS = 3000;   // F1: elke 3 seconden
const unsigned long BAUDRATE = 9600;      // moet gelijk zijn aan ontvanger.py

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(BAUDRATE);
  dht.begin();
  delay(2000);  // de sensor heeft na het opstarten even nodig
#if DEBUG
  Serial.println("Start");
#endif
}

void loop() {
  float temperatuur = dht.readTemperature();   // graden Celsius
  float vochtigheid = dht.readHumidity();      // % RH

  // F2: alleen geldige waarden versturen (bij een fout geeft de sensor NaN)
  if (!isnan(temperatuur) && !isnan(vochtigheid)) {
    Serial.print(temperatuur, 1);
    Serial.print(',');
    Serial.println(vochtigheid, 1);
  } else {
#if DEBUG
    Serial.println("Geen meting");
#endif
  }

  delay(INTERVAL_MS);
}
