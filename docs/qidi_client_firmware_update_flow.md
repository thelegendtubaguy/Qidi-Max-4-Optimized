# QIDI Client Firmware Update Flow

This note captures what can be confirmed from the shipped `qidi_client/bin/qidiclient` binary about online firmware update checks and downloads.

It focuses on:

- the URL path used to check for updates
- the hostnames present in the binary
- what appears to happen after a new version is found
- what `currentVersion` and `deviceId` most likely mean

## Evidence Source

These findings come from string inspection of:

- `qidi_client/bin/qidiclient`

and from:

- a live packet capture while opening the firmware page
- live `qidi-client` log output while opening the firmware page
- targeted static disassembly of the request-construction code paths

## Confirmed Update Check Path

The binary contains this exact path string:

```text
/backend/v1/fireware/upgrade-info?hardware=
```

The same cluster of strings also contains:

```text
QD_MAX4
&currentVersion=
&deviceId=
```

So the update check request shape is strongly supported as:

```text
<api-base>/backend/v1/fireware/upgrade-info?hardware=QD_MAX4&currentVersion=<...>&deviceId=<...>
```

The path contains QIDI's apparent `fireware` spelling rather than `firmware`.

## Confirmed API Hosts

The binary contains these API base hosts:

```text
https://api.qidimaker.com
https://api-cn.qidi3dprinter.com
```

So the check URL is most likely one of these, depending on region and runtime selection logic:

```text
https://api.qidimaker.com/backend/v1/fireware/upgrade-info?hardware=QD_MAX4&currentVersion=<currentVersion>&deviceId=<deviceId>
https://api-cn.qidi3dprinter.com/backend/v1/fireware/upgrade-info?hardware=QD_MAX4&currentVersion=<currentVersion>&deviceId=<deviceId>
```

## Confirmed Runtime Behavior

The live client log shows that simply opening the firmware page triggers a version request:

```text
page to -> Page_Firmware
[HTTP] Func: [版本请求]
[HTTP] Func: [版本请求成功]
```

So the request happens on page entry, not only after pressing a separate update button.

The live packet capture confirms that this printer session used:

```text
api.qidimaker.com
```

Specifically:

- the printer queried DNS for `api.qidimaker.com`
- DNS resolved it to `104.21.96.25` and `172.67.150.123`
- the printer opened HTTPS connections to those Cloudflare IPs on port `443`
- the TLS ClientHello included SNI for `api.qidimaker.com`
- the TLS ALPN advertisement included `h2` and `http/1.1`

So for this printer and this session, the firmware check did not go to the China API host and did not go to any `download_aliyun.qidi3dprinter.com` URL.

The shipped client binary also contains direct references to:

```text
/home/qidi/update/
/home/qidi/update/firmware_manifest.json
firmware_manifest.json
```

and the live printer file at `/home/qidi/update/firmware_manifest.json` contains:

```text
SOC.version = 01.01.06.01
SOC.region = NA
MCU.version = 02.01.01.09
THR.version = 02.02.01.08
BOX.version = 02.03.01.21
CLOSED_LOOP_MOTOR.version = 03.01.10.13
```

This is the strongest evidence so far that `currentVersion` for the online update check is sourced from the local SOC package version in that manifest.

A live `openat` trace of `qidiclient` while entering the firmware page shows:

```text
openat(..., "/home/qidi/update/firmware_manifest.json", O_RDONLY) = 33
```

right before the firmware page assets are loaded.

That makes the manifest read on firmware-page entry directly observed, not just inferred from binary strings.

The live Moonraker database also contains a separate machine-unique `instance_id`, which is intentionally redacted in this repo.

The live CPU serial is also machine-unique and intentionally redacted here.

Moonraker derives the default user alias from that serial as:

```text
3DP-{first3}-{last3}
```

which matches the stored alias:

```text
3DP-XXX-XXX
```

## Exact Request Shape Recovered From Process Memory

The strongest evidence so far came from readable strings in a live `qidiclient` core dump on the printer.

Those strings included the full request form, with machine-unique identifiers redacted here:

```text
https://api.qidimaker.com/backend/v1/fireware/upgrade-info?hardware=QD_MAX4&currentVersion=01.01.06.01&deviceId=DEVICE_ID_REDACTED
fireware/upgrade-info?hardware=QD_MAX4&currentVersion=01.01.06.01&deviceId=DEVICE_ID_REDACTED HTTP/2
X-DeviceId: DEVICE_ID_REDACTED
x-deviceid: DEVICE_ID_REDACTED
```

