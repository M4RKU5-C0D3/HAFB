# Home Assistant FRITZ!Box Budget

[![HACS Custom Repository](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/M4RKU5-C0D3/HAFB) [![GitHub release](https://img.shields.io/github/v/release/M4RKU5-C0D3/HAFB?style=for-the-badge)](https://github.com/M4RKU5-C0D3/HAFB/releases) [![Validate](https://img.shields.io/github/actions/workflow/status/M4RKU5-C0D3/HAFB/validate.yml?branch=master&style=for-the-badge&label=Validate)](https://github.com/M4RKU5-C0D3/HAFB/actions/workflows/validate.yml)

Home Assistant Custom Integration **`fritzbox_budget`**: controls the internet access of individual devices on a FRITZ!Box with a daily time budget – similar to the parental controls of a Nintendo Switch. One config entry = one FRITZ!Box.

## Features

- **Managed devices** are selected via the options flow.
- Per device a **`switch`** (internet on/off) using the FRITZ!Box device lock (`X_AVM-DE_HostFilter`).
- Per device a **`sensor`** showing the remaining time today (budget + extensions − used time).
- **Daily budget** per device, reset daily at **03:00**.
- **Extensions** via the service `fritzbox_budget.extend_time` (15 / 30 / 60 minutes) – also before the budget runs out, limited by a daily cap.
- **Automatic shutdown** once the budget is exhausted.
- On connection or authentication errors the last known state is kept.

> The time calculation ("used time") is based on how long internet access was granted through this integration. The FRITZ!Box offers no API for the actual usage time per device – for a child's device this approximation is usually sufficient.

## Requirements

- A FRITZ!Box with **"Access for apps" (TR-064)** enabled under Home Network → Network → Network Settings → Home Network Access Settings (UPnP may also need to be enabled).
- A FRITZ!Box user with the **FRITZ!Box settings** permission (recommendation: create a separate user).

## Installation

### Via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=M4RKU5-C0D3&repository=HAFB&category=integration)

1. In HACS: go to **HACS → ⋮ → Custom repositories**
2. Add the repository URL `https://github.com/M4RKU5-C0D3/HAFB` with the category **Integration**
3. Click **Download** on "FRITZ!Box Budget"
4. Restart Home Assistant
5. Under **Settings → Devices & Services → Add Integration** search for **"FRITZ!Box Budget"** and enter your FRITZ!Box credentials

### Manually

1. Copy `custom_components/fritzbox_budget/` into `<config>/custom_components/fritzbox_budget/`
2. Restart Home Assistant
3. Under **Settings → Devices & Services → Add Integration** search for **"FRITZ!Box Budget"** and enter your FRITZ!Box credentials

## Setup

After adding the FRITZ!Box:

1. Open **Integration → Options**.
2. Select the devices you want to manage.
3. For each device set the **daily budget** (minutes) and the **max. extension per day** (minutes).

## Extensions

Grant a device extra time via the service `fritzbox_budget.extend_time`:

```yaml
service: fritzbox_budget.extend_time
data:
  device: "AA:BB:CC:DD:EE:FF"   # device MAC address
  minutes: 15                    # 15, 30 or 60
```

The extension takes effect immediately and is limited by the configured daily cap. Even if the device was already locked by the budget, the extension unlocks it again.

## Notification before shutdown

The integration does not send notifications itself. Using the remaining-time sensor (`sensor.<device>_remaining_time_today`) you can raise your own warnings via automation once the budget is almost used up – e.g. a numeric trigger at "≤ 30/20/10 minutes" and a dispatch via Gotify or similar to the desired device:

```yaml
automation:
  - alias: "Budget warning"
    trigger:
      - platform: numeric_state
        entity_id: sensor.kind_pc_remaining_time_today
        below: 10
    action:
      - service: notify.myservice
        data:
          message: "10 minutes of internet time left!"
```

## Data polling

- Update interval: 15 s, `DataUpdateCoordinator`.
- On connection or authentication errors the last known state is kept; entities are not marked as unavailable.

## Disclaimer

Personal project. It only controls your own FRITZ!Box via the local TR-064 interface.

## Vibe coding

Created with AI assistance via [opencode](https://opencode.ai) (model `big-pickle`), modeled on the reference project [HASH](https://github.com/M4RKU5-C0D3/HASH). All code was reviewed and released by a human maintainer.
