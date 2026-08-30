# Home Assistant FRITZ!Box Budget

[![HACS Custom Repository](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/M4RKU5-C0D3/HAFC) [![GitHub release](https://img.shields.io/github/v/release/M4RKU5-C0D3/HAFC?style=for-the-badge)](https://github.com/M4RKU5-C0D3/HAFC/releases)

Home Assistant Custom Integration **`fritzbox_budget`**: steuert den Internet-Zugang einzelner Geräte einer FRITZ!Box mit einem täglichen Zeitbudget – ähnlich der Kindersicherung einer Nintendo Switch. Ein Config-Entry = eine FRITZ!Box.

## Funktionsumfang

- **Verwaltete Geräte** über den Options-Flow auswählen.
- Pro Gerät ein **`switch`** (Internet ein/aus) über die FRITZ!Box-Gerätesperre (`X_AVM-DE_HostFilter`).
- Pro Gerät ein **`sensor`** mit der verbleibenden Zeit heute (Budget + Verlängerungen − verbrauchte Zeit).
- **Tagesbudget** pro Gerät, zurückgesetzt täglich um **03:00 Uhr**.
- **Verlängerungen** per Service `fritzbox_budget.extend_time` (15 / 30 / 60 Minuten) – auch schon vor Ablauf des Budgets, begrenzt durch ein Tageslimit.
- **Automatisches Abschalten**, sobald das Budget erschöpft ist.
- Bei Verbindungs-/Anmeldefehlern bleibt der letzte Datenstand erhalten.

> Die Zeitberechnung („verbrauchte Zeit") basiert auf der Dauer, in der der Internet-Zugang über diese Integration gewährt war. Die FRITZ!Box bietet keine API für die tatsächliche Nutzungszeit pro Gerät – für ein Kindergerät ist diese Näherung in der Regel ausreichend.

## Voraussetzungen

- FRITZ!Box mit aktiviertem **„Zugriff für Anwendungen" (TR-064)** unter Heimnetz → Netzwerk → Netzwerkeinstellungen → Zugangseinstellungen im Heimnetz (ggf. zusätzlich UPnP aktiviert).
- Ein FRITZ!Box-Benutzer mit der Berechtigung **FRITZ!Box-Einstellungen** (Empfehlung: ein separater Benutzer anlegen).

## Installation

### Via HACS (empfohlen)

1. In HACS: **HACS → ⋮ → Benutzerdefinierte Repositorys**
2. Repository-URL `https://github.com/M4RKU5-C0D3/HAFC` mit Kategorie **Integration** hinzufügen
3. „FRITZ!Box Budget" herunterladen
4. Home Assistant neu starten
5. **Einstellungen → Geräte & Dienste → Integration hinzufügen → „FRITZ!Box Budget"** und Zugangsdaten eingeben

### Manuell

1. `custom_components/fritzbox_budget/` in `<config>/custom_components/fritzbox_budget/` kopieren
2. Home Assistant neu starten
3. Integration über die UI hinzufügen (s. o.)

## Einrichtung

Nach dem Hinzufügen der FRITZ!Box:

1. **Integration → Optionen** öffnen.
2. Die zu verwaltenden Geräte auswählen.
3. Für jedes Gerät **Tagesbudget** (Minuten) und **max. Verlängerung pro Tag** (Minuten) festlegen.

## Verlängerungen

Über den Service `fritzbox_budget.extend_time` gewährst du einem Gerät zusätzliche Zeit:

```yaml
service: fritzbox_budget.extend_time
data:
  device: "AA:BB:CC:DD:EE:FF"   # MAC-Adresse des Geräts
  minutes: 15                    # 15, 30 oder 60
```

Die Verlängerung ist sofort wirksam und begrenzt durch das konfigurierte Tageslimit. Auch wenn das Gerät durch das Budget bereits gesperrt war, wird es durch die Verlängerung wieder freigeschaltet.

## Benachrichtigung vor Abschaltung

Die Integration sendet keine Benachrichtigungen selbst. Über den Restzeit-Sensor (`sensor.<gerät>_remaining_time_today`) kannst du per Automation eigene Warnungen auslösen, sobald das Budget fast aufgebraucht ist – z. B. ein Numerik-Trigger bei „≤ 30/20/10 Minuten" und ein Versand über Gotify o. ä. an das gewünschte Gerät:

```yaml
automation:
  - alias: "Budget Warnung"
    trigger:
      - platform: numeric_state
        entity_id: sensor.kind_pc_remaining_time_today
        below: 10
    action:
      - service: notify.myservice
        data:
          message: "Noch 10 Minuten Internet-Zeit übrig!"
```

## Datenabfrage

- Update-Intervall: 15 s, `DataUpdateCoordinator`.
- Bei Verbindungs- oder Anmeldefehlern bleibt der letzte Datenstand erhalten; Entitäten werden nicht als unverfügbar markiert.

## Hinweis

Privates Projekt. Steuert ausschließlich die eigene FRITZ!Box über das lokale TR-064-Interface.

## Vibe coding

Erstellt mit KI-Unterstützung über [opencode](https://opencode.ai) (Modell `big-pickle`), analog zum Vorbild-Projekt [HASH](https://github.com/M4RKU5-C0D3/HASH). Gesamter Code von einem menschlichen Maintainer geprüft und veröffentlicht.