The same memory dump also contained a JSON-like state object with matching runtime context:

```text
{"bind":false,"firmwareVersion":"01.01.06.01","ipAddress":"IP_REDACTED","macAddress":"MAC_REDACTED","region":"NA","serialNumber":"CPU_SERIAL_REDACTED"}
```

Taken together, that is strong evidence that on this printer:

- the exact update host is `https://api.qidimaker.com`
- the exact path is `/backend/v1/fireware/upgrade-info`
- `currentVersion` is `01.01.06.01`
- `deviceId` equals the uppercase CPU serial for this machine
- `X-DeviceId` carries the same value as the query-string `deviceId`
- the client is speaking HTTP/2 on this path

## Verified Live Query

Using the recovered header set, a fresh timestamp, and a fresh nonce, the endpoint is directly callable with `curl`.

A verified test against this printer used an older `currentVersion` value and returned the currently available firmware release metadata.

Example request shape:

```text
curl -sS "https://api.qidimaker.com/backend/v1/fireware/upgrade-info?hardware=QD_MAX4&currentVersion=01.01.05.04&deviceId=DEVICE_ID_REDACTED" \
  -H "User-Agent: xindi/4.4.23" \
  -H "Accept: */*" \
  -H "Accept-Language: zh_CN" \
  -H "Content-Type: application/json" \
  -H "X-DeviceId: DEVICE_ID_REDACTED" \
  -H "X-DeviceType: X-MAX4" \
  -H "X-Nonce: NONCE_REDACTED" \
  -H "X-Platform: 3DPrinter" \
  -H "X-Region: NA" \
  -H "X-Signature: SIGNATURE_REDACTED" \
  -H "X-Timestamp: TIMESTAMP_REDACTED" \
  -H "X-Timezone: +00:00" \
  -H "X-Version: 01.01"
```

Verified response shape:

```json
{
  "code": 200,
  "message": "返回成功",
  "data": {
    "version": "01.01.06.01",
    "url": "https://public-cdn.qidimaker.com/upgrade/3DPrinter/QD_MAX4/01.01.06.01/.../QD_MAX4_01.01.06.01_20260312_Release.zip",
    "description": "https://wiki.qidi3d.com/en/software/qidi-studio/release-notes/release-note-02-04-01-11",
    "needUpdate": true,
    "title": "update",
    "isForce": false,
    "apkSize": "243.88 MB"
  }
}
```

So a working read of the current Max 4 release from an older starting version is:

- available version: `01.01.06.01`
- download URL host: `https://public-cdn.qidimaker.com`
- release-notes URL: `https://wiki.qidi3d.com/en/software/qidi-studio/release-notes/release-note-02-04-01-11`
- update required from `01.01.05.04`: `true`

Additional live header values recovered from process memory:

```text
Host: api.qidimaker.com
User-Agent: xindi/4.4.23
Accept: */*
Accept-Language: zh_CN
Content-Type: application/json
X-DeviceType: X-MAX4
X-Platform: 3DPrinter
X-Region: NA
X-Timezone: +00:00
X-Version: 01.01
X-Nonce: NONCE_REDACTED
X-Signature: SIGNATURE_REDACTED
X-Timestamp: TIMESTAMP_REDACTED
```

Across the sampled live request fragments in the core dump:

- `X-Nonce` had multiple unique values
- `X-Signature` had one repeated 64-hex value
- `X-Version` was consistently `01.01`

That means the signature did not appear to vary with the observed nonce values in these memory fragments, although this note does not yet prove the exact signing algorithm or whether the client was reusing a cached header block.

## Request Auth And Headers

The binary supports `Authorization` as a bearer-token header.

Confirmed string evidence:

```text
Bearer 
Authorization
accessToken
user.token
X-Version
X-Signature
X-Timestamp
X-Region
X-Nonce
X-DeviceId
```

Static analysis of the request builder shows:

- `Authorization` is built as `Bearer ` plus a runtime token string
- `X-Signature`, `X-Timestamp`, `X-Region`, `X-Nonce`, and `X-DeviceId` are populated as normal runtime header values before the request is handed to libcurl
- the signature itself appears to be computed earlier and then attached here as a prebuilt string

