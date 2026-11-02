# Einzelgeräte, QR-Scan und Materialausleihe

Die Materialfunktionen aus Technik HUB sind als Erweiterung der bestehenden Django-App `inventory` umgesetzt. Kategorien, Bestandsmengen, Materialsätze, Produktionsplanung, Packlisten, Dateien und Defektmeldungen bleiben erhalten. Es wird keine zweite Datenbank und kein Next.js-Server benötigt.

## Einrichtung

Die neuen Tabellen und Zusatzfelder werden mit den normalen Django-Migrationen angelegt:

```sh
make migrate
```

Bestehende Bestände werden nicht automatisch in Einzelgeräte umgewandelt. Unter **Material → Material auswählen → Einzelgeräte & QR-Etiketten** lassen sich physische Geräte erfassen. Beim Hinzufügen wird ein endlicher Bestand bei Bedarf auf die Anzahl aktiver Einzelgeräte erhöht. Ein Inventarcode kann angegeben oder automatisch erzeugt werden. Laufende persönliche Ausleihen müssen vor dem Anlegen von Einzelgeräten zurückgegeben werden.

## Verwendung

- **Etiketten:** Pro Material oder über „Alle QR-Etiketten“ anzeigen und mit der Druckfunktion des Browsers drucken. Die QR-Codes enthalten Geräteadressen; der Scanner akzeptiert auch reine Inventarcodes und ältere automatisch erzeugte Codes.
- **Reservierung:** In der Produktionsplanung zunächst eine Materialmenge eintragen. Über **Packliste → Einzelgeräte scannen** konkrete Geräte reservieren. Die Reservierung gilt für alle Produktionstage einschließlich des Enddatums. Überschneidungen werden abgelehnt. Die Prüfung verwendet die aktuellen Produktionsdaten, auch nach Terminänderungen; bei der Ausgabe werden Konflikte erneut geprüft.
- **Ausgabe/Rückgabe:** QR-Code per Kamera scannen, Inventarcode eingeben oder einen USB-Scanner verwenden. Die Kamera bleibt für weitere Geräte offen. Ein Gerät kann nur eine offene Ausgabe haben. Vorzeitige Ausgaben sind nur zulässig, wenn keine frühere Reservierung blockiert wird. Rückgaben bleiben auch nach Abschluss des Abbaus möglich.
- **Defekte:** Ein Defekt am Einzelgerät zählt einmal im bestehenden Materialbestand. Nur dieses Gerät wird gesperrt. Allgemeine Defektmeldungen ohne Gerätezuordnung sperren die Ausgabe der Materialart vorsorglich. Reparaturen benötigen einen Vermerk. Die Defekthistorie bleibt erhalten.
- **Abbau:** Abbau starten, Rückgaben scannen und gegebenenfalls eine begründete Ausnahme dokumentieren. „Beschädigt“ erzeugt zusätzlich eine echte Defektmeldung. Der Abschluss ist erst möglich, wenn jede offene Ausgabe eine Ausnahme besitzt. Reservierungen werden dann freigegeben; vermisste Geräte bleiben bis zur tatsächlichen Rückgabe gesperrt. Das Abbauprotokoll enthält Zeiten, Personen und Ausnahmen und lässt sich über den Browser drucken oder als PDF speichern.
- **Persönliche Ausleihe:** Im klassischen Modus kann Mengenmaterial auf der Materialdetailseite ausgeliehen werden. Mitglieder geben eigene Ausleihen zurück; Personen mit Materialverwaltungsrecht können auch fremde Ausleihen zurücknehmen.
- **Archiv:** Ausgegebene oder künftig reservierte Geräte sind vor Archivierung geschützt. Geräte mit Historie können nur archiviert werden. Bestehende Mengenbestände werden durch Gerätearchivierung nicht automatisch geändert.

Die Rollenrechte des Planers gelten weiter: Materialverwaltung für Gerätepflege und Reparaturen, Produktionsverwaltung für Reservierungen, Scans und Abbau; Defektmeldungen entsprechend dem bestehenden Recht. Alle Zugriffe werden auf die aktive AG begrenzt.

## Kamera und Tests

Die Kamera benötigt HTTPS oder localhost und eine Kamera-Freigabe. `html5-qrcode` 2.3.8 wird samt Apache-2.0-Lizenz lokal ausgeliefert (`app/static/vendor/`); zur Laufzeit ist kein CDN nötig. Ein Wechsel des Scanmodus erfordert keinen Kameraneustart.

```sh
make test
```

`test_units.py` prüft Reservierungskonflikte, Ausgabe/Rückgabe, Defekte, Ausleihen, Rechte, AG-Trennung, Gerätehistorie und Abbau. Zwei zusätzliche Parallelzugriffstests benötigen PostgreSQL und werden auf SQLite übersprungen. Hardwaretests auf den eingesetzten Handys/Tablets bleiben erforderlich. Die Migrationen sind vor dem Start der aktualisierten Anwendung auszuführen.
## Materialmodus auswählen

Unter **Einstellungen → Materialverwaltung** wird genau ein Modus für die AG ausgewählt:

- **Klassische Liste:** Mengenplanung mit Abhaken für Ausgabe und Rückgabe. QR-Etiketten, Einzelgeräteverwaltung und Scanner sind ausgeblendet und auch über direkte Links deaktiviert.
- **Einzelgeräte & QR-Codes:** Einzelgeräte erfassen und reservieren, per Kamera scannen und den Abbau dokumentieren. Das manuelle Abhaken der klassischen Liste ist deaktiviert. Der Packlisten-Link öffnet für Personen mit Produktionsverwaltungsrecht direkt die Scan-Verwaltung.

Der Standard ist die klassische Liste. Vor dem Wechsel zu QR müssen persönliche Ausleihen zurückgegeben werden. Vor dem Wechsel zurück müssen Geräteausgaben zurückgegeben und aktive Reservierungen aufgehoben werden. Geräte, Ausgaben und Defekthistorien werden beim Wechsel nicht gelöscht.

Im QR-Modus lassen sich Geräte unter **Material → Material auswählen → Einzelgeräte & QR-Etiketten → Einzelgerät hinzufügen** anlegen. Bleibt der Inventarcode leer, wird automatisch ein Code erzeugt. Übersteigt die Anzahl aktiver Geräte den bisherigen endlichen Bestand, wird dieser entsprechend erhöht.
## Materialarten im QR-Modus

Im Materialformular lässt sich die Verwaltungsart auswählen:

- **Mengenmaterial:** beispielsweise „XLR-Kabel, 5 m“. In der Produktion wird die benötigte Menge geplant. Unter Ausgabe/Rückgabe werden Stückzahlen erfasst; Teilrückgaben sind möglich. Es werden keine bestimmten Kabel reserviert oder einzeln gescannt.
- **Einzelgeräte:** konkrete Geräte reservieren und per Inventarcode scannen. Bestehende Einzelgeräte werden bei der Migration automatisch dieser Verwaltungsart zugeordnet.
- **Verbrauchsmaterial:** Entnahmen ohne Rückgabe erfassen. Ein endlicher Bestand wird bei der Entnahme verringert.

Die Ausgabe ist auf die geplante und verfügbare Menge begrenzt. Alle Mengenbewegungen sind im Abbauprotokoll dokumentiert. Offene Rückgaben von Mengenmaterial verhindern den Abbauabschluss und den Wechsel zurück zum klassischen Modus. Nach Geräteerfassung oder ersten Ausgaben ist die Verwaltungsart zum Schutz der Historie festgelegt.
