from __future__ import annotations

import copy
import io
import json
import os
import shutil
import unittest
import urllib.error
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

from installer.runtime import messages, system_optimizations
from installer.runtime import fluidd_box_filaments as fluidd_patch
from installer.runtime import moonraker_allowed_services
from installer.runtime import moonraker_speedups
from installer.runtime import remote_screen
from installer.runtime import cpu_governor
from installer.runtime import restart_on_exit
from installer.runtime import webcam_id
from installer.runtime import service_priority
from installer.runtime import zram_swap
from installer.runtime.fluidd_box_filaments import OPERATION as FLUIDD_BOX_OPERATION, PATCH_MARKER
from installer.runtime.fluidd_filament_config import OPERATION as FILAMENT_CONFIG_OPERATION
from installer.runtime.klipper_box_config import OPERATION as KLIPPER_BOX_OPERATION
from installer.runtime.klipper_print_stats_manager import OPERATION as KLIPPER_PRINT_STATS_OPERATION
from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.compatibility import load_supported_upgrade_sources
from installer.runtime.errors import InstalledPackageValidationError
from installer.runtime.manifest import load_manifest
from installer.runtime.models import SystemOptimizationCliOptions
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.runtime.state_file import StateValidationError, load_installed_state, write_installed_state
from installer.runtime.system_optimizations import (
    SYSTEM_ROOT_ENV,
    SystemOptimizationApplyError,
    SystemOptimizationRecoveryError,
    _compact_host_ledger,
    _replace_system_ledger,
    apply_system_optimizations,
    _journal_path,
    recover_pending_system_optimization,
    validate_system_ledger,
)
from installer.runtime.uninstall import run_uninstall
from installer.tests.helpers import (
    FIXTURES_ROOT,
    REPO_ROOT,
    build_env,
    copy_base_runtime,
    fake_host_run,
    fake_system_root,
    moonraker_urlopen,
    snapshot_tree,
    with_fluidd_build,
    with_moonraker_speedups,
)


