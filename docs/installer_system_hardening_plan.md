# Installer system hardening plan

## Source behavior

- `../QidiMax4CommunityWiki/docs/mods/making_qidiclient_suck_less.md` replaces animated touchscreen GIFs under `/home/qidi/QIDI_Client/access` with static GIFs from `../QidiMax4CommunityWiki/files/qidiclient-static-gifs.tar.gz`, backs up originals to `/home/qidi/QIDI_Client/access/.gif-backup-<timestamp>`, and restarts `qidi-client.service`.
- `../QidiMax4CommunityWiki/docs/mods/process_hardening_optimiztion.md#apt-sources` replaces `/etc/apt/sources.list` with Debian Bullseye entries for `deb.debian.org` and `security.debian.org`.
- `../QidiMax4CommunityWiki/docs/mods/process_hardening_optimiztion.md#dns-resolution` changes `/etc/resolv.conf` to `/run/resolvconf/resolv.conf`, clears `/etc/resolvconf/resolv.conf.d/head`, writes fallback resolvers to `/etc/resolvconf/resolv.conf.d/tail`, and runs `resolvconf -u`.
- DNS fallback resolvers should be `nameserver 1.1.1.1` followed by `nameserver 8.8.8.8` in `/etc/resolvconf/resolv.conf.d/tail`.
- `../QidiMax4CommunityWiki/docs/mods/process_hardening_optimiztion.md#vpn-client` disables `xl2tpd` with `systemctl disable --now xl2tpd`.
- `../QidiMax4CommunityWiki/docs/mods/process_hardening_optimiztion.md#bluetooth` disables `bluetooth` with `systemctl disable --now bluetooth`.
- `../QidiMax4CommunityWiki/docs/mods/process_hardening_optimiztion.md#algo-app` disables `algo_app.service` with `systemctl disable --now algo_app.service` only when the operator does not use QIDI AI detection features.
- Supported firmware `01.01.06.03` exposes the touchscreen process through `qidi-client.service`; live `01.01.06.03` has `ExecStart=bash /home/qidi/QIDI_Client/bin/start.sh` and process `/home/qidi/QIDI_Client/bin/qidiclient`.
- Supported firmware `01.01.06.03` exposes AI detection through `algo_app.service`; live `01.01.06.03` has `ExecStart=/usr/local/bin/algo_app/main`, working directory `/usr/local/bin/algo_app`, and API `/version` reporting `{"sw_version":"1.1.0"}`.
- Live firmware `01.01.06.03` has `algo_app.service` listening on `0.0.0.0:9010`; `/config` reports detection flags `is_detect_flag=False`, `is_pei_check=False`, `is_foreign_check=False`, and `is_md_check=False` on the inspected machine.
- Touchscreen AI toggles under `Settings` -> `Printing Options` can remain visually checked after `algo_app.service` is disabled; the visible options are `Spaghetti Detection` and `Foreign Object Detection`.
- `Spaghetti Detection` and `Foreign Object Detection` are stored in the `qidiclient` app state, not in the `algo_app.service` backend state.
- Unchecking and rechecking `Spaghetti Detection` and `Foreign Object Detection` on the touchscreen did not re-enable `algo_app.service`, did not restore port `9010`, and did not restore the API.
- `../Qidi-Max4-Defaults/QIDI_MAX4_FIRMWARE_UPDATE_PROCESS.md` records SOC firmware package behavior that touches `/home/qidi/QIDI_Client`, stops `algo_app.service` before install, and enables/starts `algo_app.service` in `postinst`; auto-update reconciliation must assume QIDI firmware updates can undo qidiclient and service hardening.

## Installer scope

