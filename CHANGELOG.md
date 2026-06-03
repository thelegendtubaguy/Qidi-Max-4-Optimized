# Changelog

## 26.06.02.1
- Preserved the active print Z offset across startup reset, KAMP mesh save, and offset reapply.
- Kept retained-filament startup waiting at the purge chute while bed and chamber reach target temperature.
- Tracked retained QIDI Box filament from `slot_sync` so auto-runout reloads can be reused when the next print selects the reloaded slot.
- Fixed QIDI Studio end G-code compatibility by avoiding unsupported indexed completion-air-filtration placeholders.

## 26.05.27.1
- Removed hardcoded shaper algo for x and y

## 26.05.21.1
- Fixed legacy manual install reset when stock `config/KAMP` is a symlink

## 26.05.19.1
- Removed the older QIDI Max 4 firmware baseline from installer support
- Added system optimizations (DNS, APT, qidiclient, algo_app)

## 26.05.04.1
- Added probe accuracy and screw-tilt helper macros
- Added `TLTG_SET_BOX_TEMP` macro to be able to set the box temp from fluidd
- Installer hardening
- Optimized nozzle cleaning
- Clean nozzle post print
- Finalized slicer gcode contract
