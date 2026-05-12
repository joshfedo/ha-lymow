# Lymow API — Reverse Engineering Notes

Captured via mitmproxy from the official Android app (v2.1.46).
APK analysed via `strings` on `assets/index.android.bundle` (React Native bundle).

---

## Multi-Region Architecture

The app ships with **4 regions**, each with its own full stack. The region is
selected at account registration time — it is baked into the Cognito Identity
Pool ID returned after login. The integration must detect which region a user
belongs to and use the corresponding endpoints.

**How to determine the user's region:** After `InitiateAuth` / `RespondToAuthChallenge`,
call `cognito-identity` to get the Identity ID. Its prefix (`eu-west-1:`, `us-east-2:`,
etc.) tells you the region for all subsequent API calls.

| Region | Coverage |
|--------|----------|
| `eu-west-1` | Europe |
| `us-east-2` | Americas |
| `ap-southeast-2` | Australia / SE Asia |
| `ap-east-1` | East Asia (HK) |

---

## Authentication

Uses **AWS Amplify 6.15.5** with **AWS Cognito** (SRP auth). All regions share
the same auth flow but use region-local Cognito endpoints.

### Cognito Config Per Region

| Region | User Pool ID | Identity Pool ID |
|--------|-------------|-----------------|
| `eu-west-1` | `eu-west-1_6qNPbnrrd` | `eu-west-1:c905a69c-0153-401a-a879-0c50b892015b` |
| `us-east-2` | (not yet extracted) | `us-east-2:037db699-5df0-4ed2-92b8-0dd0f1843918` |
| `ap-southeast-2` | `ap-southeast-2_vNriuUNeQ` | `ap-southeast-2:87d0fe24-16af-4189-b02f-984a7ed14ee0` |
| `ap-east-1` | `ap-east-1_23Lf1WZer` | `ap-east-1:3e9265aa-f564-4083-8e1e-988e6cfdc446` |

Cognito Auth Domain: `mow.auth.<region>.amazoncognito.com`
S3 user data bucket pattern: `mow-user-data-<region>`
App Client ID (eu-west-1, partial): `c1e40b87b1c283350144e66e19b192...` (32 hex chars — needs full extraction from capture)

### Auth Flow
1. `POST https://cognito-idp.<region>.amazonaws.com/`
   - Target: `AWSCognitoIdentityProviderService.InitiateAuth`
   - Auth type: `USER_SRP_AUTH`
   - Returns a `PASSWORD_VERIFIER` challenge

2. `POST https://cognito-idp.<region>.amazonaws.com/`
   - Target: `AWSCognitoIdentityProviderService.RespondToAuthChallenge`
   - Completes SRP exchange
   - Returns `IdToken`, `AccessToken`, `RefreshToken`

3. `POST https://cognito-identity.<region>.amazonaws.com/`
   - Exchanges Cognito IdToken for temporary AWS credentials (`AccessKeyId`, `SecretKey`, `SessionToken`)
   - The returned Identity ID prefix determines which region the user belongs to
   - Credentials are used to SigV4-sign the IoT MQTT WebSocket URL

### Logout
- `POST cognito-idp` with target `RevokeToken`
- `POST <sns-api>/prod/sns-disable` (deregisters push notifications)

---

## REST API Endpoints Per Region

All endpoints are AWS API Gateway (`<id>.execute-api.<region>.amazonaws.com/prod`).
The path structure is identical across all regions — only the gateway ID differs.

### Endpoint IDs Per Region

| Purpose | eu-west-1 | us-east-2 | ap-southeast-2 | ap-east-1 |
|---------|-----------|-----------|----------------|-----------|
| Device list / validation | `asjqh5wbtj` | `zt810q0p60` | `vvikmtssjh` | `08ydw34dfj` |
| Device info & features | `6ghz1zkccg` | `6r8m5rxeth` | `7k2iuc99h7` | `m35t3px95i` |
| Firmware / OTA check | `eigc6a2ds9` | `453ahng0z4` | `2xipi98nw3` | `4gr97nlmga` |
| OTA job management | `io4nsakkt8` | `tvdfyh81d1` | `1sfa49lnl8` | `1h2q9awtqd` |
| Map | `3q1zxz98l2` | `bpath65iid` | `l2gobpcoqc` | `kdueg6qcwl` |
| Push notifications | `mu0adv3yse` | `suk4e76xe5` | `inflizu44a` | `i1pbnu30si` |
| WebSocket / misc | `eigc6a2ds9` | `6at3p6r6ce` | `19d2hfwavg` | `v2tsms5kll` |
| (unknown) | `frgai1jfwg` | `xuw7gtx113` | — | `t0da44vtxf` |
| (unknown) | `l3hazobjk0` | — | — | — |

