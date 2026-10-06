# Offline CS1237 reproduction

These locally authored harnesses predate inspection of the external calibration project. They exercise the recovered QIDI firmware contract, not that project's implementation. No vendor firmware, compiled module, or serial transport source is included.

Supply an extracted firmware workspace containing:

- `firmware/QD_MAX4_THR_02.02.01.08_20260303.bin`
- `host/serialhdl.py`
- `host/cs1237.cpython-39-aarch64-linux-gnu.so` for the compiled-host probe

Archive and binary provenance are recorded in [local firmware findings](../../local-firmware-findings.md). The MCU harnesses reject an unexpected THR hash. The dictionary is decoded directly from that binary; no separate dictionary file is needed.

With Unicorn 2.1.4 installed, run from this directory, replacing `WORKSPACE` with the extracted input directory:

```sh
python3 decode_protocol.py WORKSPACE
python3 emulate_cs1237.py WORKSPACE
python3 edge_cases.py WORKSPACE
```

Compare the JSON outputs with `protocol-map.json`, `emulation-results.json`, and `edge-case-results.json`. The edge-case harness extracts and executes only the supplied vendor `SerialRetryCommand` class against a fake transport; it does not import or open a serial device.

`host_probe.py WORKSPACE/host` requires ARM64 CPython 3.9 and loads the compiled vendor CS1237 module with command spies. Run it in an isolated container with networking disabled, read-only mounts/root, dropped capabilities, and resource limits, not on the printer. `host-probe.txt` preserves the earlier output; object addresses are incidental, while command bindings and sends are the evidence.

The synthetic fixtures establish control flow and decoding only. They do not reproduce peripheral timing, noise, throughput, or physical safety. They are research harnesses, not part of the installed package or core test suite.
