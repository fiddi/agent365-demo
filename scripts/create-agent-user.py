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
        # The UPN must belong to *this* agent identity, not to an older identity or an ordinary user.
        if not DRY and u.get("identityParentId") != ai.get("id"):
            print(f"ABORT: {upn} exists but is not the agent user of identity {short(ai.get('id'))} "
                  f"(identityParentId={short(u.get('identityParentId')) or 'none'}).")
            sys.exit(1)
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

    # 3) Delegated consent for the agent identity: mirror the blueprint's admin grants
    #    (the admin center's "Accept permissions" step normally does this).
    #    Only tenant-wide (AllPrincipals) admin grants are mirrored; user-specific (Principal)
    #    grants are never expanded to tenant-wide consent. Any failed read/write aborts before .env is touched.
    def must(st, res, what):
        if st >= 300:
            print(f"ABORT: {what} failed ({st}): {res.get('error', {}).get('message', '')}")
            sys.exit(1)
        return res

    def admin_grants(client_id):
        url = f"https://graph.microsoft.com/v1.0/oauth2PermissionGrants?$filter=clientId eq '{client_id}' and consentType eq 'AllPrincipals'"
        st, res = http("GET", url.replace(" ", "%20"), adm)
        return [g for g in must(st, res, "read consent grants").get("value", []) if g.get("consentType") == "AllPrincipals"]

    if not DRY:
        st, bpsp = http("GET", f"https://graph.microsoft.com/v1.0/servicePrincipals(appId='{blueprint}')?$select=id", adm)
        must(st, bpsp, "read blueprint service principal")
        bpg, aig = admin_grants(bpsp["id"]), admin_grants(ai["id"])
        have = {g["resourceId"] for g in aig}
        wanted = {g["resourceId"]: g["scope"].strip() for g in bpg}
        # Work IQ MCP servers (public Microsoft app IDs: Mail, OneDrive, SharePoint) all need
        # Tools.ListInvoke.All – the blueprint's Mail grant only has McpServers.Mail.All.
        for app in ("ea9ffc3e-8a23-4a7d-836d-234d7c7565c1", "b0b2a2bb-6361-4549-a00c-a018417eb8e2",
                    "292cff14-c0e8-4116-9e3b-99934ae05766"):
            st, sp = http("GET", f"https://graph.microsoft.com/v1.0/servicePrincipals(appId='{app}')?$select=id", adm)
            must(st, sp, f"read MCP service principal {app[:8]}")
            scopes = set(wanted.get(sp["id"], "").split()) | {"Tools.ListInvoke.All"}
            wanted[sp["id"]] = " ".join(sorted(scopes))
        # The Agents SDK also requests Graph User.Read for the agent user (blueprint grant has only User.Read.All).
        st, graph = http("GET", "https://graph.microsoft.com/v1.0/servicePrincipals(appId='00000003-0000-0000-c000-000000000000')?$select=id", adm)
        must(st, graph, "read Microsoft Graph service principal")
        wanted[graph["id"]] = " ".join(sorted(set(wanted.get(graph["id"], "").split()) | {"User.Read"}))
        for g in aig:
            missing = set(wanted.get(g["resourceId"], "").split()) - set(g["scope"].split())
            if missing:
                st, res = http("PATCH", f"https://graph.microsoft.com/v1.0/oauth2PermissionGrants/{g['id']}", adm,
                               {"scope": " ".join(sorted(set(g["scope"].split()) | missing))})
                must(st, res, f"update grant {short(g['resourceId'])}")
                print("grant update", short(g["resourceId"]), st)
        for rid, scope in wanted.items():
            if rid in have: continue
            st, res = http("POST", "https://graph.microsoft.com/v1.0/oauth2PermissionGrants", adm,
                           {"clientId": ai["id"], "consentType": "AllPrincipals", "resourceId": rid, "scope": scope})
            must(st, res, f"create grant {short(rid)}")
            print("grant", short(rid), st)

    # 4) Licenses (assign manually or extend here):
    #    AGENT_365, Office 365 E5 (no Teams), M365 Copilot – see docs/plan.md Phase 4.

    # write the agent identity id into .env for later steps
    if not DRY and ai.get("id") and env.get("A365_AGENT_ID") != ai["id"]:
        lines = open(os.path.join(ROOT, ".env"), encoding="utf-8").read().splitlines()
        lines = [l for l in lines if not l.startswith("A365_AGENT_ID=")] + [f"A365_AGENT_ID={ai['id']}"]
        open(os.path.join(ROOT, ".env"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print("A365_AGENT_ID updated in .env")


if __name__ == "__main__":
    main()
