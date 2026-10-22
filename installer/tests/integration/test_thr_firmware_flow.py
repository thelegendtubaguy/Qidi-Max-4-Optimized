from __future__ import annotations

import hashlib
import io
import itertools
import json
import shutil
import subprocess
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from installer.runtime import thr_firmware
from installer.runtime.auto_update import LOCK_HELD_ENV
from installer.runtime.cli import main, parse_args, resolve_runtime_paths
from installer.runtime.reporter import create_reporter
from installer.runtime.safety import THR_RECOVERY_MARKER, ensure_no_recovery_sentinel
from installer.runtime.errors import InstallerError
from installer.runtime.models import InstallResult
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, temp_path
from scripts import flash_thr_firmware as protocol
from scripts.build_thr_firmware import patch_thr


class Printer:
    def __init__(self, root, manifest, stock, boot, *, patched=False, failure=None, timer=True):
        self.root, self.manifest = root, manifest
        self.stock, self.boot = stock, boot
        self.image = patch_thr(stock, manifest) if patched else stock
        self.failure = failure
        self.states = {s: 'active' for s in protocol.SERVICES}
        self.states['qidi-client.service'] = 'inactive'
        if not timer:
            del self.states['tltg-optimized-auto-update.timer']
        self.original = dict(self.states)
        self.transfers = 0
        self.snapshots = 0
        self.state = 'standby'
        self.idle_state = 'Ready'
        self.restarting_queries = 0
        self.targets = {'extruder': 0, 'heater_bed': 0, 'heater_generic chamber': 0, 'heater_generic extra': 0}

    def urlopen(self, *args, **kwargs):
        if self.restarting_queries:
            self.restarting_queries -= 1
            raise OSError('Klippy not connected')
        status = {'print_stats': {'state': self.state}, 'webhooks': {'state': 'ready'},
                  'idle_timeout': {'state': self.idle_state}, 'heaters': {'available_heaters': list(self.targets)}}
        status.update({name: {'target': value} for name, value in self.targets.items()})
        return io.BytesIO(json.dumps({'result': {'status': status}}).encode())

    def run(self, command, **kwargs):
        command = list(command)
        def result(code=0, output=''):
            return subprocess.CompletedProcess(command, code, stdout=output, stderr='')
        if command[:4] == ['sudo', '-S', '-p', '']:
            command = command[4:]
        if command == ['-v']:
            return result()
        if command[:2] == ['systemctl', 'show']:
            service = command[2]
            if service not in self.states:
                return result(1, 'LoadState=not-found\nActiveState=inactive\n')
            return result(output='LoadState=loaded\nActiveState=' + self.states[service] + '\n')
        if command[:1] == ['systemctl'] and command[1] in ('stop', 'start'):
            if self.failure == 'restore' and command[1] == 'start':
                return result(1)
            self.states[command[2]] = 'inactive' if command[1] == 'stop' else 'active'
            return result()
        if command[1].endswith('/scripts/flash_thr_firmware.py'):
            operation = command[2]
            if operation == 'snapshot':
                self.snapshots += 1
                destination = Path(command[command.index('--output-dir') + 1])
                destination.mkdir()
                image, boot = self.image, self.boot
                if self.failure == 'unknown-app' and self.snapshots == 1:
                    image = image[:-1] + bytes([image[-1] ^ 1])
                if self.failure == 'unknown-boot' and self.snapshots == 1:
                    boot = boot[:-1] + bytes([boot[-1] ^ 1])
                if self.failure == 'readback' and self.snapshots == 2:
                    image = self.stock
                supported = protocol.digest(boot) in protocol.thr_bootloaders.ADMITTED_BOOTLOADERS
                region = image + b'\xff' * (0x18000 - len(image)) if not supported else None
                protocol.save_snapshot(destination, boot, image, application_region=region)
                return result(0 if supported else protocol.UNSUPPORTED_BOOTLOADER)
            if operation == 'transfer':
                self.transfers += 1
                if self.failure == 'interrupt':
                    raise KeyboardInterrupt()
                if self.failure == 'transfer':
                    return result(1)
                self.image = Path(command[command.index('--image') + 1]).read_bytes()
                return result()
        raise AssertionError('Unexpected external operation: ' + str(command))