However, live process-memory searches on this printer did not find `Authorization:` or `Bearer ` in the captured firmware-check request fragments.

That matches the live state object recovered from memory:

```text
{"bind":false,...}
```

and the live Moonraker config state, which showed:

```text
user.token = ""
```

So the best current interpretation is:

- the client binary supports bearer-token auth in general
- this specific printer appears unbound
- this specific firmware-check flow relied on signed QIDI headers without an `Authorization` header in the observed request fragments

## Most Likely Request Shape

Best current reconstruction:

```text
GET https://api.qidimaker.com/backend/v1/fireware/upgrade-info?hardware=QD_MAX4&currentVersion=<firmwareVersion>&deviceId=<deviceId>
```

with headers shaped like:

```text
Authorization: Bearer <accessToken>
X-Version: <runtime value>
X-Signature: <runtime value>
X-Timestamp: <runtime value>
X-Region: <runtime value>
X-Nonce: <runtime value>
X-DeviceId: <runtime value>
Accept-Language: <runtime value>
X-Timezone: <runtime value>
```

Why `GET` is the current best read:

- the firmware path is assembled as one URL string with query parameters
- the generic libcurl executor supports request bodies, but only when the caller populates body or upload fields
- the `checkNewVersion` request-construction path does not currently show a forced custom method or a clearly populated POST body

This is no longer just a static inference. The URL shape and `X-DeviceId` form were recovered from live process memory, while the use of `GET` is still inferred from the surrounding static and wire evidence.

## Live Endpoint Probe

The endpoint is publicly reachable, but it is not anonymously callable with a bare URL.

I probed these URLs directly:

```text
https://api.qidimaker.com/backend/v1/fireware/upgrade-info?hardware=QD_MAX4&currentVersion=01.01.06.01&deviceId=test
https://api-cn.qidi3dprinter.com/backend/v1/fireware/upgrade-info?hardware=QD_MAX4&currentVersion=01.01.06.01&deviceId=test
```

With no special headers, both returned HTTP `401` with:

```json
{"code":2010,"message":"X-Timestamp missing in request header",...}
```

After adding headers step by step, the API continued validating required headers in this order:

```text
X-Timestamp
X-DeviceType
X-Signature
X-Platform
Accept-Language
X-Timezone
```

That behavior strongly supports the conclusion that the online firmware check uses a signed request profile, not a simple public GET.

It also implies that a faithful client request likely includes at least these headers:

```text
X-Timestamp
X-DeviceType
X-DeviceId
X-Region
X-Nonce
X-Version
X-Signature
X-Platform
Accept-Language
X-Timezone
```

What I have not yet reproduced is the exact signature algorithm or header values needed to obtain a successful response.

## Confirmed Response Clues

Near the update-check strings, the binary also contains:

```text
firmwareVersion
needUpdate
description
URL:
```

This strongly suggests the update-check response includes at least:

- a current or target firmware version field
- a boolean or flag-like `needUpdate`
- descriptive text
- a URL field used for the download step

## Confirmed Download Hosts

The binary contains these download hostnames:

```text
https://download.apac.qidi3dprinter.com
https://download_aliyun.qidi3dprinter.com
https://download.eea.qidi3dprinter.com
https://download.na.qidi3dprinter.com
https://download.others.qidi3dprinter.com
```

What is not visible in the binary is a single fixed firmware ZIP path on one of those hosts.

## Public Front-End Page On `download_aliyun.qidi3dprinter.com`

The binary also contains this page-style URL template:

```text
https://download_aliyun.qidi3dprinter.com/#/?api=CN&model=X-MAX4&regin=&sn=&v=1&ver=01.01.06.01
```

Calling that URL returns a small HTML shell that loads these JavaScript bundles:

```text
https://download_aliyun.qidi3dprinter.com/js/manifest.js?1bc75b192f58f7189d95
https://download_aliyun.qidi3dprinter.com/js/vendor.js?da8640c34281cd4b61b0
https://download_aliyun.qidi3dprinter.com/js/index.js?1947b385132d6ee4e2f0
```

So the visible page is a front-end app, not a directly rendered server page.

At the time of this note, I have not yet extracted a clean public release-notes API path from those minified bundles.