- Add a system-optimization phase to `installer/runtime/runner.py` after Klipper config postflight succeeds and before the final install result is printed.
- Keep Klipper config writes under the existing `config/` backup and rollback path in `installer/runtime/rollback.py`.
- Add a separate system-change ledger because `/etc/resolv.conf`, `/etc/resolvconf/resolv.conf.d/*`, `/etc/apt/sources.list`, `/home/qidi/QIDI_Client/access`, and systemd unit state are outside `config/`.
- Store the system-change ledger under `config/tltg_optimized_state.yaml` as an optional top-level `system_ledger` key so older parser code that ignores unknown top-level keys can still read schema version `1` installs.
- Add `installer/runtime/system_optimizations.py` for DNS, APT source, service, qidiclient GIF, sudo, preflight, dry-run, ledger, and rollback operations.
- Move the sudo helpers from `installer/runtime/auto_update.py` into a shared `installer/runtime/sudo.py`, then import the shared helper from `auto_update.py` and `system_optimizations.py`.
- Add bundled static GIF assets under `installer/system/qidiclient-static-gifs.tar.gz` instead of running `curl https://raw.githubusercontent.com/... | sudo bash` from the installer.
- Record the asset SHA-256 in `installer/package.yaml` under a new `system_optimizations.qidiclient_static_gifs.sha256` field.

## Manifest shape

```yaml
system_optimizations:
  enabled_by_default: true
  dns:
    resolv_conf: /etc/resolv.conf
    resolvconf_head: /etc/resolvconf/resolv.conf.d/head
    resolvconf_tail: /etc/resolvconf/resolv.conf.d/tail
    target_symlink: /run/resolvconf/resolv.conf
    fallback_nameservers:
      - 1.1.1.1
      - 8.8.8.8
  apt_sources:
    file: /etc/apt/sources.list
    content: |
      deb http://deb.debian.org/debian bullseye main contrib
      deb-src http://deb.debian.org/debian bullseye main contrib
      deb http://security.debian.org/debian-security bullseye-security main contrib
      deb-src http://security.debian.org/debian-security bullseye-security main contrib
      deb http://deb.debian.org/debian bullseye-updates main contrib
      deb-src http://deb.debian.org/debian bullseye-updates main contrib
  services:
    disable:
      - xl2tpd
      - bluetooth
    optional_disable:
      - id: algo_app
        service: algo_app.service
        prompt: Would you like us to disable QIDI AI detection features?
  qidiclient_static_gifs:
    archive: system/qidiclient-static-gifs.tar.gz
    destination: /home/qidi/QIDI_Client/access
    restart_service: qidi-client.service
```

## Prompt and CLI behavior

- Interactive `install.sh` should prompt `Would you like to apply system hardening and OS optimizations?` before any system write.
- A `Yes` response to the system optimization prompt should record `system_ledger.policy.system_optimizations = enabled`.
- A `No` response to the system optimization prompt should record `system_ledger.policy.system_optimizations = disabled` and skip DNS, APT, qidiclient GIF, VPN, Bluetooth, and AI detection changes.
- `install.sh --yes` should apply DNS, APT source, qidiclient static GIFs, `xl2tpd` disablement, and `bluetooth` disablement without prompting on fresh installs.
- Interactive installs should prompt `Would you like us to disable QIDI AI detection features?` when system optimizations are enabled.
- The AI detection prompt should state that disabling `algo_app.service` does not clear touchscreen AI toggles because `Spaghetti Detection` and `Foreign Object Detection` are stored in `qidiclient` app state.
- A `Yes` response to the AI prompt should print `Turn off Settings -> Printing Options -> Spaghetti Detection and Foreign Object Detection on the touchscreen if you want the screen to match the disabled backend state.`, run `systemctl disable --now algo_app.service`, record the previous enabled/active state in `system_ledger`, and record `system_ledger.policy.ai_detection = disable`.
- A `No` response to the AI prompt should leave `algo_app.service` unchanged and record `system_ledger.policy.ai_detection = keep_enabled`.
- `install.sh --yes` should keep `algo_app.service` unchanged on fresh installs unless `--disable-ai-detection` is supplied, because non-interactive mode cannot ask the operator about AI detection use.
- Add `--skip-system-optimizations` to bypass DNS, APT, qidiclient GIF, VPN, Bluetooth, and AI detection changes and record `system_ledger.policy.system_optimizations = disabled`.
- Add `--disable-ai-detection` to disable `algo_app.service` during non-interactive installs and record `system_ledger.policy.ai_detection = disable`.
- Add `--keep-ai-detection` to suppress the AI prompt, leave `algo_app.service` unchanged, and record `system_ledger.policy.ai_detection = keep_enabled`.
- `install.sh --dry-run` should list every planned system operation and every skipped system operation without writing `/etc`, `/home/qidi/QIDI_Client/access`, or systemd state.
- Auto-update child installs invoked by `auto-update.sh --run` should follow `system_ledger.policy` from the previous successful user-invoked install.
- Auto-update should apply any new system hardening operation added in a newer bundle when `system_ledger.policy.system_optimizations = enabled`.
- Auto-update should not apply new system hardening operations when `system_ledger.policy.system_optimizations = disabled`.
- Auto-update should disable `algo_app.service` only when `system_ledger.policy.ai_detection = disable`.
- Auto-update should keep `algo_app.service` unchanged when `system_ledger.policy.ai_detection = keep_enabled` or missing.

