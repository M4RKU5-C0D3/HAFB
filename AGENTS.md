# AGENTS.md — Richtlinien für KI-Agenten

Anleitung für Coding-Agenten, die an diesem Repository arbeiten (analog zum Vorbild-Projekt [HASH](https://github.com/M4RKU5-C0D3/HASH)).

## Projektüberblick

Home Assistant Custom Integration **`fritzbox_budget`**: steuert den Internet-Zugang einzelner Geräte einer FRITZ!Box mit einem täglichen Zeitbudget (Kindersicherung, ähnlich der Nintendo Switch). Kommunikation über TR-064 mittels der Bibliothek `fritzconnection`. Ein Config-Entry = eine FRITZ!Box. Budget-Logik läuft komplett in Home Assistant (nicht über FRITZ!Box-Filterprofile).

## Repository-Struktur

```
.github/workflows/validate.yml     HACS-Validierung (hacs/action)
custom_components/fritzbox_budget/
  __init__.py                      Setup/Unload, PLATFORMS, Services, Options-Flow-Registrierung
  api.py                           FritzBoxClient + Host + Fehlerklassen + FritzBoxInfo
  config_flow.py                   Config-Flow + Options-Flow (Geräte/Budget/Verlängerung)
  const.py                         DOMAIN, CONF_*, Defaults, Fehler-Schlüssel, Reset-Zeit
  coordinator.py                   DataUpdateCoordinator + DeviceState + Budget-Logik
  sensor.py                        Restzeit-Sensor (Restore), Auto-Abschaltung
  switch.py                        Internet-Switch je Gerät
  services.yaml                    extend_time (15/30/60 min)
  manifest.json                    Domain, Version, Codeowner, requirement fritzconnection
  strings.json                     UI-Texte (EN, Fallback)
  translations/de.json             UI-Texte (DE)
  brand/                           icon.png/@2x, logo.png/@2x
examples/                          (noch leer – geplant für YAML-Beispiele)
```

## Konventionen

- **Sprache:** Code, Docstrings, Logging und README auf Englisch; UI-Texte auf Deutsch (`translations/de.json`), Fallback `strings.json` auf Englisch.
- **Async überall:** Kein blockierender I/O auf dem Event-Loop; alle blockierenden `fritzconnection`-Aufrufe (TR-064) ausschließlich über `hass.async_add_executor_job`.
- **Externes Requirement:** `fritzconnection` ist als einzige Abhängigkeit in `manifest.json` erlaubt. Weitere nur mit gutem Grund.
- **HA-Stil:** `DataUpdateCoordinator` für Polling (15 s), Entities als `CoordinatorEntity`, `has_entity_name = True`, `DeviceInfo` pro Entry, Unique IDs aus `entry.entry_id` + MAC + Funktions-Suffix.
- **Kommentare:** Nur wenn wirklich nötig – der Code soll sich selbst erklären.

## Fachliche Randbedingungen / Kernlogik

- Geräteliste kommt aus `Hosts:1` über `FritzHosts.get_hosts_info()` (`ip`, `name`, `mac`, `active`).
- WAN-Status/Sperre über `X_AVM-DE_HostFilter:1`:
  - `GetWANAccessByIP(NewIPv4Address)` → `NewWANAccess` (`granted`/`denied`/`error`)
  - `DisallowWANAccessByIP(NewIPv4Address, NewDisallow)`
- Geräte werden **per IP** (nicht MAC) identifiziert; offline Geräte ohne IP sind nicht steuerbar (letzten Stand behalten).
- `used_today` zählt nur, solange `wan_access` ON (`granted`); Basis ist die Switch-ON-Zeit (Näherung).
- Zwei Töpfe je Gerät: **Budgets** (`budget`) und **Verlängerungen** (`granted_extension` bis `extension_limit`). Gesperrt wenn `used_today >= budget + granted_extension`.
- **Zähler-Reset um 03:00 Uhr** (`RESET_HOUR`): vor 03:00 zählt die Zeit noch zum Vortag; gesperrte Geräte werden beim Reset automatisch freigeschaltet.
- Options-Flow speichert in `entry.options[CONF_DEVICES] = {mac: {budget, extension_limit}}`; Änderungen lösen `async_reload_entry` aus.
- Service `extend_time` (device=MAC, minutes 15/30/60) ruft `coordinator.async_extend_time`.
- Bei Verbindungs-/Auth-Fehlern: `_async_update_data` gibt den letzten Datenstand zurück (kein `UpdateFailed`), damit Entitäten verfügbar bleiben.
- Verbindungsdaten sind TR-064-basiert; im Router müssen „Zugriff für Anwendungen" (TR-064) und ggf. UPnP aktiviert sein. `unique_id` = Seriennummer (`DeviceInfo:1/GetInfo/NewSerialNumber`); Enttitel = `NewModelName`.

## Verifikation vor jedem Commit

```bash
python3 -m compileall custom_components/fritzbox_budget      # Syntax
python3 - <<'EOF'                                            # JSON valide?
import json, pathlib
for p in pathlib.Path("custom_components/fritzbox_budget").rglob("*.json"):
    json.loads(p.read_text())
EOF
python3 -c "import yaml, pathlib; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.').rglob('*.y*ml')]"
ruff check custom_components/fritzbox_budget                  # falls installiert
# Korrektheit der Domain-Konstante gegenüber manifest/Ordnername prüfen:
grep -rn '"domain"' custom_components/fritzbox_budget/manifest.json
grep -rn '^DOMAIN' custom_components/fritzbox_budget/const.py
```

Manueller End-to-End-Test: `custom_components/fritzbox_budget/` in das `config/custom_components/` einer HA-Installation kopieren, neu starten, Integration hinzufügen, im Options-Flow Geräte wählen und Log auf Fehler prüfen.

## Release-Prozess

1. `version` in `manifest.json` erhöhen (SemVer)
2. Commit auf `master`, Tag `vX.Y.Z` setzen, GitHub Release erstellen
3. Die Validate-Workflow prüft HACS-Konformität automatisch
