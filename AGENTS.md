# AGENTS.md — Richtlinien für KI-Agenten

Anleitung für Coding-Agenten in diesem Repository (Vorbild: [HASH](https://github.com/M4RKU5-C0D3/HASH)). Code, Docstrings, Logging und README auf Englisch; UI-Texte auf Deutsch.

## Projektüberblick

Home Assistant Custom Integration **`fritzbox_budget`**: steuert den Internet-Zugang einzelner Geräte einer FRITZ!Box mit einem täglichen Zeitbudget (Kindersicherung, ähnlich der Nintendo Switch). Kommunikation über TR-064 mittels `fritzconnection`. Ein Config-Entry = eine FRITZ!Box. Die Budget-Logik läuft komplett in Home Assistant, **nicht** über FRITZ!Box-Filterprofile.

## Umgebung / Toolchain

- Einzige zulässige Laufzeit-Abhängigkeit ist `fritzconnection` (`manifest.json`: `>=1.13.2`). Home Assistant ist in dieser Umgebung nicht installiert/importierbar – Code-Änderungen lassen sich nicht per Import testen.
- **Python 3.12+ nötig:** `__init__.py` nutzt PEP-695-Type-Aliase (`type X = ...`).
- **Keine Test-Suite und keine Ruff-/Lint-Konfiguration im Repo.** CI (`.github/workflows/validate.yml`) prüft nur die HACS-Konformität und läuft ausschließlich bei Push auf `master` und wöchentlich – PRs werden **nicht** geprüft. Verifikation erfolgt daher lokal (siehe unten).
- `examples/` ist noch leer (geplant für YAML-Beispiele).

## Repository-Struktur

```
custom_components/fritzbox_budget/
  __init__.py         Setup/Unload, PLATFORMS, Service `extend_time`, Update-Listener
  api.py              FritzBoxClient + Host + Fehlerklassen + FritzBoxInfo (fritzconnection-Wrapper)
  config_flow.py      ConfigFlow (user) + OptionsFlow (init: Geräte, configure: Budget)
  const.py            DOMAIN, CONF_*, Defaults, Fehler-Schlüssel, EXTENSION_MINUTES, RESET_HOUR
  coordinator.py      DataUpdateCoordinator + DeviceState + Budget-Logik
  sensor.py           Restzeit-Sensor (RestoreSensor, Persistenz via Attribute)
  switch.py           Internet-Switch je Gerät
  button.py           Verlängerungs-Buttons +15/+30/+60 min
  services.yaml       extend_time (device=MAC, minutes 15/30/60)
  manifest.json       Domain, Version, Codeowner, Requirement fritzconnection
  strings.json        UI-Texte (EN, Fallback) – muss zu translations/de.json passen
  translations/de.json  UI-Texte (DE)
  brand/              icon/logo (+ @2x, dark_*)
```

## Konventionen

- **Async überall:** Kein blockierender I/O auf dem Event-Loop; alle `fritzconnection`-Aufrufe (TR-064) ausschließlich über `hass.async_add_executor_job`.
- **HA-Stil:** `DataUpdateCoordinator` (Polling 15 s), Entities als `CoordinatorEntity`, `has_entity_name = True`, eigenes `DeviceInfo` pro verwaltetem Gerät (`identifiers={(DOMAIN, mac)}`, Hersteller AVM), Unique IDs `f"{entry_id}_{mac}_<suffix>"`.
- **Übersetzungen:** Jeder neue `translation_key` / Service / Config-Feld-Schlüssel muss **in `strings.json` und `translations/de.json` gleichzeitig** ergänzt werden (HA liest beide; Abweichungen fallen erst im UI auf).
- **Kommentare:** Nur wenn wirklich nötig – der Code soll sich selbst erklären.

## Fachliche Randbedingungen / Kernlogik

- Geräteliste kommt aus `Hosts:1` über `FritzHosts.get_hosts_info()`. Das Rohfeld heißt `status` (wird in `api.py` auf `Host.active` gemappt); weitere Keys: `ip`, `name`, `mac`. MACs werden auf Großbuchstaben normalisiert; Geräte ohne MAC werden verworfen.
- WAN-Status/Sperre über `X_AVM-DE_HostFilter:1`:
  - `GetWANAccessByIP(NewIPv4Address)` → `NewWANAccess` (`granted`/`denied`/`error`)
  - `DisallowWANAccessByIP(NewIPv4Address, NewDisallow)`
- Geräte werden **per IP** (nicht MAC) gesteuert. Offline-Geräte ohne IP sind nicht steuerbar; ihr letzter Stand bleibt erhalten.
- `used_today` zählt nur, solange `wan_access` ON (`granted`) **und** das Gerät laut `status` aktiv Datenverkehr hat; Standby/„Ungenutzte Verbindungen" und die Zeit von 03:00 bis zur ersten Nutzung laufen nicht ins Kontingent.
- Zwei Töpfe je Gerät: **Budget** (`budget`) und **Verlängerungen** (`granted_extension`, wächst ohne Tages-Cap). Gesperrt wenn `used_today >= budget + granted_extension`. Verlängerung mit Restzeit: `granted_extension += minutes`; ohne Restzeit: Internet freischalten und `granted_extension = minutes + used_today - budget` (Restzeit exakt = gewählte Minuten).
- **Zähler-Reset um 03:00 Uhr** (`RESET_HOUR`): vor 03:00 zählt die Zeit noch zum Vortag; gesperrte Geräte werden beim Reset automatisch freigeschaltet und `used_today`/`granted_extension` auf 0 gesetzt.
- Options-Flow speichert `entry.options[CONF_DEVICES] = {mac: {budget}}`; ein Update-Listener ruft `async_reload_entry` → `async_reload`. Der Options-Flow `init` benötigt einen geladenen Coordinator (`hass.data[DOMAIN][entry_id]`), sonst `abort(not_ready)`.
- Config-Flow-UI fragt **kein** Port-Feld ab: Host, Username, Password, SSL. Der TR-064-Port wird aus der SSL-Wahl abgeleitet (`DEFAULT_HTTP_PORT`/`DEFAULT_HTTPS_PORT`).
- Service `extend_time` (device=MAC in Großschreibung, minutes 15/30/60) wird global in `async_setup` registriert und sucht den passenden Coordinator über alle Entries.
- Bei Verbindungs-/Auth-Fehlern gibt `_async_update_data` den letzten Datenstand zurück (kein `UpdateFailed`), damit Entitäten verfügbar bleiben. `switch.available` ist nur `True` wenn `wan_access is not None`.
- `unique_id` des Config-Entry = Seriennummer (`DeviceInfo:1/GetInfo/NewSerialNumber`); Entry-Titel = `NewModelName`. Im Router müssen „Zugriff für Anwendungen" (TR-064) und ggf. UPnP aktiviert sein.

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
# Domain-Konstante gegenüber manifest/Ordnername prüfen:
grep -rn '"domain"' custom_components/fritzbox_budget/manifest.json
grep -rn '^DOMAIN' custom_components/fritzbox_budget/const.py
```

Manueller End-to-End-Test: `custom_components/fritzbox_budget/` in das `config/custom_components/` einer HA-Installation kopieren, neu starten, Integration hinzufügen, im Options-Flow Geräte wählen und Log auf Fehler prüfen.

## Release-Prozess

1. `version` in `manifest.json` erhöhen (SemVer)
2. Commit auf `master`, Tag `vX.Y.Z` setzen, GitHub Release erstellen
3. Der Validate-Workflow prüft die HACS-Konformität automatisch (nur auf `master`)