## Auto-update reconciliation

- Treat system optimization state as desired state, not one-time migration state.
- Each auto-update run should evaluate the live system against the current bundle's `system_optimizations` manifest and the stored `system_ledger.policy`.
- When `system_ledger.policy.system_optimizations = enabled`, auto-update should reapply DNS, APT sources, qidiclient static GIFs, `xl2tpd` disablement, and Bluetooth disablement if QIDI firmware updates or manual changes reverted them.
- When a newer bundle adds another default system hardening operation, auto-update should apply it automatically if the stored policy is enabled.
- When `system_ledger.policy.ai_detection = disable`, auto-update should re-disable `algo_app.service` if QIDI firmware updates or manual changes re-enabled it.
- When `system_ledger.policy.ai_detection = keep_enabled`, auto-update should not disable `algo_app.service`, even if other system optimizations are enabled.
- Auto-update should refresh `system_ledger.actions[]` after every reconciliation so the ledger records the latest observed preimage, desired state, and postflight result.
- Auto-update should keep original restore preimages from the first time an operation was applied in `system_ledger.restore_preimages[]`; reconciliation preimages should not overwrite the values needed for uninstall restoration unless the user explicitly accepts the new current state as baseline.
- Auto-update should report `System optimizations reconciled.` only when at least one drifted or newly added operation was applied.
- Auto-update should report `System optimizations already current.` when policy is enabled and every selected operation already matches desired state.
- Auto-update should skip system reconciliation when no valid `system_ledger.policy` exists, except for fresh installs where user prompts or CLI flags create that policy.

## Operation details

### DNS

- Preflight should require `/sbin/resolvconf` or `/usr/sbin/resolvconf` before enabling the DNS operation.
- Preflight should read the current `/etc/resolv.conf` file type, symlink target, mode, owner, group, and content.
- Preflight should read `/etc/resolvconf/resolv.conf.d/head` and `/etc/resolvconf/resolv.conf.d/tail` when those files exist.
- Install should write an empty `/etc/resolvconf/resolv.conf.d/head`.
- Install should write `/etc/resolvconf/resolv.conf.d/tail` with `nameserver 1.1.1.1` and `nameserver 8.8.8.8`.
- Install should run `resolvconf -u` after writing `head` and `tail`.
- Install should replace `/etc/resolv.conf` with a symlink to `/run/resolvconf/resolv.conf`.
- Postflight should verify `readlink /etc/resolv.conf` returns `/run/resolvconf/resolv.conf`.
- Postflight should verify `/run/resolvconf/resolv.conf` contains DHCP-provided resolver lines before fallback lines when `/run/resolvconf/interface/*.dhcp` contains nameservers.
- Postflight should verify `/etc/resolv.conf` does not contain `114.114.114.114` or `options edns0 trust-ad` unless DHCP or another resolvconf source reintroduced those values.

### APT sources

- Preflight should read `/etc/apt/sources.list` mode, owner, group, and content.
- Install should replace `/etc/apt/sources.list` with the Debian Bullseye content from `system_optimizations.apt_sources.content`.
- Install should not run `apt update` or `apt upgrade`; package index mutation is slow, network-dependent, and unrelated to Klipper config installation.
- Postflight should compare `/etc/apt/sources.list` byte-for-byte against the manifest content.