Based on the page assets and extracted URLs, this front-end appears to be used for public QIDI Link or version-information flows rather than the actual printer-side firmware availability check.

## Confirmed Download Flow Behavior

The binary logs contain:

```text
Starting incremental online update from url: {}
Starting downloading update package
Download completed
/home/qidi/download/
online_update.zip
Starting online update
Online update completed
Online update failed
```

That strongly supports this flow:

1. call the `upgrade-info` endpoint
2. parse a response that contains `needUpdate` and a download URL
3. pass that URL into the online updater
4. download the package to `/home/qidi/download/online_update.zip`
5. extract and apply the update from there

So the firmware package URL appears to be response-provided, not hardcoded as one fixed path in the client binary.

## What `currentVersion` Most Likely Is

Best-supported interpretation:

- `currentVersion` is the printer's current top-level firmware package version, not the MCU-only version and not the box-only version

Why this is the best current read:

1. The update-check endpoint uses a single `currentVersion` query parameter for the whole machine update flow.
2. The same binary separately tracks component versions such as:
   - `mcu_version`
   - `mcu_thr_version`
   - `closed_loop_x_version`
   - `closed_loop_y_version`
   - `previous_version`
3. The online updater then applies a package that can contain multiple components:
   - `THR firmware`
   - `MCU firmware`
   - `BOX firmware`
   - closed-loop motor firmware
4. The binary also contains the field name `firmwareVersion`, which is a better match for the package-level version than for one subcomponent.
5. The binary also contains `PrinterDataManager::FirmwareVersion`, which is the strongest current candidate for the runtime source of `currentVersion`.
6. The client binary explicitly references `/home/qidi/update/firmware_manifest.json`, and that file exposes `SOC.version = 01.01.06.01` on the live printer.

There is also one visible example version string embedded in a QIDI download/history URL:

```text
01.01.06.01
```

That looks like the same kind of value likely used for `currentVersion`, but the binary evidence here does not prove that exact string is the current machine's runtime value.

What is not yet proven from the available files:

- the exact field-to-query wiring that copies `PrinterDataManager::FirmwareVersion` into `currentVersion`
- whether there is any fallback path if that package-level firmware version is unavailable

## What `deviceId` Most Likely Is

Best-supported interpretation:

- `deviceId` is separate from `serialNumber` and is probably a QIDI logical device identifier or a locally derived hardware identity used by QIDI's cloud APIs

Why this is the best current read:

1. The binary contains `deviceId` in the same area as cloud and binding APIs:

```text
/auth/v1/device/get/bindCode
/auth/v1/device/bind/callback
/auth/v1/get/bind/status
X-DeviceId
Authorization
Bearer
```

2. The binary also contains `serialNumber` as a separate field name near the same HTTP string cluster.
3. The update-check URL includes `deviceId`, while `serialNumber` appears to be tracked separately.
4. There are also nearby cloud-reporting strings such as:

```text
/community/v1/device/status/report
macAddress
ipAddress
serialNumber
```

That separation makes it unlikely that `deviceId` is just another label for the printer serial number.

The strongest current static candidates for the underlying identity source are:

```text
ID_SERIAL
ID_SERIAL_SHORT
ID_FS_UUID
cat /proc/cpuinfo | grep Serial| awk '{printf "%s", substr($0, index($0, ":") + 2)}'
```

The binary also imports `libudev` helpers, which makes a hardware-derived ID plausible.

However, the stronger live process-memory evidence indicates that the firmware-check `deviceId` is the uppercase CPU serial on this machine, not Moonraker's separate `instance_id`.

Best current inference:

- `deviceId` is a hardware-derived logical identifier, and on this printer it matches the uppercase CPU serial recovered from live process memory

What is not yet proven from the available files:

- where the client persists that value locally
- whether the machine can check for updates when unbound by falling back to another identifier
- whether the query-string `deviceId` and `X-DeviceId` always carry the same value on all machines and firmware revisions

## What Did Not Pan Out

The Moonraker SQLite database at `/home/qidi/printer_data/database/moonraker-sql.db` does contain tables such as:

```text
authorized_users
config
job_history
job_totals
namespace_store
table_registry
```

but a targeted search for `deviceId`, `accessToken`, `user.token`, `user.region`, `serialNumber`, `firmwareVersion`, and `currentVersion` in `namespace_store` did not return useful rows.

