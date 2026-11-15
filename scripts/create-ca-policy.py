"""Create (or update) a report-only Conditional Access policy for Ava's agent identity:
block token issuance when the agent risk is medium or high. Report-only = evaluated and
logged in the sign-in logs, never enforced. Reads IDs from the git-ignored .env.

Usage: python -I scripts/create-ca-policy.py [--enforce]
Requires: az login as an admin of the M365 tenant (Conditional Access Administrator or higher).
"""
import json, os, subprocess, sys, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "Agent365 Demo - Ava: block on agent risk (report-only)"
STATE = "enabled" if "--enforce" in sys.argv else "enabledForReportingButNotEnforced"


def env():
    return dict(l.strip().split("=", 1) for l in open(os.path.join(ROOT, ".env"), encoding="utf-8")
                if "=" in l and not l.startswith("#"))


def token():
    return subprocess.check_output(["az", "account", "get-access-token", "--resource-type", "ms-graph",
                                    "--query", "accessToken", "-o", "tsv"], text=True, shell=os.name == "nt").strip()


def call(method, url, tok, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            t = r.read().decode()
            return r.status, json.loads(t) if t else {}
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def main():
    e, tok = env(), token()
    base = "https://graph.microsoft.com/beta/identity/conditionalAccess/policies"
    body = {
        "displayName": NAME,
        "state": STATE,
        "conditions": {
            "clientAppTypes": ["all"],
            "agentIdRiskLevels": "medium,high",
            "applications": {"includeApplications": ["All"]},
            "users": {"includeUsers": ["None"]},
            "clientApplications": {"includeServicePrincipals": [],
                                   "includeAgentIdServicePrincipals": [e["A365_AGENT_ID"]],
                                   "excludeServicePrincipals": []},
        },
        "grantControls": {"operator": "OR", "builtInControls": ["block"]},
    }
    st, res = call("GET", base + "?$select=id,displayName,state", tok)
    if st != 200:
        print("list policies failed:", st, res.get("error", {}).get("message")); sys.exit(1)
    existing = [p for p in res.get("value", []) if p["displayName"] == NAME]
    if existing:
        st, res = call("PATCH", f"{base}/{existing[0]['id']}", tok, body)
        print("update policy:", st, res.get("error", {}).get("message", "") if st >= 300 else STATE)
    else:
        st, res = call("POST", base, tok, body)
        print("create policy:", st, res.get("error", {}).get("message", "") if st >= 300 else f"{STATE} ({res['id'][:8]}…)")
    sys.exit(0 if st < 300 else 1)


if __name__ == "__main__":
    main()