### Service disablement

- Preflight should run `systemctl is-enabled <service>` and `systemctl is-active <service>` for `xl2tpd`, `bluetooth`, and `algo_app.service`.
- Missing `xl2tpd` or `bluetooth` units should be recorded as `missing` and skipped without failing the config install.
- Install should run `systemctl disable --now xl2tpd` when the unit exists.
- Install should run `systemctl disable --now bluetooth` when the unit exists.
- Install should run `systemctl disable --now algo_app.service` only when the AI prompt or `--disable-ai-detection` selects disablement.
- Disabling `algo_app.service` should be treated as backend disablement only; the installer should not assume touchscreen AI toggle state has been cleared.
- Postflight should run `systemctl is-enabled` and `systemctl is-active` after each disable operation and accept `disabled`, `masked`, `inactive`, or `not-found` according to the recorded unit state.

### qidiclient static GIFs

- Preflight should require `/home/qidi/QIDI_Client/access` to exist before enabling the qidiclient GIF operation.
- Preflight should validate `installer/system/qidiclient-static-gifs.tar.gz` against the SHA-256 stored in `installer/package.yaml`.
- Preflight should reject archive members with absolute paths, `..`, symlinks, devices, or paths outside the intended `/home/qidi/QIDI_Client/access` relative tree.
- Install should copy the current GIF files replaced by the archive into `/home/qidi/QIDI_Client/access/.gif-backup-<timestamp>`.
- Install should extract static GIF replacements from a temporary directory into `/home/qidi/QIDI_Client/access`.
- Install should preserve destination ownership and modes where existing GIF files are replaced.
- Install should run `systemctl restart qidi-client.service` after GIF replacement when `qidi-client.service` exists.
- Postflight should hash every installed static GIF and compare it to the archive member hash.

## Ledger and rollback

- `system_ledger.policy.system_optimizations` should store `enabled` or `disabled` from the user's previous answer or CLI flag.
- `system_ledger.policy.ai_detection` should store `disable`, `keep_enabled`, or `unset` from the user's previous answer or CLI flag.
- `system_ledger.actions[]` should record `id`, `status`, `started_at`, `completed_at`, `preimage`, `desired`, `postflight`, `source`, and `reconciled` for each selected system operation.
- `source` should distinguish `interactive_install`, `yes_install`, `auto_update_reconcile`, and `uninstall_restore`.
- `reconciled` should be `true` when an operation was reapplied because live state drifted from desired state.
- `system_ledger.restore_preimages[]` should preserve the first preimage captured before the installer initially changed each operation.
- Reconciliation runs should append action records without replacing `restore_preimages[]`.
- File preimages should store content SHA-256 and backup paths under `/home/qidi/printer_data/tltg_optimized_system_backups/<install-id>/`.
- `/etc/resolv.conf` preimage data should record whether the original path was a regular file, symlink, or missing path.
- Service preimages should record the original `systemctl is-enabled` and `systemctl is-active` values before `disable --now` runs.
- qidiclient preimages should record the `.gif-backup-<timestamp>` path and every replaced GIF relative path.
- A transient journal at `/home/qidi/printer_data/.tltg_optimized_system_journal.json` should be written before each system operation starts.
- A system operation failure should roll back only the system operations recorded in the transient journal.
- A system operation failure after Klipper config installation should not roll back the already verified Klipper config installation unless the failure occurred before `config/tltg_optimized_state.yaml` was written.
- A system operation failure should print `System optimizations were not fully applied. Klipper config installation remains installed.` after rollback completes.
- Successful system operations should delete `/home/qidi/printer_data/.tltg_optimized_system_journal.json` after `config/tltg_optimized_state.yaml system_ledger` is written.

## Uninstall behavior