class SystemOptimizationFlowTests(unittest.TestCase):
    def test_system_optimization_dry_run_install_and_uninstall_lifecycle(self):
        printer_root = copy_base_runtime()
        system_root = fake_system_root(
            include_moonraker_cache=True,
            include_fluidd_bundle=True,
            include_filament_config=True,
            include_klipper_box_config=True,
            include_klipper_print_stats_manager=True,
            include_nginx_site=True,
            include_moonraker_asvc=True,
            include_moonraker_metadata=True,
        )
        host_run = fake_host_run(system_root)
        moonraker = system_root / "home/qidi/moonraker/moonraker/components/file_manager/file_manager.py"
        moonraker.write_bytes(moonraker.read_bytes().replace(b"\n", b"\r\n"))
        moonraker_before = moonraker.read_bytes()
        moonraker.chmod(0o640)
        fluidd = system_root / "home/qidi/fluidd/assets/index-DlFvHGAh.js"
        fluidd_before = fluidd.read_bytes()
        service_worker = system_root / "home/qidi/fluidd/sw.js"
        service_worker_before = service_worker.read_bytes()
        box_config = system_root / "home/qidi/klipper/klippy/extras/box_config.py"
        box_config_before = box_config.read_bytes()
        stats_manager = system_root / "home/qidi/klipper/klippy/extras/print_stats_manager.py"
        stats_manager_before = stats_manager.read_bytes()
        klippy_apis = system_root / "home/qidi/moonraker/moonraker/components/klippy_apis.py"
        klippy_apis_before = klippy_apis.read_bytes()
        metadata = system_root / "home/qidi/moonraker/moonraker/components/file_manager/metadata.py"
        metadata_before = metadata.read_bytes()
        spoolman = system_root / "home/qidi/moonraker/moonraker/components/spoolman.py"
        spoolman_before = spoolman.read_bytes()
        nginx_site = system_root / remote_screen.NGINX_SITE.lstrip("/")
        nginx_site_before = nginx_site.read_bytes()
        screen_unit = system_root / remote_screen.UNIT_FILE.lstrip("/")
        screen_server = system_root / remote_screen.SERVER_FILE.lstrip("/")
        screen_state = system_root / "systemd" / f"{remote_screen.UNIT}.json"
        asvc = system_root / moonraker_allowed_services.FILE.lstrip("/")
        asvc_before = asvc.read_bytes()
        before = snapshot_tree(system_root)
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(system_root)
        boot_id = printer_root / "boot-id"
        boot_id.write_text("boot-one\n", encoding="utf-8")
        env["TLTG_OPTIMIZED_BOOT_ID_PATH"] = str(boot_id)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        compatibility = load_supported_upgrade_sources(
            REPO_ROOT / "installer/supported_upgrade_sources.yaml"
        )
        stream = io.StringIO()

        result = run_install(
            paths,
            manifest,
            PlainReporter(stream),
            dry_run=True,
            urlopen=moonraker_urlopen(),
            environ=env,
            system_options=SystemOptimizationCliOptions(disable_ai_detection=True),
            run=host_run,
        )

        self.assertTrue(result.dry_run)
        self.assertEqual(snapshot_tree(system_root), before)
        self.assertFalse((printer_root / manifest.state_file).exists())
        self.assertIn("System optimizations dry-run:", stream.getvalue())

        install_responses = io.StringIO("yes\nno\nunused\n")
        base_urlopen = moonraker_urlopen(
            saved_variables_path=paths.config_root / "saved_variables.cfg"
        )
        install_idle_checks = 0
        service_events = []

        def install_urlopen(request, timeout=0):
            nonlocal install_idle_checks
            url = getattr(request, "full_url", str(request))
            if url == paths.moonraker_url:
                install_idle_checks += 1
            if url.endswith("/server/info"):
                service_events.append("moonraker answered")
            if url.endswith("/machine/services/restart"):
                service_events.append("klipper.service via Moonraker")
            return base_urlopen(request, timeout=timeout)

        def install_run(command, **kwargs):
            if list(command)[-3:-1] == ["systemctl", "restart"]:
                service_events.append(list(command)[-1])
            if list(command)[-2:] == ["systemctl", "daemon-reload"]:
                service_events.append("daemon-reload")
            return host_run(command, **kwargs)

        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=install_responses,
            urlopen=install_urlopen,
            environ=env,
            run=install_run,
        )
        self.assertEqual(install_idle_checks, 2)
        # Every host change is in place before any service restarts, and each restarts once. Zram swap starts first,
        # the touchscreen app restarts after Moonraker answers again, and Klipper restarts once for its host and source
        # changes.
        restarts = [
            zram_swap.UNIT,
            "moonraker.service",
            "moonraker answered",
            remote_screen.UNIT,
            "qidi-client.service",
            cpu_governor.SERVICE,
            "klipper.service via Moonraker",
        ]
        self.assertEqual(service_events[-len(restarts):], restarts)
        self.assertEqual(set(service_events[:-len(restarts)]), {"daemon-reload"})
        # Klipper and Moonraker restart after any exit outside systemd, without restarting them to apply it.
        for dropin in restart_on_exit.FILES.values():
            self.assertEqual((system_root / dropin.lstrip("/")).read_text(encoding="utf-8"), restart_on_exit.CONTENT)
        # QIDI's camera ID script waits for the camera's index0 link from the next boot, without running it now.
        self.assertEqual((system_root / webcam_id.FILE.lstrip("/")).read_text(encoding="utf-8"), webcam_id.CONTENT)
        self.assertNotIn(webcam_id.UNIT, service_events)
        # Klipper gets the CPU before Moonraker, and both before the touchscreen app.
        for operation, dropin in service_priority.FILES.items():
            self.assertIn(f"Nice={service_priority.NICE[operation]}\n", (system_root / dropin.lstrip("/")).read_text(encoding="utf-8"))
        # Zram swap's modules and boot script are root-owned under /usr/local, and its unit is enabled.
        zram = system_root / zram_swap.DESTINATION.lstrip("/")
        zram_unit = system_root / zram_swap.UNIT_FILE.lstrip("/")
        for module in manifest.system_optimizations.zram_swap.modules:
            self.assertEqual((zram / f"{module.name}.ko").read_bytes(), (REPO_ROOT / "installer" / module.archive).read_bytes())
        self.assertEqual((zram / zram_swap.SCRIPT).stat().st_mode & 0o777, 0o755)
        self.assertIn("insmod", (zram / zram_swap.SCRIPT).read_text(encoding="utf-8"))
        self.assertEqual(zram_unit.read_text(encoding="utf-8"), zram_swap.UNIT_CONTENT)
        self.assertEqual(json.loads((system_root / "systemd" / f"{zram_swap.UNIT}.json").read_text(encoding="utf-8"))["enabled"], "enabled")
        self.assertIn('GOVERNOR="performance"\n', (system_root / cpu_governor.FILE.lstrip("/")).read_text(encoding="utf-8"))
        # They run already, and the installer recommends a reboot to confirm they start on their own.
        self.assertTrue(paths.reboot_recommended_path.exists())
        paths.reboot_recommended_path.unlink()
        self.assertEqual(install_responses.readline(), "unused\n")
        self.assertTrue((system_root / "etc/resolv.conf").is_symlink())
        self.assertIn(
            "deb http://deb.debian.org/debian bullseye",
            (system_root / "etc/apt/sources.list").read_text(encoding="utf-8"),
        )
        rockchip = manifest.system_optimizations.rockchip_root_sync
        dropin = system_root / rockchip.dropin.lstrip("/")
        self.assertEqual(dropin.read_text(encoding="utf-8"), rockchip.dropin_content)
        self.assertTrue(paths.host_reboot_marker_path.exists())
        state = load_installed_state(printer_root / manifest.state_file)
        self.assertIn("rockchip_root_sync", state.system_ledger["restore_preimages"])
        probe_helper = paths.managed_klipper_root / "klippy/extras/tltg_probe_test.py"
        self.assertEqual(probe_helper.read_bytes(), (REPO_ROOT / "installer/klipper/tltg/probe_test.py").read_bytes())
        # Earlier builds recorded the probe helper as a host operation; loading the state drops it.
        retired = copy.deepcopy(state.system_ledger)
        retired["restore_preimages"]["klipper_probe_signal_test"] = {"path": "/home/qidi/klipper/klippy/extras/tltg_probe_test.py", "exists": False}
        retired["outcomes"]["klipper_probe_signal_test"] = {"status": "applied", "source": "yes_install"}
        write_installed_state(printer_root / manifest.state_file, _replace_system_ledger(state, retired))
        state = load_installed_state(printer_root / manifest.state_file)
        self.assertNotIn("klipper_probe_signal_test", state.system_ledger["restore_preimages"])
        self.assertNotIn("klipper_probe_signal_test", state.system_ledger["outcomes"])
        self.assertEqual(state.system_ledger["schema_version"], 2)
        self.assertNotIn("actions", state.system_ledger)
        self.assertIn("rockchip_root_sync", state.system_ledger["committed_transactions"])
        cache_id = system_optimizations.MOONRAKER_CACHE_OPERATION
        self.assertIn(cache_id, state.system_ledger["restore_preimages"])
        self.assertNotEqual(moonraker.read_bytes(), moonraker_before)
        self.assertIn(b"\r\n", moonraker.read_bytes())
        self.assertEqual(moonraker.stat().st_mode & 0o777, 0o640)
        self.assertIn(b"            plateindex = self._tltg_3mf_plate_index(filename)\r\n", klippy_apis.read_bytes())
        # Fluidd's Box slot dialog gets the filaments a file uses, for the plate a 3MF prints.
        self.assertIn("plate_index = _3mf_selected_plate_index(", metadata.read_text(encoding="utf-8"))
        self.assertIn("each plate's own filaments", metadata.read_text(encoding="utf-8"))
        self.assertIn(b"        self._highest_epos = self._last_epos\r\n", spoolman.read_bytes())
        self.assertIn(FLUIDD_BOX_OPERATION, state.system_ledger["restore_preimages"])
        self.assertIn(PATCH_MARKER.encode(), fluidd.read_bytes())
        self.assertIn(b"Math.floor(u/4)===t-1", fluidd.read_bytes())
        self.assertIn(b"enableFullDisplay:!0", fluidd.read_bytes())
        self.assertIn(b"LOAD_FILAMENT_CONTROL", fluidd.read_bytes())
        self.assertIn(fluidd_patch.PRINT_SLOT_CHANGE_PATCHED.encode(), fluidd.read_bytes())
        self.assertIn(fluidd_patch.BOX_MOTION_START.encode(), fluidd.read_bytes())
        self.assertIn(b"t(TltgBoxMotion)", fluidd.read_bytes())
        self.assertIn(fluidd_patch.SERVICE_WORKER_OPERATION, state.system_ledger["restore_preimages"])
        self.assertIn(b'{"revision":"tltg-optimized-', service_worker.read_bytes())
        self.assertIn(fluidd_patch.SERVICE_WORKER_TAKEOVER_PATCHED.encode(), service_worker.read_bytes())
        self.assertIn(KLIPPER_BOX_OPERATION, state.system_ledger["restore_preimages"])
        self.assertIn(b"config.access_tracking if module == 'heater_generic'", box_config.read_bytes())
        self.assertNotIn(b"\n", box_config.read_bytes().replace(b"\r\n", b""))
        self.assertIn(KLIPPER_PRINT_STATS_OPERATION, state.system_ledger["restore_preimages"])
        self.assertIn(b"if self.printer.is_shutdown() or getattr(self, '_tltg_resetting', False):", stats_manager.read_bytes())
        self.assertNotIn(b"\n", stats_manager.read_bytes().replace(b"\r\n", b""))
        filament_config = manifest.system_optimizations.fluidd_filament_config
        filament_link = printer_root / filament_config.link
        self.assertEqual(os.readlink(filament_link), filament_config.target)
        self.assertIn(FILAMENT_CONFIG_OPERATION, state.system_ledger["restore_preimages"])
        self.assertIn(b"TltgScreenCard:TltgScreenCard", fluidd.read_bytes())
        self.assertIn(b'{id:"tltg-screen-card",enabled:!0,collapsed:!0}', fluidd.read_bytes())
        self.assertIn(fluidd_patch.QIDIBOX_START.encode(), fluidd.read_bytes())
        self.assertIn(fluidd_patch.QIDIBOX_HIDDEN_PATCHED.encode(), fluidd.read_bytes())
        self.assertIn(b'{id:"tltg-qidi-box-card",enabled:!0,collapsed:!1}', fluidd.read_bytes())
        self.assertEqual(screen_unit.read_text(encoding="utf-8"), remote_screen.UNIT_CONTENT)
        self.assertEqual(screen_server.read_bytes(), remote_screen.SERVER_PAYLOAD.read_bytes())
        self.assertEqual(json.loads(screen_state.read_text(encoding="utf-8"))["enabled"], "enabled")
        # Without a package Fluidd build, nginx keeps serving QIDI's patched bundle.
        self.assertEqual(nginx_site.read_bytes(), nginx_site_before)
        self.assertEqual(state.system_ledger["outcomes"][system_optimizations.FLUIDD_BUILD_OPERATION]["status"], "missing")
        # Without the package's wheels, Moonraker is never pointed at a speedups directory.
        self.assertEqual(state.system_ledger["outcomes"][moonraker_speedups.OPERATION]["status"], "missing")
        self.assertEqual(state.system_ledger["outcomes"][moonraker_speedups.PATH_OPERATION]["status"], "skipped")
        self.assertEqual(asvc.read_bytes(), asvc_before + b"\nqidi-client\n")
        fluidd_current = fluidd.read_bytes()
        # Earlier package versions left owned Fluidd patches, including an older Box motion section, that updates must replace in place.
        fluidd_previous = fluidd_before.decode().replace(fluidd_patch.SLOT_PARSE_STOCK, fluidd_patch.SLOT_PARSE_PATCHED).replace(
            fluidd_patch.FILAS_LIST_STOCK, fluidd_patch._filas_list_patched_v1()
        ).replace(
            fluidd_patch.BOX_MOTION_DEFINE_STOCK,
            fluidd_patch.BOX_MOTION_DEFINE_HEAD + fluidd_patch.BOX_MOTION_START + "const TltgBoxMotion={render:h=>h()};"
            + fluidd_patch.BOX_MOTION_END + fluidd_patch.BOX_MOTION_DEFINE_TAIL,
        ).replace(fluidd_patch.BOX_MOTION_RENDER_STOCK, fluidd_patch.BOX_MOTION_RENDER_PATCHED).encode()
        fluidd.write_bytes(fluidd_previous)
        prior_preimage = state.system_ledger["restore_preimages"][cache_id]
        fluidd_preimage = state.system_ledger["restore_preimages"][FLUIDD_BOX_OPERATION]
        cache_policy = copy.deepcopy({**state.system_ledger, "policy": {"system_optimizations": "disabled", "ai_detection": "unset"}})
        cache_policy["outcomes"][FLUIDD_BOX_OPERATION]["postflight"]["sha256"] = __import__("hashlib").sha256(fluidd_previous).hexdigest()
        reconciled = apply_system_optimizations(
            paths=paths, spec=manifest.system_optimizations, ledger=cache_policy,
            reporter=PlainReporter(io.StringIO()), input_stream=None, environ=env,
            source="auto_update_reconcile", run=host_run,
            urlopen=moonraker_urlopen(),
        )
        self.assertEqual(reconciled["restore_preimages"][cache_id], prior_preimage)
        # Runs that change none of them don't recommend another reboot.
        self.assertFalse(paths.reboot_recommended_path.exists())
        self.assertEqual(fluidd.read_bytes(), fluidd_current)
        self.assertEqual(reconciled["restore_preimages"][FLUIDD_BOX_OPERATION], fluidd_preimage)
        self.assertEqual(os.readlink(filament_link), filament_config.target)
        # Updates replace the screen service from an earlier package version.
        prior_server = remote_screen.SERVER_MARKER.encode() + b"print('earlier screen service')\n"
        screen_server.write_bytes(prior_server)
        reconciled["outcomes"][remote_screen.SERVER_OPERATION]["postflight"]["sha256"] = __import__("hashlib").sha256(prior_server).hexdigest()
        reconciled = apply_system_optimizations(
            paths=paths, spec=manifest.system_optimizations, ledger=reconciled,
            reporter=PlainReporter(io.StringIO()), input_stream=None, environ=env,
            source="auto_update_reconcile", run=host_run,
            urlopen=moonraker_urlopen(),
        )
        self.assertEqual(screen_server.read_bytes(), remote_screen.SERVER_PAYLOAD.read_bytes())
        self.assertFalse(reconciled["restore_preimages"][remote_screen.SERVER_OPERATION]["exists"])

        # Serving the package Fluidd build retires QIDI's bundle patches, and Moonraker gets the speedup packages; a
        # failure first rolls both back.
        manifest = with_moonraker_speedups(with_fluidd_build(manifest))
        build = system_root / "home/qidi/tltg-fluidd"
        previous_build = system_root / "home/qidi/tltg-fluidd.tltg-previous"
        marker = build / ".tltg-optimized-fluidd"
        speedups = system_root / moonraker_speedups.DESTINATION.lstrip("/")
        previous_speedups = system_root / moonraker_speedups.PREVIOUS.lstrip("/")
        speedups_marker = speedups / moonraker_speedups.MARKER
        speedups_path = system_root / moonraker_speedups.PATH_FILE.lstrip("/")
        speedups_digest = moonraker_speedups.digest(wheel.sha256 for wheel in manifest.system_optimizations.moonraker_speedups.wheels)

        def failing_restart(unit):
            failed = False

            def run(command, **kwargs):
                nonlocal failed
                if not failed and list(command)[-3:] == ["systemctl", "restart", unit]:
                    failed = True
                    return CompletedProcess(command, 1, stdout="", stderr="restart failed")
                return host_run(command, **kwargs)
            return run

        def reconcile(ledger, run=host_run):
            return apply_system_optimizations(
                paths=paths, spec=manifest.system_optimizations, ledger=ledger,
                reporter=PlainReporter(io.StringIO()), input_stream=None, environ=env,
                source="auto_update_reconcile", run=run,
                urlopen=moonraker_urlopen(),
            )

        with self.assertRaises(SystemOptimizationApplyError):
            reconcile(reconciled, failing_restart("nginx.service"))
        self.assertFalse(build.exists())
        self.assertFalse(speedups.exists())
        self.assertFalse(speedups_path.exists())
        self.assertEqual(nginx_site.read_bytes(), nginx_site_before)
        self.assertEqual(fluidd.read_bytes(), fluidd_current)
        reconciled = reconcile(reconciled)
        self.assertEqual(marker.read_text(encoding="utf-8"), manifest.system_optimizations.fluidd_build.sha256 + "\n")
        self.assertEqual((build / "assets/index.js").stat().st_mode & 0o777, 0o644)
        self.assertEqual(speedups_marker.read_text(encoding="utf-8"), speedups_digest + "\n")
        self.assertEqual((speedups / "msgspec/_core.so").stat().st_mode & 0o777, 0o755)
        self.assertEqual((speedups / "uvloop/__init__.py").stat().st_mode & 0o777, 0o644)
        self.assertEqual(speedups_path.read_text(encoding="utf-8"), moonraker_speedups.PATH_CONTENT)
        self.assertIn(b"\r\n    root /home/qidi/tltg-fluidd;\r\n    gzip_static on;\r\n", nginx_site.read_bytes())
        self.assertIn(b"location /tltg-screen/ {\r\n", nginx_site.read_bytes())
        self.assertNotIn(b"\n", nginx_site.read_bytes().replace(b"\r\n", b""))
        self.assertEqual(fluidd.read_bytes(), fluidd_before)
        self.assertEqual(service_worker.read_bytes(), service_worker_before)
        self.assertNotIn(FLUIDD_BOX_OPERATION, reconciled["restore_preimages"])
        self.assertNotIn(fluidd_patch.SERVICE_WORKER_OPERATION, reconciled["restore_preimages"])
        self.assertEqual(reconciled["outcomes"][FLUIDD_BOX_OPERATION]["status"], "retired")
        # Updates replace an earlier build and earlier speedups, which come back if a later change fails.
        marker.write_text("0" * 64 + "\n", encoding="utf-8")
        speedups_marker.write_text("0" * 64 + "\n", encoding="utf-8")
        screen_server.write_bytes(prior_server)
        reconciled["outcomes"][remote_screen.SERVER_OPERATION]["postflight"]["sha256"] = __import__("hashlib").sha256(prior_server).hexdigest()
        # A site that an earlier version switched to the build, before it served the build's gzip copies.
        prior_site = nginx_site.read_bytes().replace(b"    gzip_static on;\r\n", b"", 1)
        nginx_site.write_bytes(prior_site)
        reconciled["outcomes"][remote_screen.NGINX_OPERATION]["postflight"]["sha256"] = __import__("hashlib").sha256(prior_site).hexdigest()
        with self.assertRaises(SystemOptimizationApplyError):
            reconcile(reconciled, failing_restart(remote_screen.UNIT))
        self.assertEqual(marker.read_text(encoding="utf-8"), "0" * 64 + "\n")
        self.assertFalse(previous_build.exists())
        self.assertEqual(speedups_marker.read_text(encoding="utf-8"), "0" * 64 + "\n")
        self.assertFalse(previous_speedups.exists())
        self.assertEqual(nginx_site.read_bytes(), prior_site)
        reconciled = reconcile(reconciled)
        self.assertEqual(marker.read_text(encoding="utf-8"), manifest.system_optimizations.fluidd_build.sha256 + "\n")
        self.assertFalse(previous_build.exists())
        self.assertEqual(speedups_marker.read_text(encoding="utf-8"), speedups_digest + "\n")
        self.assertFalse(previous_speedups.exists())
        self.assertEqual(nginx_site.read_bytes().count(b"    gzip_static on;\r\n"), 1)
        write_installed_state(printer_root / manifest.state_file, _replace_system_ledger(state, reconciled))

        # Declining the system-restoration prompt keeps only the optional OS optimizations; everything install makes
        # regardless of policy is always undone. Moonraker stays unreachable for a while after restoration restarts
        # it, and the pending Klipper restart still runs once it answers again.
        moonraker_down = 0

        def uninstall_run(command, **kwargs):
            nonlocal moonraker_down
            if list(command)[-3:] == ["systemctl", "restart", "moonraker.service"]:
                moonraker_down = 3
            return host_run(command, **kwargs)

        base_uninstall_urlopen = moonraker_urlopen()

        def uninstall_urlopen(request, *args, **kwargs):
            nonlocal moonraker_down
            if moonraker_down:
                moonraker_down -= 1
                raise urllib.error.URLError("Moonraker is restarting")
            return base_uninstall_urlopen(request, *args, **kwargs)

        with mock.patch("installer.runtime.safety.time.sleep"):
            run_uninstall(
                paths,
                manifest,
                compatibility,
                PlainReporter(io.StringIO()),
                input_stream=io.StringIO("yes\nno\nno\n"),
                urlopen=uninstall_urlopen,
                environ=env,
                run=uninstall_run,
            )
        self.assertFalse(paths.restart_marker_path.exists())
        self.assertFalse((printer_root / manifest.state_file).exists())
        self.assertNotEqual((system_root / "etc/apt/sources.list").read_text(encoding="utf-8"), "old apt\n")
        self.assertTrue(dropin.exists())
        self.assertEqual(moonraker.read_bytes(), moonraker_before)
        self.assertEqual(moonraker.stat().st_mode & 0o777, 0o640)
        self.assertEqual(fluidd.read_bytes(), fluidd_before)
        self.assertEqual(service_worker.read_bytes(), service_worker_before)
        self.assertEqual(box_config.read_bytes(), box_config_before)
        self.assertEqual(stats_manager.read_bytes(), stats_manager_before)
        self.assertEqual(klippy_apis.read_bytes(), klippy_apis_before)
        self.assertEqual(metadata.read_bytes(), metadata_before)
        self.assertEqual(spoolman.read_bytes(), spoolman_before)
        self.assertFalse(probe_helper.exists())
        self.assertFalse(filament_link.is_symlink())
        self.assertEqual(nginx_site.read_bytes(), nginx_site_before)
        self.assertEqual(asvc.read_bytes(), asvc_before)
        self.assertFalse(build.exists())
        self.assertFalse(speedups.exists())
        self.assertFalse(speedups_path.exists())
        self.assertTrue(speedups_path.parent.is_dir())
        self.assertFalse(screen_unit.exists())
        self.assertFalse(screen_server.exists())
        self.assertEqual(json.loads(screen_state.read_text(encoding="utf-8"))["enabled"], "disabled")
        for dropin in restart_on_exit.FILES.values():
            self.assertFalse((system_root / dropin.lstrip("/")).exists())
        self.assertFalse((system_root / webcam_id.FILE.lstrip("/")).exists())
        for dropin in service_priority.FILES.values():
            self.assertFalse((system_root / dropin.lstrip("/")).exists())
        # Zram swap and the CPU governor are optional OS optimizations, so declining restoration keeps them.
        self.assertTrue((zram / zram_swap.MARKER).is_file())
        self.assertEqual((system_root / cpu_governor.FILE.lstrip("/")).read_text(encoding="utf-8"), cpu_governor.CONTENT)
        self.assertEqual(zram_unit.read_text(encoding="utf-8"), zram_swap.UNIT_CONTENT)

    def test_os_optimizations_apply_whatever_an_earlier_install_chose(self):
        printer_root = copy_base_runtime()
        root = fake_system_root()
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        boot_id = printer_root / "boot-id"
        boot_id.write_text("boot-one\n", encoding="utf-8")
        env["TLTG_OPTIMIZED_BOOT_ID_PATH"] = str(boot_id)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        state_path = printer_root / manifest.state_file
        urlopen = moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg")
        # An earlier install that declined the OS optimizations recorded that choice and changed nothing on the host.
        run_install(paths, manifest, PlainReporter(io.StringIO()), input_stream=None, urlopen=urlopen, environ=env)
        state = load_installed_state(state_path)
        declined = {**(state.system_ledger or {}), "policy": {"system_optimizations": "disabled", "ai_detection": "unset"}}
        write_installed_state(state_path, _replace_system_ledger(state, declined))

        env[SYSTEM_ROOT_ENV] = str(root)
        host_run = fake_host_run(root)
        system_optimizations.maybe_reconcile_system_optimizations(
            paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()), environ=env, run=host_run, urlopen=urlopen,
        )

        # An automatic update applies them anyway, leaving AI detection on.
        state = load_installed_state(state_path)
        self.assertEqual(state.system_ledger["policy"], {"system_optimizations": "enabled", "ai_detection": "keep_enabled"})
        self.assertEqual((root / zram_swap.UNIT_FILE.lstrip("/")).read_text(encoding="utf-8"), zram_swap.UNIT_CONTENT)
        self.assertTrue(paths.host_reboot_marker_path.exists())
        self.assertTrue(paths.reboot_recommended_path.exists())
        self.assertEqual(json.loads((root / "systemd/algo_app.service.json").read_text(encoding="utf-8"))["enabled"], "enabled")

        # With AI detection already off, an install asks nothing about the OS optimizations.
        algo_app = root / "systemd/algo_app.service.json"
        algo_app.write_text(json.dumps({"exists": True, "service": "algo_app.service", "enabled": "disabled", "active": "inactive"}), encoding="utf-8")
        report = io.StringIO()
        run_install(paths, manifest, PlainReporter(report), input_stream=io.StringIO("no\nno\nno\n"), urlopen=urlopen, environ=env, run=host_run)
        self.assertNotIn(messages.AI_DETECTION_PROMPT, report.getvalue())
        self.assertEqual(load_installed_state(state_path).system_ledger["policy"]["system_optimizations"], "enabled")

    def test_unreviewed_host_files_are_preserved_without_blocking_other_patches(self):
        printer_root = copy_base_runtime()
        root = fake_system_root(include_moonraker_cache=True, include_fluidd_bundle=True, include_moonraker_asvc=True)
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(root)
        boot_id = printer_root / "boot-id"
        boot_id.write_text("boot-one\n", encoding="utf-8")
        env["TLTG_OPTIMIZED_BOOT_ID_PATH"] = str(boot_id)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        fluidd = root / manifest.system_optimizations.fluidd_box_filament_ids.file.lstrip("/")
        fluidd.write_text(fluidd.read_text().replace('"officiallFilasList",e)', '"officiallFilasList",e||{})'))
        original = fluidd.read_bytes()
        asvc = root / moonraker_allowed_services.FILE.lstrip("/")
        asvc.write_text("[allowed]\nklipper_mcu\n", encoding="utf-8")
        operator_dropin = root / restart_on_exit.FILES[restart_on_exit.KLIPPER_OPERATION].lstrip("/")
        operator_dropin.parent.mkdir(parents=True)
        operator_dropin.write_text("[Service]\nRemainAfterExit=yes\n", encoding="utf-8")

        ledger = apply_system_optimizations(
            paths=paths, spec=manifest.system_optimizations,
            ledger={"policy": {"system_optimizations": "disabled", "ai_detection": "unset"}},
            reporter=PlainReporter(io.StringIO()), input_stream=None,
            environ=env, source="yes_install", run=fake_host_run(root),
            urlopen=moonraker_urlopen(),
        )

        self.assertEqual(fluidd.read_bytes(), original)
        self.assertEqual(ledger["outcomes"][FLUIDD_BOX_OPERATION]["status"], "unsupported")
        self.assertNotIn(FLUIDD_BOX_OPERATION, ledger["restore_preimages"])
        self.assertEqual(asvc.read_text(encoding="utf-8"), "[allowed]\nklipper_mcu\n")
        self.assertEqual(ledger["outcomes"][moonraker_allowed_services.OPERATION]["status"], "unsupported")
        self.assertEqual(operator_dropin.read_text(encoding="utf-8"), "[Service]\nRemainAfterExit=yes\n")
        self.assertEqual(ledger["outcomes"][restart_on_exit.KLIPPER_OPERATION]["status"], "unsupported")
        self.assertIn(restart_on_exit.MOONRAKER_OPERATION, ledger["restore_preimages"])
        self.assertIn(system_optimizations.MOONRAKER_CACHE_OPERATION, ledger["restore_preimages"])

        # Zram swap that fails to start, such as modules the kernel rejects, leaves nothing behind,
        # including the root remount that ran before it.
        host_run = fake_host_run(root)

        def zram_fails(command, **kwargs):
            if list(command)[-3:] == ["systemctl", "restart", zram_swap.UNIT]:
                return CompletedProcess(command, 1, stdout="", stderr="insmod failed")
            return host_run(command, **kwargs)

        with self.assertRaises(SystemOptimizationApplyError):
            apply_system_optimizations(
                paths=paths, spec=manifest.system_optimizations,
                ledger={**ledger, "policy": {"system_optimizations": "enabled", "ai_detection": "keep_enabled"}},
                reporter=PlainReporter(io.StringIO()), input_stream=None,
                environ=env, source="yes_install", run=zram_fails,
                urlopen=moonraker_urlopen(),
            )
        self.assertFalse((root / zram_swap.DESTINATION.lstrip("/")).exists())
        self.assertFalse((root / zram_swap.UNIT_FILE.lstrip("/")).exists())
        self.assertEqual(json.loads((root / "systemd" / f"{zram_swap.UNIT}.json").read_text(encoding="utf-8"))["enabled"], "disabled")
        self.assertEqual((root / "mounts/root.options").read_text(encoding="utf-8"), "rw,relatime,sync\n")
        self.assertFalse((root / manifest.system_optimizations.rockchip_root_sync.dropin.lstrip("/")).exists())
        self.assertFalse(paths.host_reboot_marker_path.exists())
        self.assertFalse(_journal_path(paths).exists())

    def test_moonraker_cache_admission_and_restart_failure_preserve_source(self):
        for fault in ("unknown", "unknown_metascan", "symlink", "restart", "concurrent"):
            with self.subTest(fault=fault):
                printer_root = copy_base_runtime()
                root = fake_system_root(include_moonraker_cache=True)
                env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
                env[SYSTEM_ROOT_ENV] = str(root)
                paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
                manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
                target = root / manifest.system_optimizations.moonraker_file_manager.file.lstrip("/")
                if fault == "unknown":
                    target.write_text(target.read_text().replace("retries = 3", "retries = 4"))
                elif fault == "unknown_metascan":
                    target.write_text(target.read_text().replace("get_str('filename')", "get_str('filename', '')"))
                original = target.read_bytes()
                if fault == "symlink":
                    other = target.with_name("operator.py")
                    target.rename(other)
                    target.symlink_to(other)
                host_run = fake_host_run(root)
                failed = False

                def run(command, **kwargs):
                    nonlocal failed
                    if not failed and list(command)[-3:] == ["systemctl", "restart", "moonraker.service"]:
                        if fault == "restart":
                            failed = True
                            return CompletedProcess(command, 1, stdout="", stderr="restart failed")
                        if fault == "concurrent":
                            failed = True
                            target.write_bytes(target.read_bytes() + b"\n# concurrent operator edit\n")
                            return CompletedProcess(command, 1, stdout="", stderr="restart failed")
                    return host_run(command, **kwargs)

                expected_error = SystemOptimizationRecoveryError if fault == "concurrent" else SystemOptimizationApplyError
                with self.assertRaises(expected_error):
                    apply_system_optimizations(
                        paths=paths, spec=manifest.system_optimizations,
                        ledger={"policy": {"system_optimizations": "disabled", "ai_detection": "unset"}},
                        reporter=PlainReporter(io.StringIO()), input_stream=None,
                        environ=env, source="yes_install", run=run,
                        urlopen=moonraker_urlopen(),
                    )
                if fault == "concurrent":
                    drifted = target.read_bytes()
                    self.assertTrue(drifted.endswith(b"# concurrent operator edit\n"))
                    self.assertTrue(_journal_path(paths).exists())
                    with self.assertRaises(SystemOptimizationRecoveryError):
                        recover_pending_system_optimization(
                            paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()),
                            input_stream=None, environ=env, run=host_run,
                            urlopen=moonraker_urlopen(),
                        )
                    self.assertEqual(target.read_bytes(), drifted)
                else:
                    self.assertEqual(target.read_bytes(), original)
                    self.assertFalse(_journal_path(paths).exists())
                self.assertEqual(target.is_symlink(), fault == "symlink")

    def test_forged_host_preimages_fail_closed_before_uninstall(self):
        printer_root = copy_base_runtime()
        system_root = fake_system_root()
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        forged = {
            "schema_version": 2,
            "policy": {"system_optimizations": "enabled", "ai_detection": "unset"},
            "restore_preimages": {
                "apt_sources": {
                    "file": {
                        "path": "/etc/shadow",
                        "exists": True,
                        "type": "file",
                        "backup_path": "/tmp/shadow",
                        "sha256": "0" * 64,
                        "mode": "0600",
                        "uid": 0,
                        "gid": 0,
                    }
                }
            },
            "outcomes": {"apt_sources": {"status": "applied"}},
            "committed_transactions": {},
        }
        with self.assertRaisesRegex(Exception, "Host file restoration preimage is invalid"):
            validate_system_ledger(forged, manifest=manifest, paths=paths)
        journal = {"schema_version": 1, "operation": "apt_sources", "transaction_id": "x", "phase": "apply", "preimage": forged["restore_preimages"]["apt_sources"]}
        _journal_path(paths).write_text(json.dumps(journal), encoding="utf-8")
        with self.assertRaises(SystemOptimizationRecoveryError):
            recover_pending_system_optimization(
                paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()),
                input_stream=io.StringIO(), environ=env, run=fake_host_run(system_root),
                urlopen=moonraker_urlopen(),
            )
        self.assertTrue(_journal_path(paths).exists())

    def test_host_ledger_migration_and_rockchip_journal_recovery(self):
        printer_root = copy_base_runtime()
        system_root = fake_system_root()
        host_run = fake_host_run(system_root)
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(system_root)
        boot = printer_root / "boot-id"
        boot.write_text("test-boot\n")
        env["TLTG_OPTIMIZED_BOOT_ID_PATH"] = str(boot)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        legacy = {
            "policy": {"system_optimizations": "enabled", "ai_detection": "unset"},
            "actions": [{"id": "rockchip_root_sync", "status": "applied", "transaction_id": "committed", "desired": {}}],
            "restore_preimages": {},
        }
        compacted = _compact_host_ledger(legacy)
        self.assertEqual(compacted["schema_version"], 2)
        self.assertEqual(compacted["committed_transactions"]["rockchip_root_sync"], "committed")
        self.assertNotIn("actions", compacted)

        rockchip = manifest.system_optimizations.rockchip_root_sync
        journal = {
            "schema_version": 1,
            "operation": "rockchip_root_sync",
            "transaction_id": "committed",
            "started_at": "2026-01-01T00:00:00Z",
            "phase": "captured",
            "preimage": {
                "classification": "defective_stock",
                "dropin": {"path": rockchip.dropin, "exists": False},
                "desired_dropin": rockchip.dropin_content,
                "unit": {},
                "mount_options": ["rw", "sync"],
                "marker": {"exists": False},
            },
        }
        _journal_path(paths).write_text(json.dumps(journal), encoding="utf-8")
        self.assertTrue(
            recover_pending_system_optimization(
                paths=paths,
                manifest=manifest,
                reporter=PlainReporter(io.StringIO()),
                input_stream=io.StringIO(),
                environ=env,
                run=host_run,
                urlopen=moonraker_urlopen(),
            )
        )
        self.assertFalse(_journal_path(paths).exists())

        # The remount runs before the other operations, and a crash before the installed state commits it still
        # rolls it back.
        mount_before = (system_root / "mounts/root.options").read_text(encoding="utf-8")
        apply_system_optimizations(
            paths=paths, spec=manifest.system_optimizations,
            ledger={"policy": {"system_optimizations": "enabled", "ai_detection": "keep_enabled"}},
            reporter=PlainReporter(io.StringIO()), input_stream=None,
            environ=env, source="yes_install", run=host_run,
            urlopen=moonraker_urlopen(),
        )
        self.assertNotIn("sync", (system_root / "mounts/root.options").read_text(encoding="utf-8").strip().split(","))
        self.assertTrue(
            recover_pending_system_optimization(
                paths=paths,
                manifest=manifest,
                reporter=PlainReporter(io.StringIO()),
                input_stream=io.StringIO(),
                environ=env,
                run=host_run,
                urlopen=moonraker_urlopen(),
            )
        )
        self.assertEqual((system_root / "mounts/root.options").read_text(encoding="utf-8"), mount_before)
        self.assertFalse((system_root / rockchip.dropin.lstrip("/")).exists())
        self.assertFalse(_journal_path(paths).exists())

    def test_uninstall_preserves_user_modified_host_state(self):
        printer_root = copy_base_runtime()
        system_root = fake_system_root(include_moonraker_cache=True, include_filament_config=True)
        host_run = fake_host_run(system_root)
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(system_root)
        boot = printer_root / "boot-id"
        boot.write_text("test-boot\n")
        env["TLTG_OPTIMIZED_BOOT_ID_PATH"] = str(boot)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        compatibility = load_supported_upgrade_sources(REPO_ROOT / "installer/supported_upgrade_sources.yaml")
        run_install(
            paths, manifest, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nno\n"),
            urlopen=moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg"), environ=env,
            run=host_run,
        )
        (system_root / "etc/apt/sources.list").write_text("operator apt\n", encoding="utf-8")
        moonraker = system_root / manifest.system_optimizations.moonraker_file_manager.file.lstrip("/")
        drifted = moonraker.read_bytes() + b"\n# operator modification outside the patched class\n"
        moonraker.write_bytes(drifted)
        filament_link = printer_root / manifest.system_optimizations.fluidd_filament_config.link
        filament_link.unlink()
        filament_link.symlink_to("/home/qidi/operator_filaments")
        state = load_installed_state(printer_root / manifest.state_file)
        cache_policy = {**state.system_ledger, "policy": {"system_optimizations": "disabled", "ai_detection": "unset"}}
        reconciled = apply_system_optimizations(
            paths=paths, spec=manifest.system_optimizations, ledger=cache_policy,
            reporter=PlainReporter(io.StringIO()), input_stream=None, environ=env,
            source="auto_update_reconcile", run=host_run,
            urlopen=moonraker_urlopen(),
        )
        self.assertEqual(moonraker.read_bytes(), drifted)
        self.assertEqual(os.readlink(filament_link), "/home/qidi/operator_filaments")
        write_installed_state(printer_root / manifest.state_file, _replace_system_ledger(state, reconciled))
        (system_root / "etc/apt/sources.list").write_text("operator apt\n", encoding="utf-8")
        probe_helper = paths.managed_klipper_root / "klippy/extras/tltg_probe_test.py"
        probe_modified = probe_helper.read_bytes() + b"\n# operator modification\n"
        probe_helper.write_bytes(probe_modified)
        zram = system_root / zram_swap.DESTINATION.lstrip("/")
        (zram / zram_swap.MARKER).unlink()
        report = io.StringIO()
        run_uninstall(
            paths, manifest, compatibility, PlainReporter(report), input_stream=io.StringIO("yes\nyes\nno\n"),
            urlopen=moonraker_urlopen(), environ=env,
            run=host_run,
        )
        self.assertEqual((system_root / "etc/apt/sources.list").read_text(encoding="utf-8"), "operator apt\n")
        self.assertEqual(moonraker.read_bytes(), drifted)
        self.assertEqual(os.readlink(filament_link), "/home/qidi/operator_filaments")
        self.assertEqual(probe_helper.read_bytes(), probe_modified)
        self.assertTrue(zram.is_dir())
        self.assertFalse((system_root / zram_swap.UNIT_FILE.lstrip("/")).exists())

    def test_legacy_host_preimages_migrate_and_restore(self):
        printer_root = copy_base_runtime()
        system_root = fake_system_root()
        host_run = fake_host_run(system_root)
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(system_root)
        boot = printer_root / "boot-id"
        boot.write_text("test-boot\n", encoding="utf-8")
        env["TLTG_OPTIMIZED_BOOT_ID_PATH"] = str(boot)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        compatibility = load_supported_upgrade_sources(REPO_ROOT / "installer/supported_upgrade_sources.yaml")
        run_install(paths, manifest, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nno\nno\n"), urlopen=moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg"), environ=env, run=host_run)
        state_path = printer_root / manifest.state_file
        state = load_installed_state(state_path)
        legacy = copy.deepcopy(state.system_ledger)
        for preimage in legacy["restore_preimages"].values():
            self._make_legacy_preimage(preimage, system_root)
        legacy.pop("schema_version")
        legacy["actions"] = [
            {"id": operation_id, "status": "applied", "transaction_id": outcome.get("transaction_id"), "desired": outcome.get("desired", {})}
            for operation_id, outcome in legacy.pop("outcomes").items()
        ]
        legacy.pop("committed_transactions")
        write_installed_state(state_path, _replace_system_ledger(state, legacy))
        run_install(paths, manifest, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nno\nno\n"), urlopen=moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg"), environ=env, run=host_run)
        migrated = load_installed_state(state_path).system_ledger
        self.assertEqual(migrated["restore_preimages"]["apt_sources"]["file"]["sha256"], __import__("hashlib").sha256(b"old apt\n").hexdigest())
        migrated_gifs = Path(migrated["restore_preimages"]["qidiclient_static_gifs"]["backup_dir"])
        self.assertTrue(migrated_gifs.is_relative_to(paths.printer_data_root / system_optimizations.SYSTEM_BACKUP_DIR))
        # Simulate power loss after atomic state commit but before migration-journal cleanup.
        migration_target = migrated_gifs.parent
        migration_id = migration_target.name.removeprefix(system_optimizations.LEGACY_MIGRATION_PREFIX)
        (migration_target / system_optimizations.LEGACY_MIGRATION_OWNER).write_text(
            json.dumps({"kind": "legacy-system-ledger-gifs", "migration_id": migration_id}), encoding="utf-8"
        )
        (paths.printer_data_root / system_optimizations.LEGACY_MIGRATION_JOURNAL).write_text(
            json.dumps({"schema_version": 1, "kind": "legacy-system-ledger-gifs", "migration_id": migration_id, "target": str(migration_target)}), encoding="utf-8"
        )
        system_optimizations.recover_pending_legacy_system_ledger_migration(paths, state_path)
        self.assertTrue(migrated_gifs.is_dir())
        run_uninstall(paths, manifest, compatibility, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nyes\nno\n"), urlopen=moonraker_urlopen(), environ=env, run=host_run)
        self.assertEqual((system_root / "etc/apt/sources.list").read_text(encoding="utf-8"), "old apt\n")
        self.assertEqual((system_root / "home/qidi/QIDI_Client/access/account/process.gif").read_bytes(), b"old")
        self.assertFalse((system_root / zram_swap.DESTINATION.lstrip("/")).exists())

    def test_legacy_migration_has_no_writes_before_preflight_dry_run_or_failed_plan(self):
        paths, manifest, env, root = self._legacy_host_context()
        state_path = paths.printer_data_root / manifest.state_file
        before_state = state_path.read_bytes()
        backup_root = paths.printer_data_root / system_optimizations.SYSTEM_BACKUP_DIR
        before = snapshot_tree(backup_root)
        with self.assertRaisesRegex(RuntimeError, "preflight stop"):
            run_install(
                paths,
                manifest,
                PlainReporter(io.StringIO()),
                dry_run=True,
                urlopen=moonraker_urlopen(),
                disk_usage=lambda _: (_ for _ in ()).throw(RuntimeError("preflight stop")),
                environ=env,
                run=fake_host_run(root),
            )
        self.assertEqual(snapshot_tree(backup_root), before)
        with mock.patch("installer.runtime.runner.build_install_plan", side_effect=RuntimeError("invalid plan")):
            with self.assertRaisesRegex(RuntimeError, "invalid plan"):
                run_install(paths, manifest, PlainReporter(io.StringIO()), urlopen=moonraker_urlopen(), environ=env, run=fake_host_run(root))
        self.assertEqual(state_path.read_bytes(), before_state)
        self.assertEqual(snapshot_tree(backup_root), before)
        self._assert_legacy_migration_interruption_recovers_unreferenced_copy(paths, manifest, env, state_path)

    def _assert_legacy_migration_interruption_recovers_unreferenced_copy(self, paths, manifest, env, state_path):
        before_state = state_path.read_bytes()
        migrated_paths = []
        system_optimizations.migrate_legacy_system_ledger(
            load_installed_state(state_path).system_ledger,
            manifest=manifest,
            paths=paths,
            environ=env,
            created_paths=migrated_paths,
        )
        self.assertEqual(len(migrated_paths), 1)
        self.assertTrue(migrated_paths[0].exists())
        self.assertTrue((paths.printer_data_root / system_optimizations.LEGACY_MIGRATION_JOURNAL).exists())
        system_optimizations.recover_pending_legacy_system_ledger_migration(paths, state_path)
        self.assertFalse(migrated_paths[0].exists())
        self.assertFalse((paths.printer_data_root / system_optimizations.LEGACY_MIGRATION_JOURNAL).exists())
        self.assertEqual(state_path.read_bytes(), before_state)

    def test_legacy_migration_cleanup_requires_owned_dedicated_target(self):
        invalid_cases = (
            ("backup-root", lambda backup_root, unrelated: {"schema_version": 1, "kind": "legacy-system-ledger-gifs", "migration_id": "a" * 32, "target": str(backup_root)}),
            ("unrelated-subtree", lambda backup_root, unrelated: {"schema_version": 1, "kind": "legacy-system-ledger-gifs", "migration_id": "b" * 32, "target": str(unrelated)}),
            ("malformed-schema", lambda backup_root, unrelated: {"schema_version": 999, "kind": "legacy-system-ledger-gifs", "migration_id": "c" * 32, "target": str(unrelated)}),
            ("missing-identity", lambda backup_root, unrelated: {"schema_version": 1, "target": str(unrelated)}),
        )
        paths, _, _, _ = self._host_context()
        backup_root = paths.printer_data_root / system_optimizations.SYSTEM_BACKUP_DIR
        unrelated = backup_root / "retained-preimage"
        unrelated.mkdir(parents=True)
        retained = unrelated / "retained.bin"
        retained.write_bytes(b"retain")
        journal = paths.printer_data_root / system_optimizations.LEGACY_MIGRATION_JOURNAL
        for name, payload_for in invalid_cases:
            with self.subTest(name=name):
                journal.write_text(json.dumps(payload_for(backup_root, unrelated)), encoding="utf-8")
                with self.assertRaises(StateValidationError):
                    system_optimizations.recover_pending_legacy_system_ledger_migration(
                        paths, paths.printer_data_root / "absent-state.yaml"
                    )
                self.assertEqual(retained.read_bytes(), b"retain")

        link = backup_root / ".ledger-migration-link"
        link.symlink_to(unrelated, target_is_directory=True)
        journal = paths.printer_data_root / system_optimizations.LEGACY_MIGRATION_JOURNAL
        journal.write_text(json.dumps({"schema_version": 1, "kind": "legacy-system-ledger-gifs", "migration_id": "a" * 32, "target": str(link)}), encoding="utf-8")
        with self.assertRaises(StateValidationError):
            system_optimizations.recover_pending_legacy_system_ledger_migration(
                paths, paths.printer_data_root / "absent-state.yaml"
            )
        self.assertEqual(retained.read_bytes(), b"retain")

        paths, _, _, _ = self._host_context()
        backup_root = paths.printer_data_root / system_optimizations.SYSTEM_BACKUP_DIR
        collision = backup_root / f"{system_optimizations.LEGACY_MIGRATION_PREFIX}{'c' * 32}"
        collision.mkdir(parents=True)
        retained = collision / "retained.bin"
        retained.write_bytes(b"retain")
        old = paths.printer_data_root / "old-gifs"
        (old / "account").mkdir(parents=True)
        (old / "account/process.gif").write_bytes(b"old")
        preimage = {
            "backup_dir": str(old),
            "replaced": ["account/process.gif"],
            "files": {"account/process.gif": {"sha256": __import__("hashlib").sha256(b"old").hexdigest()}},
        }
        migration_id = mock.Mock(hex="c" * 32)
        with mock.patch.object(system_optimizations.uuid, "uuid4", return_value=migration_id):
            with self.assertRaises(FileExistsError):
                system_optimizations._materialize_legacy_gif_preimage(preimage, paths=paths)
        self.assertEqual(retained.read_bytes(), b"retain")

    def test_forged_ledger_uninstall_has_no_backup_or_host_side_effect(self):
        paths, manifest, env, root = self._installed_host_context()
        state_path = paths.printer_data_root / manifest.state_file
        state = load_installed_state(state_path)
        forged = {
            "schema_version": 2,
            "policy": {"system_optimizations": "enabled", "ai_detection": "unset"},
            "restore_preimages": {"apt_sources": {"file": {"path": "/etc/shadow", "exists": True, "type": "file", "backup_path": "/tmp/shadow", "sha256": "0" * 64, "mode": "0600", "uid": 0, "gid": 0}}},
            "outcomes": {"apt_sources": {"status": "applied"}},
            "committed_transactions": {},
        }
        write_installed_state(state_path, _replace_system_ledger(state, forged))
        before = snapshot_tree(root)
        compatibility = load_supported_upgrade_sources(REPO_ROOT / "installer/supported_upgrade_sources.yaml")
        with mock.patch("installer.runtime.uninstall.create_config_backup") as backup, mock.patch("installer.runtime.uninstall.prune_installer_backups") as prune:
            with self.assertRaises(InstalledPackageValidationError):
                run_uninstall(paths, manifest, compatibility, PlainReporter(io.StringIO()), input_stream=io.StringIO(), urlopen=moonraker_urlopen(), environ=env, run=fake_host_run(root))
        backup.assert_not_called(); prune.assert_not_called()
        self.assertEqual(snapshot_tree(root), before)

    def test_forged_legacy_rockchip_journal_never_clears(self):
        legacy = {"policy": {"system_optimizations": "enabled", "ai_detection": "unset"}, "restore_preimages": {}, "outcomes": {}, "committed_transactions": {}, "actions": [{"id": "rockchip_root_sync", "status": "applied", "transaction_id": "same"}]}
        # Recovery loads only an on-disk installed state; use a valid install then replace its ledger.
        paths, manifest, env, root = self._installed_host_context()
        state_path = paths.printer_data_root / manifest.state_file
        write_installed_state(state_path, _replace_system_ledger(load_installed_state(state_path), legacy))
        journal = {"schema_version": 1, "operation": "rockchip_root_sync", "transaction_id": "same", "phase": "captured", "preimage": {"classification": "defective_stock", "dropin": {"path": "/etc/shadow", "exists": False}, "desired_dropin": manifest.system_optimizations.rockchip_root_sync.dropin_content, "unit": {}, "mount_options": ["rw", "sync"], "marker": {"exists": False}}}
        _journal_path(paths).write_text(json.dumps(journal), encoding="utf-8")
        with self.assertRaises(SystemOptimizationRecoveryError):
            recover_pending_system_optimization(paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()), input_stream=io.StringIO(), environ=env, run=fake_host_run(root), urlopen=moonraker_urlopen())
        self.assertTrue(_journal_path(paths).exists())

    def test_rockchip_restores_full_admitted_mount_preimage(self):
        paths, manifest, env, root = self._host_context()
        (root / "mounts/root.options").write_text("ro,noatime,sync\n", encoding="utf-8")
        # A kernel other than the build the zram modules were made for, such as one from a QIDI update, runs without them.
        (root / "proc/sys/kernel/version").write_text("#5 SMP PREEMPT Mon Jan 5 10:00:00 CST 2026\n", encoding="utf-8")
        run_install(paths, manifest, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nno\nno\n"), urlopen=moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg"), environ=env, run=fake_host_run(root))
        outcomes = load_installed_state(paths.printer_data_root / manifest.state_file).system_ledger["outcomes"]
        self.assertEqual(outcomes[zram_swap.OPERATION]["status"], "unsupported")
        self.assertEqual(outcomes[zram_swap.UNIT_OPERATION]["status"], "skipped")
        self.assertFalse((root / zram_swap.DESTINATION.lstrip("/")).exists())
        self.assertFalse((root / zram_swap.UNIT_FILE.lstrip("/")).exists())
        self.assertEqual((root / cpu_governor.FILE.lstrip("/")).read_text(encoding="utf-8"), cpu_governor.CONTENT)
        # An update that finds the repair already in place still lets uninstall put the mount back, including after
        # an earlier version recorded that outcome without the mount options.
        state_path = paths.printer_data_root / manifest.state_file
        state = load_installed_state(state_path)
        state.system_ledger["outcomes"]["rockchip_root_sync"] = {"status": "already_current_owned", "source": "yes_install", "postflight": {"classification": "already_current_owned"}}
        write_installed_state(state_path, state)
        run_install(paths, manifest, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nno\nno\n"), urlopen=moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg"), environ=env, run=fake_host_run(root))
        compatibility = load_supported_upgrade_sources(REPO_ROOT / "installer/supported_upgrade_sources.yaml")
        report = io.StringIO()
        run_uninstall(paths, manifest, compatibility, PlainReporter(report), input_stream=io.StringIO("yes\nyes\n"), urlopen=moonraker_urlopen(), environ=env, run=fake_host_run(root))
        self.assertNotIn("Rockchip system state was modified", report.getvalue())
        self.assertEqual((root / "mounts/root.options").read_text(encoding="utf-8"), "ro,noatime,sync\n")
        # Accepted restoration puts back QIDI's ondemand governor.
        self.assertFalse((root / cpu_governor.FILE.lstrip("/")).exists())

    def test_compensation_journal_blocks_until_all_services_recover(self):
        paths, manifest, env, root = self._host_context()
        calls = {"fail_apply": True, "fail_restore": True}
        base_run = fake_host_run(root)
        def run(command, **kwargs):
            actual = command[4:] if command[:4] == ["sudo", "-S", "-p", ""] else command
            if actual == ["systemctl", "disable", "--now", "bluetooth"] and calls["fail_apply"]:
                return CompletedProcess(command, 1, stdout="failed")
            if actual in (["systemctl", "enable", "xl2tpd"], ["systemctl", "start", "xl2tpd"], ["systemctl", "enable", "--now", "xl2tpd"]) and calls["fail_restore"]:
                return CompletedProcess(command, 1, stdout="failed")
            return base_run(command, **kwargs)
        ledger = {"policy": {"system_optimizations": "enabled", "ai_detection": "keep_enabled"}, "restore_preimages": {}, "actions": []}
        selected = ("service_xl2tpd", "service_bluetooth")
        with mock.patch.object(system_optimizations, "_selected_operation_ids", return_value=selected):
            with self.assertRaises(SystemOptimizationRecoveryError) as failed:
                apply_system_optimizations(paths=paths, spec=manifest.system_optimizations, ledger=ledger, reporter=PlainReporter(io.StringIO()), input_stream=io.StringIO(), environ=env, source="test", run=run, urlopen=moonraker_urlopen())
        # The failure that started the rollback stays visible beside the rollback's own failure.
        self.assertIn(messages.SYSTEM_OPTIMIZATIONS_FAILED, failed.exception.message)
        self.assertIn(messages.SYSTEM_RESTORE_FAILED, failed.exception.message)
        payload = json.loads(_journal_path(paths).read_text(encoding="utf-8"))
        self.assertIn("service_xl2tpd", payload["preimages"])
        self.assertIn("service_bluetooth", payload["preimages"])
        calls["fail_apply"] = False
        with self.assertRaises(SystemOptimizationRecoveryError) as pending:
            recover_pending_system_optimization(paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()), input_stream=io.StringIO(), environ=env, run=run, urlopen=moonraker_urlopen())
        self.assertIn(messages.SYSTEM_OPTIMIZATIONS_FAILED, pending.exception.message)
        self.assertTrue(_journal_path(paths).exists())
        with self.assertRaises(SystemOptimizationRecoveryError):
            apply_system_optimizations(paths=paths, spec=manifest.system_optimizations, ledger=ledger, reporter=PlainReporter(io.StringIO()), input_stream=io.StringIO(), environ=env, source="next-lifecycle", run=run, urlopen=moonraker_urlopen())
        calls["fail_restore"] = False
        output = io.StringIO()
        self.assertTrue(recover_pending_system_optimization(paths=paths, manifest=manifest, reporter=PlainReporter(output), input_stream=io.StringIO(), environ=env, run=run, urlopen=moonraker_urlopen()))
        self.assertIn(messages.SYSTEM_OPTIMIZATIONS_FAILED, output.getvalue())
        self.assertFalse(_journal_path(paths).exists())

    def test_rockchip_drift_journal_never_replays_after_interrupt(self):
        paths, manifest, env, root = self._installed_host_context()
        state = load_installed_state(paths.printer_data_root / manifest.state_file)
        mount_options = root / "mounts/root.options"
        mount_options.write_text("ro,noatime,async\n", encoding="utf-8")
        reporter = PlainReporter(io.StringIO())
        original_line = reporter.line
        def interrupt_after_preserve(message):
            original_line(message)
            if message == "Rockchip system state was modified after install and was preserved.":
                raise KeyboardInterrupt
        with mock.patch.object(reporter, "line", side_effect=interrupt_after_preserve):
            with self.assertRaises(KeyboardInterrupt):
                system_optimizations.restore_system_optimizations(paths=paths, manifest=manifest, state=state, reporter=reporter, input_stream=io.StringIO(), environ=env, include_optional=True, run=fake_host_run(root), urlopen=moonraker_urlopen())
        self.assertEqual(mount_options.read_text(encoding="utf-8"), "ro,noatime,async\n")
        recover_pending_system_optimization(paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()), input_stream=io.StringIO(), environ=env, run=fake_host_run(root), urlopen=moonraker_urlopen())
        self.assertEqual(mount_options.read_text(encoding="utf-8"), "ro,noatime,async\n")

    def test_unsafe_or_incomplete_mount_preimage_fails_before_host_mutation(self):
        paths, manifest, env, root = self._installed_host_context()
        state = load_installed_state(paths.printer_data_root / manifest.state_file)
        original = list(state.system_ledger["restore_preimages"]["rockchip_root_sync"]["mount_options"])
        before = snapshot_tree(root)
        for mount_preimage in (["rw", "bind"], ["sync"]):
            with self.subTest(mount_preimage=mount_preimage):
                state.system_ledger["restore_preimages"]["rockchip_root_sync"]["mount_options"] = mount_preimage
                with self.assertRaisesRegex(Exception, "Rockchip restoration preimage is invalid"):
                    system_optimizations.restore_system_optimizations(
                        paths=paths,
                        manifest=manifest,
                        state=state,
                        reporter=PlainReporter(io.StringIO()),
                        input_stream=io.StringIO(),
                        environ=env,
                        include_optional=True,
                        run=fake_host_run(root),
                        urlopen=moonraker_urlopen(),
                    )
                self.assertFalse(_journal_path(paths).exists())
                self.assertEqual(snapshot_tree(root), before)
        state.system_ledger["restore_preimages"]["rockchip_root_sync"]["mount_options"] = original

    def _legacy_host_context(self):
        paths, manifest, env, root = self._installed_host_context()
        state_path = paths.printer_data_root / manifest.state_file
        state = load_installed_state(state_path)
        legacy = copy.deepcopy(state.system_ledger)
        for preimage in legacy["restore_preimages"].values():
            self._make_legacy_preimage(preimage, root)
        legacy.pop("schema_version")
        legacy["actions"] = [
            {"id": operation_id, "status": "applied", "transaction_id": outcome.get("transaction_id"), "desired": outcome.get("desired", {})}
            for operation_id, outcome in legacy.pop("outcomes").items()
        ]
        legacy.pop("committed_transactions")
        write_installed_state(state_path, _replace_system_ledger(state, legacy))
        return paths, manifest, env, root

    def _host_context(self):
        printer_root = copy_base_runtime(); root = fake_system_root()
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid"); env[SYSTEM_ROOT_ENV] = str(root)
        boot = printer_root / "boot-id"
        boot.write_text("test-boot\n", encoding="utf-8")
        env["TLTG_OPTIMIZED_BOOT_ID_PATH"] = str(boot)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        return paths, load_manifest(REPO_ROOT / "installer/package.yaml"), env, root

    def _installed_host_context(self):
        paths, manifest, env, root = self._host_context()
        run_install(paths, manifest, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nno\nno\n"), urlopen=moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg"), environ=env, run=fake_host_run(root))
        return paths, manifest, env, root

    def _make_legacy_preimage(self, preimage, root):
        if not isinstance(preimage, dict): return
        if "sha256" in preimage:
            preimage.pop("sha256")
        if "backup_path" in preimage:
            return
        if "files" in preimage:
            for item in preimage["files"]: self._make_legacy_preimage(item, root)
        if "file" in preimage: self._make_legacy_preimage(preimage["file"], root)
        if preimage.get("destination"):
            source = Path(preimage["backup_dir"])
            destination = root / preimage["destination"].lstrip("/") / ".gif-backup-old"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination)
            preimage["backup_dir"] = str(destination)
            for metadata in preimage.get("files", {}).values(): metadata.pop("sha256", None)
