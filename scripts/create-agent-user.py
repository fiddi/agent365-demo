"""Create Ava's agent identity and agent user via Microsoft Graph (workaround when the
M365 admin center activation is blocked). Reads IDs/secrets only from git-ignored local files
and never prints them.

Usage: python -I scripts/create-agent-user.py [--dry-run]
Requires: az login with an admin of the M365 tenant (default account = M365 tenant subscription).
"""
import json, os, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry-run" in sys.argv


def load_env():
    env = {}
    for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    return env


def http(method, url, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt else {})
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def blueprint_token(tenant, client_id, secret):
    data = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": client_id,
                                   "client_secret": secret, "scope": "https://graph.microsoft.com/.default"}).encode()
    with urllib.request.urlopen(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", data) as r:
        return json.loads(r.read())["access_token"]


def admin_token():
    return subprocess.check_output(["az", "account", "get-access-token", "--resource-type", "ms-graph",
                                    "--query", "accessToken", "-o", "tsv"], text=True, shell=os.name == "nt").strip()


def short(x):
    return (x or "")[:8] + "…"


def main():
    env = load_env()
    tenant, blueprint = env["A365_TENANT_ID"], env["A365_BLUEPRINT_ID"]
    upn, name = env.get("AGENT_UPN") or "ava@fiddi.ch", env.get("AGENT_DISPLAY_NAME") or "Ava"
    dev = json.load(open(os.path.join(ROOT, "src/DemoAgent/appsettings.Development.json"), encoding="utf-8"))
    secret = dev["Connections"]["ServiceConnection"]["Settings"]["ClientSecret"]

    adm = admin_token()
    st, me = http("GET", "https://graph.microsoft.com/v1.0/me?$select=id,userPrincipalName", adm)
    assert st == 200, me
    print("admin:", me["userPrincipalName"])

    bp = blueprint_token(tenant, blueprint, secret)

    # 1) Agent identity (idempotent: reuse by display name under this blueprint)
    flt = urllib.parse.quote(f"displayName eq '{name}'")
    st, res = http("GET", f"https://graph.microsoft.com/beta/servicePrincipals/microsoft.graph.agentIdentity?$filter={flt}", adm)
    existing = [s for s in res.get("value", []) if s.get("agentIdentityBlueprintId") == blueprint]
    if existing:
        ai = existing[0]
        print("agent identity exists:", short(ai["id"]))
    elif DRY:
        print("DRY: would create agent identity", name); ai = {"id": "<new>"}
    else:
        st, ai = http("POST", "https://graph.microsoft.com/v1.0/servicePrincipals/microsoft.graph.agentIdentity", bp, {
            "displayName": name,
            "agentIdentityBlueprintId": blueprint,
            "sponsors@odata.bind": [f"https://graph.microsoft.com/v1.0/users/{me['id']}"],
        })
        print("create agent identity:", st, short(ai.get("id")) if st < 300 else ai)
        if st >= 300: sys.exit(1)

    # 2) Agent user
    st, u = http("GET", f"https://graph.microsoft.com/beta/users/{urllib.parse.quote(upn)}?$select=id,userPrincipalName,identityParentId", adm)
    if st == 200:
        print("agent user exists:", u["userPrincipalName"])
    elif DRY:
        print("DRY: would create agent user", upn); u = None
    else:
        body = {"@odata.type": "microsoft.graph.agentUser", "displayName": name, "userPrincipalName": upn,
                "mailNickname": upn.split("@")[0], "identityParentId": ai["id"], "accountEnabled": True,
                "usageLocation": "CH"}
        st, u = http("POST", "https://graph.microsoft.com/beta/users", bp, body)
        if st >= 300:
            print("create agent user with blueprint token:", st, u.get("error", {}).get("message"))
            st, u = http("POST", "https://graph.microsoft.com/beta/users", adm, body)
        print("create agent user:", st, u.get("userPrincipalName") if st < 300 else u)
        if st >= 300: sys.exit(1)

    # write the agent identity id into .env for later steps
    if not DRY and ai.get("id") and env.get("A365_AGENT_ID") != ai["id"]:
        lines = open(os.path.join(ROOT, ".env"), encoding="utf-8").read().splitlines()
        lines = [l for l in lines if not l.startswith("A365_AGENT_ID=")] + [f"A365_AGENT_ID={ai['id']}"]
        open(os.path.join(ROOT, ".env"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print("A365_AGENT_ID updated in .env")


if __name__ == "__main__":
    main()