There is also a root-owned file at `/root/.auth_cache` that contains 128 ASCII characters and base64-decodes to 96 bytes of binary data, but the current binary analysis did not recover a direct string reference to `/root/.auth_cache` from `qidiclient`.

So at this point:

- `firmware_manifest.json` is strongly supported as part of the `currentVersion` path
- `moonraker|instance_id` exists, but it is no longer the leading `deviceId` candidate
- `/root/.auth_cache` is still only a candidate auth-related blob, not a confirmed input to the firmware check

The running `qidiclient` process environment did not expose helpful `token`, `region`, `device`, `serial`, `version`, `mqtt`, or `frp` variables.

The `openat` trace during firmware-page entry did not show `qidiclient` opening:

- `/root/.auth_cache`
- `/home/qidi/printer_data/database/moonraker-sql.db`
- `/root/Frp/frpc.json`
- `/root/Frp/servers.json`

So those values are likely either:

- already resident in process memory before the firmware page is opened, or
- obtained through another path that was not exercised in this narrow trace window

The `download_aliyun.qidi3dprinter.com/#/?...` URL above does not appear to be the actual firmware availability check endpoint and does not appear to be the direct package download URL.

Why:

- it is an `#/?...` style page URL
- it carries `model`, `sn`, and `ver`
- the fetched front-end bundle exposes public app-download links such as QIDI Link
- the real availability check is separately exposed by the signed `api.qidimaker.com` or `api-cn.qidi3dprinter.com` `upgrade-info` endpoint

So this URL should be treated as a public front-end page, not as the actual firmware-check API and not as the actual `online_update.zip` package fetch.

## Best Current Summary

Confirmed:

- the client checks for updates with `/backend/v1/fireware/upgrade-info?hardware=QD_MAX4&currentVersion=<...>&deviceId=<...>`
- the API base is region-dependent and at least two API hosts are present in the binary
- this printer session actually connected to `api.qidimaker.com` when the firmware page was opened
- opening the firmware page triggers the version request immediately
- the client binary supports bearer-token auth, but the live unbound-printer request fragments showed only signed QIDI headers including `X-Signature`, `X-Timestamp`, `X-Region`, `X-Nonce`, and `X-DeviceId`
- the live request fragments include `User-Agent: xindi/4.4.23`, `Content-Type: application/json`, `X-DeviceType: X-MAX4`, `X-Platform: 3DPrinter`, `X-Region: NA`, `X-Timezone: +00:00`, and `X-Version: 01.01`
- the live core dump shows six unique `X-Nonce` values but one repeated 64-hex `X-Signature` value
- no live `Authorization:` or `Bearer ` header was recovered from the captured request fragments on this unbound printer
- the client binary explicitly references `/home/qidi/update/firmware_manifest.json`
- the live printer manifest reports `SOC.version = 01.01.06.01` and `SOC.region = NA`
- a live `openat` trace shows `qidiclient` reading `/home/qidi/update/firmware_manifest.json` when entering the firmware page
- readable live process-memory strings expose the exact `upgrade-info` URL shape with `currentVersion=01.01.06.01` and `deviceId=DEVICE_ID_REDACTED`
- readable live process-memory strings expose `X-DeviceId: DEVICE_ID_REDACTED`
- the live CPU serial and stored alias are machine-unique and intentionally redacted in this repo
- the response likely contains `needUpdate`, `description`, and a URL field
- the actual update package is then downloaded to `/home/qidi/download/online_update.zip`

Best current inference:

- `currentVersion` is the machine's package-level firmware version, likely owned by `PrinterDataManager::FirmwareVersion` and sourced from the local SOC manifest data
- `deviceId` is a hardware-derived logical identifier and, on this printer, matches the uppercase CPU serial recovered from live process memory
- the request is most likely a signed `GET` with query parameters and no body
- on an unbound printer, the firmware-check flow appears to rely on signed QIDI headers without bearer-token auth

Not yet proven from this repo snapshot:

- the exact field-to-query wiring that copies manifest/package version state into `currentVersion`
- the exact code path that derives `deviceId` from machine identity state
- the exact signature algorithm and canonicalized signing input
- why `X-Version` is `01.01` while `currentVersion` is `01.01.06.01`
- whether all firmware revisions and printer models derive `deviceId` the same way
- the exact JSON schema returned by the `upgrade-info` endpoint
