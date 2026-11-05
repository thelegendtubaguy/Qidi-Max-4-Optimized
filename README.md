<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/images/valve-oil-logo-dark.png">
    <img alt="Valve Oil" src=".github/images/valve-oil-logo.png" width="520">
  </picture>
</h1>

Faster, fixed, and more capable QIDI printers: optimized Klipper macros, slicer start G-code, and a current Fluidd, installed and removed with one command. The installer detects your printer and installs what fits it.

<p>
  <a href="https://youtube.com/@TubaMakes"><img alt="Subscribe to Tuba Makes on YouTube" src="https://img.shields.io/badge/YouTube-Tuba%20Makes-FF0000?style=for-the-badge&logo=youtube&logoColor=white"></a>
  <a href="https://tubag.uy/patreon"><img alt="Support Tuba Makes on Patreon" src="https://img.shields.io/badge/Patreon-Support%20me-F96854?style=for-the-badge&logo=patreon&logoColor=white"></a>
</p>

If you want to help support content like this, consider subscribing on YouTube or joining on Patreon!

> [!CAUTION]
> I refuse to be responsible for your printer.  PLEASE watch prints start ensuring the printer doesn't do something horrible like gouge your bed and be ready to cut power at a moment's notice.

## Supported printers

| Printer | QIDI firmware |
|---|---|
| QIDI Max 4 | `01.01.06.03`, `01.01.06.04`, `01.01.06.05`, `01.01.07.01` |

Support for the QIDI Plus 5 is in progress. On any other printer or firmware, the installer stops before changing anything.

## Install

1. SSH into your printer `qidi@<your printer's ip>`.
2. Run this on your printer:
   ```bash
   /bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/valve-oil/releases/latest/download/install-latest.sh)"
   ```
3. Follow the prompts.
4. In OrcaSlicer 2.4.0 or later, subscribe to the [OrcaCloud bundle](https://cloud.orcaslicer.com/b/4c4b3b74c745). For QIDI Studio or older Orca, [copy the start G-code by hand](docs/install.md#slicer-start-g-code).
5. Slice using your printer's TLTG Optimized profile, `Qidi X-Max 4 0.4 nozzle - TLTG Optimized GCode` on the Max 4. Optionally, make a copy and customize it.

On a Max 4 with firmware `01.01.07.01`, the installer first asks whether to flash a fix for the toolhead board's accelerometer. **The default is No.** If you say yes, **run input shaper calibration before bed leveling or printing**; see [Firmware fixes](docs/firmware.md).

[Dry run, automatic updates, updating, and uninstalling →](docs/install.md)

## What you get

### Faster prints
- Shorter print starts and filament changes: quicker homing and probing, and less fixed waiting around cuts, wipes, and saves.
- Box filament stays loaded between prints, so the next print skips the unload and reload.
- Options to reuse a saved bed mesh, warm up the bed, chamber, and nozzle in turn, and start once the chamber reaches a minimum temperature.

[Print start and end →](docs/print-start.md)

### QIDI Box
- Faster, tunable loading and unloading.
- Box heater control from Fluidd, and Box processor temperatures.
- Edit QIDI's filament list from Fluidd, including brands such as Bambu, Overture, and Polymaker.

[QIDI Box →](docs/qidi-box.md)

### Spoolman
- Each QIDI Box slot can have its own Spoolman spool, and filament use is charged to the loaded slot's spool.

[Spoolman →](docs/spoolman.md)

### Current Fluidd
- [This project's build of current Fluidd](https://github.com/thelegendtubaguy/fluidd), replacing the old Fluidd QIDI ships (1.30.5 on the Max 4), which QIDI no longer updates. Your settings carry over.
- A redesigned QIDI Box card, a live view of the touchscreen, and a restart button for a frozen touchscreen.

[Installing and undoing it →](docs/fluidd.md)

### Fixes for QIDI bugs
- The real error instead of a bare `MCU shutdown`.
- Fewer Boxes dropping with `Lost communication with MCU 'mcu_boxN'`.
- Multi-plate 3MF files print the right plate from Fluidd, reprints, and the job queue.

[All fixes →](docs/fixes.md)

### Tools
- A guided nozzle load-cell check, probe accuracy, and bed screw helpers.
- A switch to stop the external spool's runout sensor from pausing prints.

[Tools →](docs/tools.md)

## More

- [Every setting and command in one table](docs/settings.md)
- [If something goes wrong](docs/troubleshooting.md): restoring backups and reporting problems
- [Optional firmware fixes](docs/firmware.md) for the Max 4 toolhead board and the QIDI Box
- [What the installer changes on your printer](docs/under-the-hood.md)
- [Changelog](CHANGELOG.md)
- [Help test releases](TESTING.md) and [run the dev branch](DEVELOPMENT.md)

## License

Repository-authored content is licensed under [GPLv3](LICENSE). Third-party components and license texts are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