- `install.sh --uninstall` should restore system changes only when `config/tltg_optimized_state.yaml system_ledger` contains applied system operations.
- Interactive uninstall should prompt `Would you like to restore system settings changed by the optimized installer?` after the existing Klipper config uninstall confirmation.
- A `Yes` response should restore DNS, APT source, service enablement/active state, qidiclient GIFs, and AI detection service state from `system_ledger.restore_preimages[]`.
- A `No` response should uninstall only the Klipper config changes and leave system optimizations in their current state.
- `install.sh --uninstall --yes` should restore system changes recorded in `system_ledger`.
- Add `install.sh --uninstall --keep-system-optimizations` to remove Klipper config changes while keeping DNS, APT source, service disablement, qidiclient GIFs, and AI detection decisions.
- DNS uninstall should restore original `/etc/resolv.conf`, `/etc/resolvconf/resolv.conf.d/head`, and `/etc/resolvconf/resolv.conf.d/tail` from file preimages, then run `resolvconf -u` when resolvconf exists.
- APT uninstall should restore the original `/etc/apt/sources.list` content, mode, owner, and group.
- Service uninstall should restore each service to its recorded enabled and active state when the unit still exists.
- qidiclient uninstall should restore GIFs from the recorded `.gif-backup-<timestamp>` directory and restart `qidi-client.service` when the unit exists.
- AI uninstall should only re-enable or restart `algo_app.service` when the installer disabled it and the preimage says it was enabled or active.

## Tests and validation

- Add unit tests for manifest parsing under `installer/tests/unit/test_system_optimizations.py`.
- Add unit tests for DNS file planning, resolvconf command ordering, and `/etc/resolv.conf` symlink restoration.
- Add unit tests for service preimage capture with fake `systemctl is-enabled` and `systemctl is-active` results.
- Add unit tests for qidiclient archive validation that reject absolute paths, `..`, symlinks, device files, and unexpected roots.
- Add integration tests under `installer/tests/integration/test_system_optimization_flow.py` using temporary fake `/etc`, fake `/home/qidi/QIDI_Client/access`, fake `systemctl`, and fake `resolvconf` commands.
- Add dry-run assertions that no fake `/etc`, fake systemd state, or fake GIF file changes occur.
- Add auto-update reconciliation tests where a firmware-update fixture restores `114.114.114.114`, rewrites China APT mirrors, re-enables `xl2tpd`, re-enables Bluetooth, restores animated qidiclient GIFs, and re-enables `algo_app.service`.
- Add auto-update policy tests where a newer bundle adds a new default hardening operation and an existing `system_ledger.policy.system_optimizations = enabled` causes that operation to run without prompting.
- Add auto-update policy tests where `system_ledger.policy.system_optimizations = disabled` prevents newly added hardening operations.
- Add auto-update policy tests where `system_ledger.policy.ai_detection = keep_enabled` prevents `algo_app.service` disablement while other system optimizations reconcile.
- Update `scripts/run_installer_core_tests.py` to include the new system optimization unit and integration tests.
- Update `scripts/build_installer_bundle.py --smoke-test` to verify `installer/system/qidiclient-static-gifs.tar.gz` is included in the release archive.
- Run `python3 scripts/run_installer_core_tests.py` after installer runtime changes.
- Run `python3 scripts/build_installer_bundle.py --output-dir dist --channel dev --build-id local --smoke-test` after bundle packaging changes.

## Documentation updates

- Update `docs/installer_runtime_contract.md` with the new system optimization prompt strings, status strings, dry-run behavior, ledger fields, rollback behavior, uninstall behavior, and CLI flags.
- Update `docs/installer_restore_helper.md` if the restore helper should warn that config restore does not restore `/etc`, systemd unit state, or `/home/qidi/QIDI_Client/access` unless `system_ledger` restore is implemented there.
- Update `docs/optimized_vs_stock.md` with behavior-level entries for DHCP-first DNS with public fallback, Debian APT mirrors, disabled VPN client, disabled Bluetooth, optional disabled AI detection service, and static qidiclient spinner GIFs.
- Add a wiki-facing operator section that maps installer behavior to `../QidiMax4CommunityWiki/docs/mods/process_hardening_optimiztion.md` and `../QidiMax4CommunityWiki/docs/mods/making_qidiclient_suck_less.md`.

