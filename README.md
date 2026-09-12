# SMA Sunny Tripower – Active Power Limitation (Home Assistant custom integration)

Local, cloud-free Home Assistant custom integration to control the **active
power limitation** of an SMA Sunny Tripower 4.0 (`STP4.0-3AV-40`, firmware
`4.10.10.R`) over **Modbus TCP**.

> **⚠️ Unofficial, community project.** This is **not** an official SMA
> integration and is **not affiliated with, endorsed by, or supported by
> SMA Solar Technology AG**. It is provided **"as is", without warranty of
> any kind**, and is used **at your own risk**. Writing to Modbus registers
> that affect active power limitation can influence your inverter's grid
> feed-in behavior and, depending on your local grid operator rules, its
> regulatory compliance. Test carefully on your own hardware before relying
> on it, and make sure any change you make is compliant with the
> requirements of your grid operator/installer.

This integration is intentionally narrow in scope: it does **not** monitor AC
power, voltage, frequency or energy. If you need that, use the native Home
Assistant SMA integration.

## What you get

One Home Assistant **device**: `SMA Sunny Tripower 4.0`, with exactly two
entities:

| Entity | Type | Register | Description |
|---|---|---|---|
| `Operating Mode` | `select` | `40210` (U32) | Off / Manual setting in W / Manual setting in % / External active power setpoint |
| `Active Power Limit` | `number` (slider, 0–100 %) | `40214` (U32) | Active power limitation in % |

## Registers used

This integration reads and writes only the following registers. No other
registers are touched.

- **40210** – Operating mode active power setting (U32)
  - `303` → Off
  - `1077` → Manual setting in W
  - `1078` → Manual setting in %
  - `1079` → External active power setpoint
- **40214** – Active power limitation in % (U32, range 0–100). Only takes
  effect when `40210 = 1078`.

Modbus U32 values are transmitted as two 16-bit registers, **high word
first**: e.g. `20 → [0, 20]`, `1078 → [0, 1078]`, `4000 → [0, 4000]`.


## Installation

### Option A: HACS (custom repository)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**, add
   `https://github.com/marcogpg/ha-sma-power-control` with category
   **Integration**.
2. Install **"SMA Sunny Tripower"** from HACS, then restart Home Assistant.
3. Continue from step 3 below.

### Option B: Manual copy

1. Copy the `custom_components/sma_power_control/` folder into your Home
   Assistant `config/custom_components/` directory, so you end up with:

   ```
   config/custom_components/sma_power_control/__init__.py
   config/custom_components/sma_power_control/manifest.json
   config/custom_components/sma_power_control/...
   ```

2. Restart Home Assistant.

3. Go to **Settings → Devices & services → Add Integration**, search for
   **"SMA Sunny Tripower"**, and select it.

4. Fill in the form:
   - **Host**: e.g. `192.168.1.2`
   - **Port**: `502` (default)
   - **Modbus Unit ID**: `3` (default)
   - **Device name**: `SMA Sunny Tripower 4.0` (default, editable) — useful if
     you plan to add more than one inverter and want to tell them apart in
     the device list.

   Home Assistant will open a Modbus TCP connection and read register `40210`
   to validate the configuration before creating the entry.

5. Go to **Settings → Devices & services → SMA Sunny Tripower** and you will
   find the device (named as entered above, `SMA Sunny Tripower 4.0` by
   default) with its two entities.

No YAML configuration is needed or supported.

## Usage examples

- Set the inverter to manual percentage control and limit it to 20 %:
  1. Set `Operating Mode` → `Manual setting in %` (writes `1078` to `40210`).
  2. Set `Active Power Limit` → `20` (writes `20` to `40214`).
  - On a 4 kW inverter this corresponds to roughly 800 W.

- Turn the limitation off:
  - Set `Operating Mode` → `Off` (writes `303` to `40210`).

## Removing the integration

1. Go to **Settings → Devices & services → SMA Sunny Tripower**.
2. Click the device, then remove the config entry (the "..." menu → Delete,
   or the delete icon on the integration card).
3. Optionally delete the `custom_components/sma_power_control/` folder and
   restart Home Assistant if you don't plan to reinstall it. If installed via
   HACS, remove it from **HACS → Integrations** instead, which deletes the
   folder for you.