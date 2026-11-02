# Materialerweiterung im Fork – Übergabe an die ursprüngliche Entwicklung

Stand: 02.11.2026. Ergänzung zu [Spezifikation und Meilenstein 13](../feature-liste.md), [ADR 0020](../architektur/0020-material-einzelgeraete.md) und [Bedienungsanleitung](../handbuch/material-scans.md).

Die Erweiterung bleibt innerhalb der vorhandenen Django-App `inventory`. Sie verwendet dieselbe PostgreSQL-Datenbank, Konten, AG-Zuordnung, Rollen, Materialkategorien, Materialsätze und Produktionsplanung. Es entsteht weder ein zweites Backend noch eine zweite Datenbank. Die ursprünglichen zwölf Meilensteine werden nicht nachträglich umnummeriert. Die Änderungen sind im Fork implementiert; eine Übernahme ins Originalprojekt oder eine abgeschlossene Gesamtfreigabe wird damit nicht behauptet.

## Funktionsumfang

### AG-Modus

`Organization.inventory_qr_enabled` schaltet unter Einstellungen → Materialverwaltung zwischen zwei exklusiven Abläufen um. Standard ist `False`.

- Klassisch: Mengenplanung und bisherige Packliste zum Abhaken. QR-Einstiege sind ausgeblendet und QR-Views serverseitig gesperrt.
- QR: Geräteverwaltung und strukturierte Ausgabe. Klassische Packlisten-Haken sind deaktiviert. Für Personen mit Produktionsverwaltungsrecht führt der Packlisten-Endpunkt zur Materialausgabe.
- Vor Aktivierung müssen persönliche Ausleihen zurückgegeben sein. Vor Deaktivierung müssen offene Geräteausgaben und Mengenrückgaben erledigt und aktive Einzelgerätereservierungen aufgehoben sein.
- Ein Moduswechsel löscht weder Material noch Historien. Die serverseitige Modusprüfung wird bei schreibenden Abläufen innerhalb der Transaktion erneut vorgenommen.

### Verwaltungsart einer Materialart

`Material.tracking` enthält `bulk`, `individual` oder `consumable`. Die Auswahl erscheint nur im QR-Modus. Neue Materialarten erhalten standardmäßig `bulk`; die Anwendung errät die Art nicht aus dem Namen.

| Wert | Verwendung | Ablauf |
| --- | --- | --- |
| `bulk` | Austauschbare Kabel, Adapter, Klemmen | Menge in Produktion einplanen, Stückzahlen ausgeben, auch in Teilmengen zurücknehmen |
| `individual` | Funkmikrofon, Lichtpult, besondere Kabeltrommel | Physische Geräte erfassen, konkrete Inventarcodes reservieren, Ausgabe/Rückgabe scannen |
| `consumable` | Batterien, Gaffa | Geplante Menge entnehmen; endlichen Bestand reduzieren; keine Rückgabepflicht |

Nach Geräteerfassung oder ersten Mengenbewegungen verhindert das Materialformular einen Wechsel der Verwaltungsart. Bestehende physische Geräte werden durch eine Datenmigration auf `individual` gesetzt. Materialien ohne Geräte bleiben standardmäßig `bulk`.

### Einzelgeräte und Etiketten

- `MaterialUnit` repräsentiert ein physisches Gerät einer vorhandenen Materialart.
- Inventarcodes werden manuell vergeben oder automatisch erzeugt; die Datenbank erzwingt Eindeutigkeit.
- Die Materialdetailseite enthält die Geräte direkt. Einzelne Geräte sind eingeklappt; erst beim Öffnen erscheinen Etikett, Defekte, Historie und Aktionen. Die separate Geräteansicht bleibt erreichbar.
- Ein endlicher Bestand wird beim Hinzufügen bei Bedarf bis zur Anzahl aktiver Geräte erhöht. Es gibt keine automatische vollständige Aufteilung alter Bestandsmengen.
- Archivierung/Wiederaktivierung sind möglich. Offene Ausgaben und laufende oder zukünftige Reservierungen verhindern die Archivierung. Löschen ist nur ohne Historie zulässig.
- QR-PNGs entstehen mit `qrcode`. Ihr Inhalt ist eine Geräteadresse. Eine gemeinsame Etikettenansicht und einzelne Etiketten sind über den Browser druckbar.

