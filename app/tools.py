"""Mock telecom diagnostic tools for GPT-4o tool-calling."""

import random

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "check_line_quality",
            "description": (
                "Check real-time line quality and internet diagnostics for a customer account. "
                "Use when customer reports slow internet, disconnections, or unstable connection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer account number",
                    },
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_modem",
            "description": (
                "Send a remote restart command to the customer's modem/router. "
                "Use when basic troubleshooting hasn't resolved the issue."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer account number",
                    },
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_area_outage",
            "description": (
                "Check whether there is a known network outage in the customer's area. "
                "Use when customer reports complete internet outage or widespread issues."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer account number",
                    },
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_account",
            "description": (
                "Look up account details: subscription plan, billing status, data usage, "
                "open tickets. Use for billing questions or account-related inquiries."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer account number",
                    },
                },
                "required": ["account_id"],
            },
        },
    },
]

# Human-readable labels for tool names (shown in UI)
TOOL_LABELS = {
    "check_line_quality": {
        "nl": "Lijnkwaliteit controleren",
        "en": "Checking line quality",
    },
    "restart_modem": {"nl": "Modem herstarten", "en": "Restarting modem"},
    "check_area_outage": {"nl": "Storingen controleren", "en": "Checking area outages"},
    "lookup_account": {"nl": "Account opzoeken", "en": "Looking up account"},
}

TOOL_ICONS = {
    "check_line_quality": "📡",
    "restart_modem": "🔄",
    "check_area_outage": "🗺️",
    "lookup_account": "👤",
}


def execute_tool(name: str, args: dict, customer: dict) -> dict:
    """Execute a mock diagnostic tool and return realistic results."""
    account_id = customer.get("account_number", args.get("account_id", "TLN-000"))

    if name == "check_line_quality":
        notes = customer.get("notes", "").lower()
        has_issue = any(
            w in notes for w in ["probleem", "storing", "klacht", "issue", "fout"]
        )

        if has_issue:
            packet_loss = random.randint(8, 22)
            signal = random.choice(["matig", "zwak"])
            latency = random.randint(55, 140)
            down = round(random.uniform(5, 35), 1)
        else:
            packet_loss = random.randint(0, 2)
            signal = "uitstekend"
            latency = random.randint(6, 22)
            down = round(random.uniform(80, 300), 1)

        return {
            "account": account_id,
            "signaalsterkte": signal,
            "pakketverlies_pct": packet_loss,
            "latentie_ms": latency,
            "download_mbps": down,
            "upload_mbps": round(down * 0.25, 1),
            "laatste_verbreking": "2 uur geleden" if has_issue else "6 dagen geleden",
            "modem_status": "online",
            "firmware": "up-to-date",
        }

    elif name == "restart_modem":
        return {
            "account": account_id,
            "status": "herstart_verzonden",
            "eta_seconden": 90,
            "bericht": "Herstartcommando verzonden. Modem is ca. 90 seconden offline.",
        }

    elif name == "check_area_outage":
        # ~35% chance of area outage for demo realism
        has_outage = random.random() < 0.35
        if has_outage:
            return {
                "account": account_id,
                "storing_gedetecteerd": True,
                "getroffen_diensten": ["internet", "televisie"],
                "oorzaak": random.choice(
                    [
                        "Netwerkapparatuur defect",
                        "Gepland onderhoud",
                        "Kabelbreuk in de buurt",
                    ]
                ),
                "verwachte_herstel": (
                    f"{random.randint(14, 18)}:{random.choice(['00', '30'])} vandaag"
                ),
                "storingsnummer": f"STR-{random.randint(10000, 99999)}",
                "getroffen_adressen": random.randint(50, 800),
            }
        return {
            "account": account_id,
            "storing_gedetecteerd": False,
            "gebied_status": "Alle systemen normaal",
            "laatste_check": "1 minuut geleden",
        }

    elif name == "lookup_account":
        balance = customer.get("outstanding_balance", 0)
        return {
            "account": account_id,
            "naam": customer.get("name", "Onbekend"),
            "pakket": customer.get("plan_name", "Onbekend"),
            "status": customer.get("status", "actief"),
            "openstaand_bedrag_eur": balance,
            "laatste_factuur_eur": round(balance + random.uniform(30, 65), 2),
            "laatste_betaling": "01-06-2026",
            "contract_einddatum": "31-12-2026",
            "data_gebruik_gb": round(random.uniform(5, 80), 1),
            "data_limiet_gb": 100,
            "open_tickets": random.randint(0, 2),
            "laatste_contact": customer.get("last_support", "onbekend"),
        }

    return {"fout": f"Onbekende tool: {name}"}


def tool_label(name: str, language: str = "nl") -> str:
    entry = TOOL_LABELS.get(name, {})
    return entry.get(language, entry.get("nl", name))


def tool_icon(name: str) -> str:
    return TOOL_ICONS.get(name, "🔧")
