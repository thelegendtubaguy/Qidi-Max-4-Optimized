# Fluidd

[← Back to the README](../README.md)

QIDI no longer updates the Fluidd that ships with the Max 4, version 1.30.5. The installer serves this project's build of current Fluidd instead, with QIDI's Max 4 additions plus the QIDI Box card, Box heater control, and Printer screen card.

**For what's in it and how to use it, see [thelegendtubaguy/fluidd](https://github.com/thelegendtubaguy/fluidd).**

## What the installer does

- **Installs the build in `~/tltg-fluidd`** and has the printer's web server serve it instead of QIDI's `~/fluidd`, which is left untouched. Updates replace the whole build.
- **Your settings, macros, and dashboard layout carry over,** because both versions keep them in the same place on the printer.
- **To check which one you're using,** look at the footer of any Fluidd page. This project's build reads `fluidd: v` followed by its version, `-tltg-`, and a commit ID.
- **After installing,** close every Fluidd tab and open Fluidd again. After that, open tabs switch to a newly installed version by themselves within a few minutes, or as soon as the tab is shown again.

If the installer doesn't recognize QIDI's web server configuration for Fluidd, it leaves it alone and QIDI's Fluidd stays in use, with the fixes earlier versions made to its Box card.

**To undo:** uninstalling switches back to QIDI's Fluidd and removes `~/tltg-fluidd`. Cards that only this project's Fluidd has go back to their default places on the dashboard.

## Printer screen

The installer adds a small `tltg-remote-screen` service that streams the printer's touchscreen to Fluidd's **Printer screen** card. It does no work until the card is expanded and only sends a new image when the screen changes. Only devices that can already use Fluidd can see the screen.

If the installer doesn't recognize the printer's web server configuration, the card says the screen is unavailable. Uninstall removes the service.

## Restart the touchscreen app

If the touchscreen freezes, restart it from Fluidd without SSH. Open Fluidd's power menu: `qidi-client`, QIDI's touchscreen app, is listed under services with **Restart**, **Stop**, and **Start**. **Stop** leaves the touchscreen off until you start it again or the printer reboots.