### Reservierung auf der Produktionsseite

- Zuerst die Materialart mit Menge einplanen, dann darunter konkrete Geräte reservieren.
- Fortschritt beispielsweise „3 von 6 reserviert“, Auswahl über Gerätezeilen mit Verfügbarkeitsstatus.
- Gesperrte Geräte werden mit Grund kenntlich gemacht: Defekt, Materialart gesperrt, noch ausgegeben oder zeitlich bereits reserviert.
- Anzahl konkreter Reservierungen darf die geplante Menge nicht überschreiten.
- Prüfung auf gleiche AG, Archivstatus, Defekte, offene Ausgaben und Terminüberschneidung.
- Reservierung verwendet aktuelle Produktionstage einschließlich des Enddatums; nach Terminänderung wird bei Ausgabe erneut geprüft.
- Reservieren/Aufheben führt zurück zum Materialabschnitt der Produktion. Die Ausgabeansicht enthält kein zweites Reservierungsformular.
- Nach abgeschlossenem Abbau ist keine neue Reservierung zulässig. Zum Aufheben muss eine offene Ausgabe zuerst zurückgegeben werden.

### Scan-Ausgabe und Rückgabe

- `UnitIssue` enthält Gerät, Produktion, ausgebende Person/Zeit und zurücknehmende Person/Zeit.
- Eingabe per Kamera, Inventarcode oder USB-Scanner. QR-Inhalt kann ein reiner Code oder eine Geräteadresse sein. Vorhandene ältere Codes mit Kleinbuchstaben bleiben lesbar.
- Scanner mit expliziten Modi Ausgabe/Rückgabe, fortlaufender Kamera, Unterdrückung kurzfristiger Doppelerfassungen und Statusrückmeldung ohne vollständiges Neuladen.
- Ausgabe benötigt eine noch gültige Reservierung. Vorzeitiges Packen ist nur ohne Konflikt mit früheren Reservierungen möglich.
- Transaktionen und Zeilensperren serialisieren Änderungen; eine bedingte Unique-Constraint verhindert mehrere offene Ausgaben desselben Geräts.
- Lokales `html5-qrcode` 2.3.8 einschließlich Apache-2.0-Lizenz, kein Laufzeit-CDN. Kamera benötigt HTTPS/localhost und Browserfreigabe; Stream endet beim Verlassen.

### Mengenbewegungen und Verbrauch

- `PlannedMaterial.issued_quantity` und `returned_quantity` bilden ausgegebene und zurückgegebene Stückzahlen ab; `outstanding_quantity` berechnet die Differenz.
- `QuantityMovement` protokolliert jeden Vorgang mit Menge, Operation, Person und Zeitpunkt.
- Keine Einzelstückreservierung für Kabel: die bereits eingeplante Materialmenge ist der Bedarf der Produktion.
- Ausgaben werden gegen noch geplante Menge und aktuellen verfügbaren Bestand geprüft. Bei Mengenmaterial werden offene Produktionsausgaben berücksichtigt.
- Teilrückgaben sind möglich; Überrückgaben werden abgelehnt.
- Verbrauchsmaterial verringert bei Entnahme einen endlichen Bestand. Rückgaben werden abgelehnt und beim Abbau nicht verlangt.
- Historisierte Materialpositionen können nicht einfach entfernt werden; die geplante Menge darf nicht unter die bereits ausgegebene Menge sinken.

### Defekte und Reparatur

- Vorhandenes `DefectReport` wird um optionale Gerätezuordnung, Reparaturvermerk und reparierende Person erweitert.
- Ein gerätebezogener offener Defekt reduziert den defekten Bestand einmal und sperrt nur das betroffene Gerät.
- Allgemeine offene Materialdefekte sperren die Einzelgeräteausgabe der Materialart vorsorglich.
- Reparatur benötigt einen Vermerk; vorhandene Defekte und Reparaturen bleiben sichtbar.