### API Paths (same across all regions)

**Device List** (`device-list` gateway):
| Method | Path | Description |
|--------|------|-------------|
| POST | `/prod/check-app-force-update` | Checks if app update is required |
| GET | `/prod/device-list-query?p=validation` | Session keep-alive (polled frequently) |
| GET | `/prod/device-list-query?p=devices&identityId=<id>` | Lists all devices for the user |

**Device Info & Features** (`device-info` gateway):
| Method | Path | Description |
|--------|------|-------------|
| GET | `/prod/get-device-info?deviceThingName=<thing>` | Full device state (status, battery, error codes, etc.) |
| GET | `/prod/get-device-feature?deviceThingName=<thing>` | Device feature flags / capabilities |
| PATCH | `/prod/update-device-feature` | Update device feature settings |

**Firmware / OTA**:
| Method | Path | Description |
|--------|------|-------------|
| GET | `<ota-check>/prod/check-update?deviceThingName=<thing>` | Check for firmware update |
| GET | `<ota-job>/prod/create-ota-job?deviceThingName=<thing>&objectKey=<version>` | Trigger OTA update |
| GET | `<ota-job>/prod/get-ota-job-summary?deviceThingName=<thing>&jobId=<id>` | Poll OTA job status |

**Map**:
| Method | Path | Description |
|--------|------|-------------|
| GET | `/prod/get-backup-map?deviceThingName=<thing>` | Retrieve saved mowing map |

**Push Notifications**:
| Method | Path | Description |
|--------|------|-------------|
| POST | `/prod/sns-registration?p=Loading` | Register device for push notifications |
| POST | `/prod/sns-disable` | Deregister on logout |

### SIM Card (3rd party — region-independent)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `oapi.eiotclub.com/api/v3/card/getCardsInfo` | SIM card info |
| POST | `sim.eiotclub.com/eshop/api/refresh/card` | Refresh SIM data |

---

## Real-time Control — AWS IoT MQTT over WebSocket

**IoT endpoint (same host ID across all regions):** `a3j5zqqo5iuph9-ats.iot.<region>.amazonaws.com`

**Connection:** WebSocket upgrade to `/mqtt` with SigV4-signed query params:
- `X-Amz-Algorithm`: `AWS4-HMAC-SHA256`
- `X-Amz-Credential`: temporary Cognito identity credentials (rotated)
- `X-Amz-Date`, `X-Amz-SignedHeaders`, `X-Amz-Signature`, `X-Amz-Security-Token`

**Protocol:** MQTT 3.1.1 over WebSocket

**Device thing name format:** `device_<mac_without_colons>` (e.g. `device_7890838300cd`)

MQTT topics and message payloads not yet decoded — need capture of start/stop/park commands.

---

## Integration Architecture Plan

```
Config Flow
  └─ username + password + region selection (auto-detected from Identity ID)
       └─ Cognito SRP auth (region-local) → IdToken + RefreshToken
            └─ Cognito Identity → temp AWS creds + detect region

Coordinator (polling ~30s)
  └─ GET get-device-info → mower state

MQTT Client
  └─ AWS IoT WebSocket (SigV4, region-local, creds refreshed via Cognito Identity)
       └─ subscribe to device shadow / status topics
       └─ publish commands (start, stop, park)

Entities
  └─ lawn_mower (state: mowing / docked / paused / error)
  └─ sensor: battery level
  └─ sensor: error code
  └─ binary_sensor: connected
```

---

## Open Questions
- Full Cognito App Client IDs for all regions (partial eu-west-1 extracted: `c1e40b87...`)
- User Pool IDs for `us-east-2` (not found yet)
- MQTT topic names and message payloads for mower commands
- Exact JSON schema of `get-device-info` and `get-device-feature` responses
- Token refresh flow (AccessToken expiry, RefreshToken grant)
- Purpose of unknown API gateways (`frgai1jfwg`, `l3hazobjk0`, `xuw7gtx113`, `t0da44vtxf`)
