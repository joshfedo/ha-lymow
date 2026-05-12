# Lymow API — Reverse Engineering Notes

Captured via mitmproxy from the official Android app (v2.1.46).

## Authentication

Uses **AWS Amplify 6.15.5** with **AWS Cognito** in `eu-west-1`.

### Flow
1. `POST https://cognito-idp.eu-west-1.amazonaws.com/`
   - Target: `AWSCognitoIdentityProviderService.InitiateAuth`
   - Auth type: `USER_SRP_AUTH`
   - Returns a `PASSWORD_VERIFIER` challenge

2. `POST https://cognito-idp.eu-west-1.amazonaws.com/`
   - Target: `AWSCognitoIdentityProviderService.RespondToAuthChallenge`
   - Completes SRP exchange
   - Returns `IdToken`, `AccessToken`, `RefreshToken`

3. `POST https://cognito-identity.eu-west-1.amazonaws.com/`
   - Exchanges Cognito IdToken for temporary AWS credentials (`AccessKeyId`, `SecretKey`, `SessionToken`)
   - These are used to sign the IoT MQTT WebSocket URL (SigV4)

### Logout
- `POST cognito-idp` with target `RevokeToken`
- `POST mu0adv3yse.execute-api.eu-west-1.amazonaws.com/prod/sns-disable` (deregisters push notifications)

---

## REST API Endpoints

All REST endpoints are AWS API Gateway (`*.execute-api.eu-west-1.amazonaws.com`).
All require Cognito auth headers.

### App / Device List (`asjqh5wbtj`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/prod/check-app-force-update` | Checks if app update is required |
| GET | `/prod/device-list-query?p=validation` | Validates session / keep-alive (polled frequently) |
| GET | `/prod/device-list-query?p=devices&identityId=<id>` | Lists all devices for the user |

### Device Info & Features (`6ghz1zkccg`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/prod/get-device-info?deviceThingName=<thing>` | Full device state (status, battery, error codes, etc.) |
| GET | `/prod/get-device-feature?deviceThingName=<thing>` | Device feature flags / capabilities |
| PATCH | `/prod/update-device-feature` | Update device feature settings |

### Firmware / OTA (`eigc6a2ds9` + `io4nsakkt8`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `eigc6a2ds9/prod/check-update?deviceThingName=<thing>` | Check for firmware update |
| GET | `io4nsakkt8/prod/create-ota-job?deviceThingName=<thing>&objectKey=<version>` | Trigger OTA update |
| GET | `io4nsakkt8/prod/get-ota-job-summary?deviceThingName=<thing>&jobId=<id>` | Poll OTA job status |

### Map (`3q1zxz98l2`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/prod/get-backup-map?deviceThingName=<thing>` | Retrieve saved mowing map |

### Push Notifications (`mu0adv3yse`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/prod/sns-registration?p=Loading` | Register device for push notifications |
| POST | `/prod/sns-disable` | Deregister push notifications (on logout) |

### SIM Card (3rd party: `oapi.eiotclub.com`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v3/card/getCardsInfo` | SIM card info (connectivity, data usage) |
| POST | `sim.eiotclub.com/eshop/api/refresh/card` | Refresh SIM card data |

---

## Real-time Control — AWS IoT MQTT over WebSocket

The app maintains a persistent WebSocket to AWS IoT for real-time mower status and commands.

**Endpoint:** `a3j5zqqo5iuph9-ats.iot.eu-west-1.amazonaws.com`

**Connection:** WebSocket upgrade to `/mqtt` with SigV4 signed query params:
- `X-Amz-Algorithm`: `AWS4-HMAC-SHA256`
- `X-Amz-Credential`: temporary Cognito identity credentials
- `X-Amz-Date`, `X-Amz-SignedHeaders`, `X-Amz-Signature`, `X-Amz-Security-Token`

**Protocol:** MQTT 3.1.1 over WebSocket

**Device thing name format:** `device_<mac_without_colons>`

MQTT topics and message payloads are binary (not yet decoded — need further capture with mower commands).

---

## Integration Architecture Plan

```
Config Flow
  └─ username + password
       └─ Cognito SRP auth → IdToken + RefreshToken
            └─ Cognito Identity → temp AWS creds

Coordinator (polling, ~30s)
  └─ GET get-device-info → mower state

MQTT Client
  └─ AWS IoT WebSocket (SigV4 signed, refreshed from Cognito Identity)
       └─ subscribe to device shadow / status topics
       └─ publish commands (start, stop, park)

Entities
  └─ lawn_mower entity (state: mowing / docked / paused / error)
  └─ sensor: battery level
  └─ sensor: error code
  └─ binary_sensor: connected
```

---

## Open Questions
- MQTT topic names for device shadow / commands (need capture of start/stop/park actions)
- Exact JSON schema of `get-device-info` response (need to decode)
- Cognito User Pool ID and App Client ID (needed for SRP — extract from APK or capture)
- Token refresh flow (AccessToken expiry, RefreshToken usage)