### Abbau und Protokoll

- `ProductionTeardown` hält Beginn/Abschluss samt Personen und Zeiten fest.
- `TeardownException` dokumentiert für eine offene Geräteausgabe einmalig „vermisst“, „beschädigt“ oder „sonstiges“ mit Bemerkung.
- „Beschädigt“ erzeugt in derselben Transaktion einen Gerätedefekt, sofern keiner offen ist.
- Abschluss nur nach Rückgabe oder Ausnahme für alle offenen Geräteausgaben und nach vollständiger Rückgabe von Mengenmaterial.
- Abschluss gibt Reservierungen frei. Vermisste Geräte bleiben als offene Ausgabe gesperrt; nachträgliche tatsächliche Rückgaben bleiben möglich.
- Neue Ausgaben/Reservierungen werden gesperrt. UI zeigt den Abschlussgrund statt kommentarlos verschwundener Buttons.
- Druckbares Abbauprotokoll mit Ausgaben, Rückgaben, Personen, Ausnahmen und Mengenbewegungen. PDF über Browserdruck, bisher keine Einbindung in die vorhandene WeasyPrint-Dokumentpipeline.
- Übersicht kompakt; Aktionen und Ausnahmeformulare zunächst eingeklappt. Die offene Geräteanzahl ist gesondert ausgewiesen; Mengenrückgaben stehen bei ihren Materialpositionen.

### Persönliche Ausleihen

Im klassischen Modus ergänzt `MaterialCheckout` mengenbasierte persönliche Ausleihen. Mitglieder geben eigene Ausleihen zurück; Personen mit Materialverwaltungsrecht auch fremde. Offene Ausleihen reduzieren die verfügbare Menge und beeinflussen bestehende Planungskonflikte. QR-Geräteausgaben und persönliche Ausleihen sind unterschiedliche Vorgänge.

### Oberfläche und Hilfe

Gemeinsame Materialübersicht mit Unterteilungen, keine getrennte zweite Reservierungsliste. Ausklappbare Mengenaktionen und Geräte, Statuskennzeichnung, deutlich ausgewählter Scanmodus, manuelle Eingabe als Alternative zur Kamera. Wiederverwendbare Benutzerhilfe erklärt Auswahl, Beispiele und Ablauf im Materialformular, in Einstellungen und Ausgabeansicht. Bestehende Design-Tokens werden genutzt.

## Rechte und technische Schnittstellen

- `MANAGE_INVENTORY`: Materialmodus, Gerätepflege und Reparaturen.
- `MANAGE_PRODUCTIONS`: Reservierungen, Ausgabe/Rückgabe und Abbau.
- `REPORT_DEFECT`: Gerätedefekte melden.
- Persönliche Ausleihe: Mitglieder der aktiven AG, Rücknahme fremder Ausleihen nur mit Verwaltungsrecht.
- Views prüfen aktive AG und Rechte. Eingaben aus anderen AGs werden abgewiesen. Die aktuelle Implementierung ist trotzdem vor Upstream-Übernahme vollständig auf die Projektkonventionen zu prüfen.

| Datei/Bereich | Verantwortung |
| --- | --- |
| `inventory/models.py` | Modelle, Zähler, Constraints |
| `inventory/unit_services.py` | Transaktionen, Sperren, Status- und Bestandsprüfungen |
| `inventory/unit_views.py`, `urls.py` | Geräte-, Ausgabe-, Reservierungs-, Abbau- und Einstellungsendpunkte |
| `inventory/forms.py`, `views.py`, `services.py` | Verwaltungsart, Schutz bestehender Planungen, verfügbare Bestände |
| `productions/views.py`, Produktions-Template | Gerätezustände und Reservierungsoberfläche bei der Materialposition |
| `organizations/models.py`, `settings_menu.py` | AG-Modus und Einstellungsnavigation |
| `templates/inventory/` | Geräte, Ausgabe, Protokoll, Einstellungen, gemeinsame Includes |
| `static/js/material-scanner.js` | Kamera, Scanverarbeitung, Aktualisierung der Teilansichten |
| `static/css/inventory-units.css`, `static/vendor/` | Neue Gestaltung und lokal ausgelieferte Scannerbibliothek |
| `inventory/tests/test_units.py` | Abläufe, Rechte, AG-Trennung, Parallelzugriffe |

