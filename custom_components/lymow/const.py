from __future__ import annotations

DOMAIN = "lymow"

# Cognito — App Client ID is shared across all regions
COGNITO_CLIENT_ID = "3h1sqv3hishjiofbv8giskjgb0"

# Per-region AWS config. Key = Cognito identity pool region prefix.
REGION_CONFIG: dict[str, dict[str, str | None]] = {
    "eu-west-1": {
        "user_pool_id": "eu-west-1_6qNPbnrrd",
        "identity_pool_id": "eu-west-1:c905a69c-0153-401a-a879-0c50b892015b",
        "api_device_list":  "asjqh5wbtj",
        "api_device_info":  "6ghz1zkccg",
        "api_ota_check":    "eigc6a2ds9",
        "api_map":          "3q1zxz98l2",
    },
    "us-east-2": {
        "user_pool_id": None,  # not yet extracted
        "identity_pool_id": "us-east-2:037db699-5df0-4ed2-92b8-0dd0f1843918",
        "api_device_list":  "zt810q0p60",
        "api_device_info":  "6r8m5rxeth",
        "api_ota_check":    "453ahng0z4",
        "api_map":          "bpath65iid",
    },
    "ap-southeast-2": {
        "user_pool_id": "ap-southeast-2_vNriuUNeQ",
        "identity_pool_id": "ap-southeast-2:87d0fe24-16af-4189-b02f-984a7ed14ee0",
        "api_device_list":  "vvikmtssjh",
        "api_device_info":  "7k2iuc99h7",
        "api_ota_check":    "2xipi98nw3",
        "api_map":          "l2gobpcoqc",
    },
    "ap-east-1": {
        "user_pool_id": "ap-east-1_23Lf1WZer",
        "identity_pool_id": "ap-east-1:3e9265aa-f564-4083-8e1e-988e6cfdc446",
        "api_device_list":  "08ydw34dfj",
        "api_device_info":  "m35t3px95i",
        "api_ota_check":    "4gr97nlmga",
        "api_map":          "kdueg6qcwl",
    },
}

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# How often to poll device state
POLLING_INTERVAL = 30  # seconds
