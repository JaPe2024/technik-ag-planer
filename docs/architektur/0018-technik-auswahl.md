# ADR 0018: Technik-Auswahl im Anfrage-Formular je AG

- **Status:** angenommen
- **Datum:** 2026-11-02

## Kontext

Die Ankreuzliste „Welche Technik brauchen Sie?“ im öffentlichen Anfrage-Formular war fest im Code. Jede AG hat aber andere Technik, und die Liste soll ohne Programmänderung anpassbar sein.

## Entscheidungen

**Eigenes Modell `TechOption` je AG:** Name und Reihenfolge, aufgebaut wie die Kategorien. Neue und bestehende AGs starten mit den fünf bisherigen Einträgen. Ist die Liste leer, zeigt das Formular nur das Freitextfeld.

**Anfragen speichern den Text:** `Inquiry.tech_needs` enthält die Bezeichnungen statt Schlüsseln oder Verknüpfungen. So bleibt eine eingegangene Anfrage gleich, wenn ein Eintrag später umbenannt oder gelöscht wird. Die Migration wandelt die alten Schlüssel um.

**Eigenes Recht für Owner, Admins und Lehrkräfte:** `MANAGE_TECH_OPTIONS`. Lehrkräfte bearbeiten die Anfragen und wissen, was gefragt wird. Den öffentlichen Link verwalten weiterhin nur Owner und Admins.

## Folgen

- Wird die Liste geändert, während jemand das Formular offen hat, kann ein Häkchen beim Absenden ungültig sein. Die Person sieht dann eine Fehlermeldung und die aktuelle Liste.
- Doppelte Bezeichnungen sind nicht verboten, aber unschädlich: Sie erscheinen nur doppelt in der Liste.
