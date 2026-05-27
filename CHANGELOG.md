# Changelog

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