class ThrFirmwareFlowTests(unittest.TestCase):
    def fixture(self, *, profile=protocol.thr_bootloaders.FIRST, **kwargs):
        root = temp_path('thr-firmware-flow-')
        bundle = root / 'bundle'
        (bundle / 'scripts').mkdir(parents=True)
        (bundle / 'firmware').mkdir()
        for name in ('flash_thr_firmware.py', 'thr_bootloaders.py', 'build_thr_firmware.py'):
            shutil.copy2(REPO_ROOT / 'scripts' / name, bundle / 'scripts' / name)
        manifest = json.loads((REPO_ROOT / 'firmware/max4-thr-lis2dw-fifo-v1.json').read_text())
        stock = bytearray(manifest['thr']['size'])
        for entry in manifest['thr']['patches']:
            start = int(entry['offset'], 0)
            value = bytes.fromhex(entry['before'])
            stock[start:start + len(value)] = value
        stock = bytes(stock)
        image = bytearray(stock)
        for entry in manifest['thr']['patches']:
            start = int(entry['offset'], 0)
            value = bytes.fromhex(entry['after'])
            image[start:start + len(value)] = value
        manifest['thr']['stock_sha256'] = hashlib.sha256(stock).hexdigest()
        manifest['thr']['patched_sha256'] = hashlib.sha256(image).hexdigest()
        (bundle / 'firmware/max4-thr-lis2dw-fifo-v1.json').write_text(json.dumps(manifest))
        data = root / 'printer_data'
        (data / 'config').mkdir(parents=True)
        shutil.copy2(REPO_ROOT / 'config/printer.cfg', data / 'config/printer.cfg')
        (data / 'firmware_manifest.json').write_text('{"SOC":{"version":"01.01.07.01"}}')
        python = root / 'klippy-env/bin/python'
        python.parent.mkdir(parents=True)
        python.write_text('transport fixture')
        paths = resolve_runtime_paths(bundle_root=bundle, environ=build_env(data, moonraker_url='http://printer.invalid/printer/objects/query'))
        boot = bytes(0x8000)
        printer = Printer(root, manifest, stock, boot, **kwargs)
        printer.profile = replace(profile, sha256=protocol.digest(boot))
        reporter = create_reporter(io.StringIO(), prefer_plain=True, bundle_root=REPO_ROOT, environ={})
        return paths, printer, reporter

    def execute(self, paths, printer, reporter, *, admit=True, **kwargs):
        profiles = protocol.thr_bootloaders
        with patch.dict(profiles.PROFILES, {printer.profile.sha256: printer.profile}), patch.object(
            profiles, 'ADMITTED_BOOTLOADERS', frozenset((printer.profile.sha256,)) if admit else frozenset(),
        ):
            return thr_firmware.flash_thr_firmware(
                paths=paths, reporter=reporter, run=printer.run, urlopen=printer.urlopen,
                sleep=lambda seconds: None, clock=itertools.count(0, 10).__next__, **kwargs,
            )

    def test_interactive_authorization_defaults_to_no_and_never_enrolls_updates(self):
        paths, printer, reporter = self.fixture()
        def confirm(**kwargs):
            return thr_firmware.confirm_thr_firmware(paths=paths, reporter=reporter, **kwargs)
        for answer in ('', '\n', 'n\n', 'no\n', 'unexpected\n'):
            with self.subTest(answer=answer):
                self.assertFalse(confirm(input_stream=io.StringIO(answer)))
        self.assertFalse(confirm(input_stream=None))
        self.assertFalse(confirm(input_stream=io.StringIO('yes\n'), environ={LOCK_HELD_ENV: '1'}))
        for answer in ('y\n', 'YES\n'):
            with self.subTest(answer=answer):
                self.assertTrue(confirm(input_stream=io.StringIO(answer)))
        self.assertTrue(confirm(explicit=True))
        self.assertFalse((paths.printer_data_root / THR_RECOVERY_MARKER).exists())
        self.assertIn('input shaper calibration', reporter.stream.getvalue())

    def test_stock_and_already_patched_boards_preserve_evidence_and_service_states(self):
        for profile in protocol.thr_bootloaders.PROFILES.values():
            for patched, timer in itertools.product((False, True), repeat=2):
                with self.subTest(profile=profile.sha256, patched=patched, timer=timer):
                    paths, printer, reporter = self.fixture(profile=profile, patched=patched, timer=timer)
                    if not timer:
                        printer.idle_state = 'Idle'
                    printer.restarting_queries = 3
                    self.execute(paths, printer, reporter)
                    self.assertEqual(printer.transfers, 0 if patched else 1)
                    self.assertEqual(printer.states, printer.original)
                    self.assertFalse((paths.printer_data_root / THR_RECOVERY_MARKER).exists())
                    directories = list((paths.printer_data_root / '.tltg_thr_firmware_backups').iterdir())
                    self.assertEqual(len(directories), 1)
                    evidence = json.loads((directories[0] / 'verification.json').read_text())
                    self.assertTrue(evidence['verified'])
                    self.assertEqual(evidence['application_sha256'], printer.manifest['thr']['patched_sha256'])
                    self.assertEqual((directories[0] / 'before/bootloader.bin').read_bytes(), printer.boot)
                    printer_cfg = (paths.config_root / 'printer.cfg').read_text()
                    self.assertEqual('#*# shaper_freq_x' in printer_cfg, patched)
                    self.assertIn('#*# [input_shaper]', printer_cfg)
                    self.assertEqual((directories[0] / 'printer.cfg').is_file(), not patched)
                    if not patched:
                        self.assertEqual((directories[0] / 'before/application.bin').read_bytes(), printer.stock)
                        self.execute(paths, printer, reporter)
                        self.assertEqual(printer.transfers, 1)
                        self.assertEqual(printer.states, printer.original)

    def test_unsafe_preconditions_and_unknown_images_never_program(self):
        for case in ('printing', 'paused', 'unknown-state', 'chamber-hot', 'extra-heater-hot', 'malformed-target', 'unknown-app', 'never-ready'):
            with self.subTest(case=case):
                paths, printer, reporter = self.fixture(failure=case)
                if case in ('printing', 'paused', 'unknown-state'):
                    printer.state = case
                if case == 'chamber-hot':
                    printer.targets['heater_generic chamber'] = 60
                if case == 'extra-heater-hot':
                    printer.targets['heater_generic extra'] = 40
                if case == 'never-ready':
                    printer.restarting_queries = 1000
                if case == 'malformed-target':
                    printer.targets['extruder'] = False
                with self.assertRaises(thr_firmware.ThrFirmwareError):
                    self.execute(paths, printer, reporter)
                self.assertEqual(printer.transfers, 0)
                self.assertEqual(printer.states, printer.original)
                self.assertFalse((paths.printer_data_root / THR_RECOVERY_MARKER).exists())

    def test_unrecognized_and_unadmitted_bootloaders_capture_without_firmware_blocker(self):
        for failure, profile, admit in (
            ('unknown-boot', protocol.thr_bootloaders.FIRST, True),
            (None, protocol.thr_bootloaders.SECOND, False),
        ):
            with self.subTest(failure=failure, profile=profile.sha256):
                paths, printer, reporter = self.fixture(failure=failure, profile=profile)
                config = (paths.config_root / 'printer.cfg').read_bytes()
                self.execute(paths, printer, reporter, admit=admit)
                self.assertEqual(printer.transfers, 0)
                self.assertEqual(printer.states, printer.original)
                self.assertFalse((paths.printer_data_root / THR_RECOVERY_MARKER).exists())
                self.assertEqual((paths.config_root / 'printer.cfg').read_bytes(), config)
                directory, = (paths.printer_data_root / '.tltg_thr_firmware_backups').iterdir()
                capture = directory / 'before'
                self.assertEqual((capture / 'application-region.bin').stat().st_size, 0x18000)
                for path in capture.iterdir():
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                summary = json.loads((capture / 'report.json').read_text())
                self.assertFalse(summary['supported_bootloader'])
                self.assertEqual(len(summary['bootloader_page_sha256']), 16)
                self.assertFalse((directory / 'verification.json').exists())
                self.assertIn('THR firmware was not changed', reporter.stream.getvalue())
                self.assertIn(str(capture / 'report.json'), reporter.stream.getvalue())
                ensure_no_recovery_sentinel(paths.recovery_sentinel_path)

    def test_unverified_service_restoration_retains_blocker(self):
        paths, printer, reporter = self.fixture(failure='restore')
        with self.assertRaises(thr_firmware.ThrFirmwareError):
            self.execute(paths, printer, reporter, admit=False)
        self.assertTrue((paths.printer_data_root / THR_RECOVERY_MARKER).exists())
        self.assertEqual(printer.transfers, 0)
        self.assertEqual(printer.states['klipper.service'], 'inactive')

    def test_ambiguous_writes_retain_blocker_and_do_not_roll_back_configuration(self):
        for failure in ('transfer', 'readback', 'interrupt'):
            with self.subTest(failure=failure):
                paths, printer, reporter = self.fixture(failure=failure)
                config = paths.printer_data_root / 'committed-config'
                config.write_text('verified configuration')
                error = KeyboardInterrupt if failure == 'interrupt' else thr_firmware.ThrFirmwareError
                with self.assertRaises(error):
                    self.execute(paths, printer, reporter)
                self.assertTrue((paths.printer_data_root / THR_RECOVERY_MARKER).is_file())
                self.assertTrue(all(state == 'inactive' for state in printer.states.values()))
                self.assertEqual(config.read_text(), 'verified configuration')
                self.assertIn('#*# shaper_freq_x', (paths.config_root / 'printer.cfg').read_text())
                with self.assertRaises(InstallerError):
                    ensure_no_recovery_sentinel(paths.recovery_sentinel_path)
                output = io.StringIO()
                self.assertEqual(main(['install', '--yes', '--plain'], bundle_root=REPO_ROOT, environ=build_env(paths.printer_data_root, moonraker_url='http://printer.invalid'), stream=output), 1)
                self.assertEqual(config.read_text(), 'verified configuration')

    def test_dry_run_and_ineligible_firmware_do_not_access_uart_or_services(self):
        paths, printer, reporter = self.fixture()
        def forbidden(*args, **kwargs):
            raise AssertionError('Preview or admission accessed services/UART')
        thr_firmware.flash_thr_firmware(paths=paths, reporter=reporter, dry_run=True, run=forbidden, urlopen=printer.urlopen)
        self.assertEqual(sorted(paths.printer_data_root.iterdir()), [paths.config_root, paths.firmware_manifest_path])
        with self.assertRaises(thr_firmware.ThrFirmwareError):
            thr_firmware.flash_thr_firmware(paths=paths, reporter=reporter, environ={LOCK_HELD_ENV: '1'}, run=forbidden)
        paths.firmware_manifest_path.write_text('{"SOC":{"version":"01.01.06.05"}}')
        with self.assertRaises(thr_firmware.ThrFirmwareError):
            thr_firmware.flash_thr_firmware(paths=paths, reporter=reporter, run=forbidden)
        self.assertFalse(thr_firmware.confirm_thr_firmware(paths=paths, reporter=reporter, input_stream=io.StringIO('yes\n')))

    def test_cli_opt_in_is_install_only_and_yes_alone_does_not_authorize(self):
        self.assertFalse(parse_args(['install', '--yes']).flash_thr_fifo)
        self.assertTrue(parse_args(['install', '--yes', '--flash-thr-fifo']).flash_thr_fifo)
        for argv in (['uninstall'], ['restore-backup'], ['auto-update', '--run'], ['install', '--uninstall']):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                parse_args([*argv, '--flash-thr-fifo'])
        root = copy_base_runtime()
        env = build_env(root, moonraker_url='http://printer.invalid')
        def install(paths, manifest, reporter, *, flash_thr_fifo, dry_run, input_stream, environ, **kwargs):
            opted_in = thr_firmware.confirm_thr_firmware(
                paths=paths, reporter=reporter, explicit=flash_thr_fifo,
                dry_run=dry_run, input_stream=input_stream, environ=environ,
            )
            return InstallResult((), (), 'label', None, flash_thr_firmware=opted_in)
        with patch('installer.runtime.cli.run_install', side_effect=install), patch('installer.runtime.cli.flash_thr_firmware', side_effect=AssertionError('Unexpected firmware access')):
            self.assertEqual(main(['install', '--yes', '--plain'], bundle_root=REPO_ROOT, environ=env, stream=io.StringIO()), 0)
        (root / 'firmware_manifest.json').write_text('{"SOC":{"version":"01.01.07.01"}}')
        for flags, answer, expected in ((['--yes'], '', False), ([], '\n', False), ([], 'yes\n', True), (['--yes', '--flash-thr-fifo'], '', True)):
            with self.subTest(flags=flags, answer=answer), patch('installer.runtime.cli.run_install', side_effect=install), patch('installer.runtime.cli.flash_thr_firmware') as flash:
                self.assertEqual(main(['install', '--plain', *flags], bundle_root=REPO_ROOT, environ=env, stream=io.StringIO(), input_stream=io.StringIO(answer)), 0)
                self.assertEqual(flash.called, expected)
        with patch('installer.runtime.cli.run_install', side_effect=AssertionError('Child mutated configuration')):
            self.assertEqual(main(['install', '--yes', '--flash-thr-fifo', '--plain'], bundle_root=REPO_ROOT, environ={**env, LOCK_HELD_ENV: '1'}, stream=io.StringIO()), 1)