Nebenänderungen: WeasyPrint wird in `documents/pdf.py` erst bei PDF-Erzeugung importiert. Der externe lokale PostgreSQL-Port ist standardmäßig 5433 und über `POSTGRES_DEV_PORT` konfigurierbar; intern bleibt 5432.

## Migrationen und Einführung

- `organizations/0003_organization_inventory_qr_enabled`
- `inventory/0002_material_units`
- `inventory/0003_defectreport_resolution_defectreport_resolved_by_and_more`
- `inventory/0004_materialcheckout`
- `inventory/0005_material_tracking_plannedmaterial_issued_quantity_and_more`
- `inventory/0006_preserve_device_tracking`

Vor Start der aktualisierten Anwendung regulär migrieren (`make migrate`). Kein Datenbankreset erforderlich. Bestehende Geräte werden erhalten; übrige Verwaltungsarten müssen bewusst gewählt werden. Keine automatische Neuinterpretation von Materialnamen oder klassischen Packlisten-Haken als neue Mengenhistorie.

## Validierungsstand und offene Übernahmeprüfungen

Ein größerer PostgreSQL-Testlauf bestand mit 438 Tests. Nach Änderungen an der Oberfläche bestanden 280 Material-/Sicherheitstests gegen PostgreSQL. Die letzte Einbettung der Geräteliste wurde mit 25 gezielten Tests auf SQLite geprüft; zwei PostgreSQL-Paralleltests sind dort übersprungen. Das ist weder eine vollständige aktuelle Gesamtsuite noch eine visuelle Freigabe. Lint und Migrationsabgleich wurden während der Implementierung ausgeführt.

Vor einer Übernahme verbleiben insbesondere:

- Vollständige aktuelle `make test`- und `make lint`-Läufe sowie grüne CI; PR und Review im Originalprojekt sind noch offen.
- Audit-/Exportregistrierung ist nachgezogen: alle sieben neuen Modelle sind in `inventory/apps.py` registriert; der AG-Export enthält den QR-Modus. Freigeben von Reservierungen und Rückgabe persönlicher Ausleihen verwenden `save()`, damit das Änderungsprotokoll ausgelöst wird. Ein gezielter Test prüft Registrierung, Export, AG-Trennung und Protokollierung einer Reservierungsaufhebung. Vollständige Integration weiterhin im Gesamt-Review prüfen.
- Lösch- und Aufräumpfade prüfen: neue `PROTECT`-Beziehungen können Produktionspurge oder AG-Auflösung beeinflussen. Kontoentfernung, Datenexport und Datenschutz zusammenhängend prüfen.
- Migration mit realistischem Altbestand, bereits abgeschlossenen Produktionen und vorhandenen Geräteausgaben durchspielen.
- Historie nach Terminänderungen, Mengenplanung versus aktuellem Bestand, Archivierung und Wiederaktivierung gemeinsam prüfen.
- Mengenmaterial unterstützt bisher keine begründete Verlustausnahme beim Abbau; offene Mengen müssen vollständig zurückerfasst werden. Erweiterungsbedarf fachlich entscheiden.
- Echte QR-/Kameratests auf Android/iPhone/iPad über HTTPS, einschließlich Freigaben, Moduswechsel, Kamerastopp und Doppelscans; Drucklayouts und neue Oberfläche visuell abnehmen.
- Unterstützte Rücknahme/erneutes Öffnen eines abgeschlossenen Abbaus ist derzeit nicht implementiert.

Diese Punkte sind ausdrücklich Restarbeiten für die Übernahme und keine zugesagten fertigen Funktionen.
