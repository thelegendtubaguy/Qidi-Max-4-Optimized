## Context

QIDI's Fluidd lives in `/home/qidi/fluidd` (owned by `qidi`) and is served by the nginx site `/etc/nginx/sites-available/fluidd` (`root /home/qidi/fluidd;`, CRLF line endings), which the printer-screen operation already backs up and patches. nginx runs as `www-data`; `/home/qidi` is world-readable. The installer runs as the invoking user (`qidi`) and uses sudo only for system files. The fork's release workflow publishes `fluidd.zip` (about 4.4 MB, 13 MB extracted, about 260 entries) for each `vX.Y.Z-qidi.N` tag. Upstream Fluidd and QIDI's Fluidd share Moonraker's `fluidd` database namespace for settings and layouts.

## Goals / Non-Goals

**Goals:**

- Serve the pinned fork build on every install, update, and automatic update, with QIDI's bundle untouched as the rollback.
- Never let nginx serve a missing or partial build.
- Same ownership, drift, compensation, journal recovery, and uninstall guarantees as the other host operations.
- Fall back to QIDI's Fluidd with the existing bundle patches whenever the build cannot be served.

**Non-Goals:**

- Moonraker update-manager integration or updating Fluidd outside installer releases.
- Migrating or rewriting saved Fluidd settings or layouts.
- Removing the bundle patches; they remain the fallback.

## Decisions

### Pinned release, fetched at bundle build time

`installer/package.yaml` pins the release version, download URL, and SHA-256. The bundle builder downloads the archive once into an ignored cache keyed by checksum, verifies it, and copies it to `installer/system/fluidd.zip` in the bundle. Repository checkouts do not carry the archive; the installer reports the build as missing and keeps QIDI's Fluidd. Committing each release archive was rejected to keep binary history out of the repository.

### Package-owned directory with a marker

The build is extracted to `/home/qidi/tltg-fluidd` with directories `0755` and files `0644`, and a marker file holding the archive checksum is written last. The marker proves package ownership: a directory without it is never replaced or removed. The installed build is current when the marker matches the pinned checksum and every archived file matches its hash.

### Rename-based install and rollback

A new or changed build is extracted completely into a sibling staging directory before anything is moved. An update renames the installed build to a sibling `previous` directory and then renames staging into place, so nginx sees either the old or the new tree. The host journal records the operation before the first rename. Compensation and journal recovery remove a package-marked build and rename `previous` back. After the host transaction completes, `previous` is deleted. The persisted restoration preimage is always "absent", because the build is only installed where nothing existed or over an earlier package build.

### One nginx operation, gated on the build

The existing printer-screen nginx operation owns the site file, so the root change is part of the same guarded patch: one backup, one drift check, one restore. It switches `root /home/qidi/fluidd;` to the build directory and inserts the screen route. The operation runs after the build operation and is skipped, leaving the site unchanged, unless the build is current. A site that already carries an earlier package's screen route is updated in place while its first preimage is retained.

### Retiring the bundle patches

The Fluidd bundle and service-worker operations run after the nginx operation. While nginx serves a current build, they apply nothing; a file they own is restored from its preimage when it still matches the last installed patch, under the host journal, and its ownership is released either way. If nginx later stops serving the build, for example after a firmware update rewrites the site, the bundle patches apply again from a fresh preimage.

### Restoration order

Uninstall restores the nginx site before the build, whatever order the ledger recorded them in. The build is removed only while it carries the marker and nginx no longer serves it, so a preserved, operator-modified site never points at a missing directory.

## Risks / Trade-offs

- Browsers holding QIDI's service worker serve its cached Fluidd for one more load; the build's own service worker at the same path then replaces it, as for any Fluidd update.
- The fork drops dashboard card IDs it does not know when it saves a layout, so cards that only QIDI's Fluidd has return to default positions after switching back.
- A firmware update that rewrites the nginx site back to QIDI's exact original lets the next update switch it again; one that rewrites it differently is preserved as operator drift, and QIDI's Fluidd is served with the bundle patches until the site is recognized again.
- The installer bundle grows by about 4.4 MB.
- A failure of the bundle restoration after the rest of the transaction succeeded leaves the ownership recorded and is retried on the next run.
