# Spoolman

[← Back to the README](../README.md)

[Spoolman](https://github.com/Donkie/Spoolman) keeps an inventory of your spools and how much filament is left on each. QIDI's Moonraker can already report filament use to it, but only for one spool at a time. With this project, each QIDI Box slot, and the external spool, can have its own spool, and the spool being charged follows the slot that's loaded.

## Setting it up

1. Run Spoolman on another computer on your network, for example with Docker. So that Fluidd's Spoolman card updates live, allow the address you open Fluidd at in Spoolman's `SPOOLMAN_CORS_ORIGIN` setting, for example `SPOOLMAN_CORS_ORIGIN=http://192.168.1.50`. Separate several addresses with commas. Without it, the card shows `Spoolman is blocking Fluidd's browser origin`; filament use is still recorded.
2. In Fluidd, open **Configuration**, edit `moonraker.conf`, and add:
   ```ini
   [spoolman]
   server: http://<spoolman computer's address>:7912
   ```
3. Restart Moonraker from Fluidd's power menu. The **Spoolman** card appears on the dashboard.

## Giving each slot its spool

- **In Fluidd:** with a slot loaded, choose **Change spool** on the Spoolman card. The spool becomes that slot's spool, and the console shows, for example, `Spoolman: 1B is spool 12.` With no Box slot loaded, it becomes the external spool's spool.
- **In the console:** `TLTG_SPOOLMAN_SLOT SLOT=<n> SPOOL=<id>` sets any slot's spool without loading it. Slots are numbered from 0, the same as `TLTG_BOX_MOTION SLOT=`, so 1A is slot 0 and 2A is slot 4. The external spool is slot 16. Spool IDs are shown in Spoolman.

| Command | What it does |
|---|---|
| `TLTG_SPOOLMAN_SLOT` | Lists each slot's spool and the loaded slot. |
| `TLTG_SPOOLMAN_SLOT SLOT=5 SPOOL=12` | Makes spool 12 slot 2B's spool. |
| `TLTG_SPOOLMAN_SLOT SLOT=5 SPOOL=0` | Clears slot 2B's spool. |
| `TLTG_SPOOLMAN_SLOT SPOOL=12` | Makes spool 12 the loaded slot's spool. |
| `TLTG_SPOOLMAN_SLOT RESET=1` | Clears every slot's spool. |

The spools are saved, so they survive restarts and updates.

## How filament use is charged

When the printer records a slot as loaded, that slot's spool becomes Spoolman's active spool. QIDI records the slot as soon as its filament reaches the Box hub, before the extruder draws it in, so the load's purge and everything printed until the next filament change are charged to that spool. Each print's history lists every spool it used.

- **A slot without a spool** makes no spool active, so its filament isn't charged to another slot's spool. Give it a spool to start recording it.
- **With no slot spools set,** the active spool is never changed, and Spoolman works as it does without this project.
- **A load that fails** before the filament reaches the extruder is still charged for the extruder's draw, about 30 mm, because Spoolman charges whatever the extruder moves.
- **Fluidd's spool prompt at print start** asks for one spool and gives it to whichever slot is loaded at that moment, which may not be the first one the print uses. If you give each slot its spool, turn off **Show spool selection dialog on print start** in Fluidd's Spoolman settings.

Install and update also fix two problems in QIDI's Moonraker that came from the Moonraker version it's based on, 0.9.3. After a filament change, the new spool wasn't charged until the extruder had pushed past where the previous spool's filament had reached, so the length a Box unload pulls back went uncharged on every change. And Moonraker's connection to Spoolman could drop and reconnect, because QIDI's copy of Tornado, the web library Moonraker uses, can close a connection early when it's kept alive with pings.
