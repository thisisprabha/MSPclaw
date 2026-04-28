# MSPclaw Tool Implementation Guide

This document outlines what needs to be implemented for each tool placeholder to work with real systems.

---

## Table of Contents

1. [Account Management Tools](#account-management-tools)
2. [Software Management Tools](#software-management-tools)
3. [Email & Collaboration Tools](#email--collaboration-tools)
4. [Security Tools](#security-tools)
5. [Access Management Tools](#access-management-tools)
6. [Device Management Tools](#device-management-tools)
7. [Implementation Checklist](#implementation-checklist)

---

## Account Management Tools

### `reset_password(username, temporary_password)`

**What it does:** Reset a user's password in the company IdP.

**Systems to integrate:**

| System | API | Authentication |
|--------|-----|-----------------|
| **Active Directory (on-prem)** | PowerShell / LDAP | Service account with `Reset Password` permission |
| **Azure AD / Entra ID** | Microsoft Graph API | App registration + service principal |
| **Okta** | Okta API | API token |
| **Google Workspace** | Admin SDK / Directory API | Service account (JSON key) |

**Example Implementation (Azure AD):**

```python
# agent/tools/account_management.py

from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
import secrets

def reset_password(username: str, temporary_password: str | None = None) -> str:
    """Reset password in Azure AD."""
    
    # Generate temporary password if not provided
    if not temporary_password:
        temporary_password = secrets.token_urlsafe(16)
    
    # Authenticate to Azure AD
    credential = ClientSecretCredential(
        tenant_id=os.getenv("AZURE_TENANT_ID"),
        client_id=os.getenv("AZURE_CLIENT_ID"),
        client_secret=os.getenv("AZURE_CLIENT_SECRET"),
    )
    client = GraphClient(credential=credential)
    
    try:
        # Find user by UPN (username@company.com)
        user_upn = f"{username}@{os.getenv('COMPANY_DOMAIN')}"
        users = client.get(
            f"/users?$filter=userPrincipalName eq '{user_upn}'"
        ).json()
        
        if not users["value"]:
            return f"User not found: {username}"
        
        user_id = users["value"][0]["id"]
        
        # Reset password
        client.post(
            f"/users/{user_id}/changePassword",
            json={
                "currentPassword": "",  # MSPclaw agent doesn't know current
                "newPassword": temporary_password,
            },
        )
        
        return f"Password reset for {username}. Temporary: {temporary_password}"
        
    except Exception as e:
        return f"Password reset failed: {e}"
```

**Environment Variables Needed:**

```bash
# .env
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-app-id
AZURE_CLIENT_SECRET=your-secret
COMPANY_DOMAIN=company.com
```

**Setup Steps:**

1. Create an Azure AD app registration
2. Grant `Directory.ReadWrite.All` permission
3. Create a client secret
4. Store credentials in `.env`
5. Install dependencies: `pip install azure-identity msgraph-core`

---

### `unlock_user_account(username)`

**What it does:** Unlock a locked AD/Azure account.

**Systems to integrate:**

| System | Method |
|--------|--------|
| **Active Directory** | PowerShell: `Unlock-ADAccount` |
| **Azure AD** | Not applicable (cloud doesn't lock) |
| **Okta** | API: `POST /users/{userId}/lifecycle/unlock` |

**Example Implementation (Active Directory):**

```python
import subprocess

def unlock_user_account(username: str) -> str:
    """Unlock AD account via PowerShell."""
    
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-Command",
                f"Unlock-ADAccount -Identity {username}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            return f"Account {username} unlocked successfully."
        else:
            return f"Unlock failed: {result.stderr}"
            
    except Exception as e:
        return f"Error unlocking account: {e}"
```

---

### `check_account_status(username)`

**What it does:** Check if account is locked, disabled, or expired.

**Systems to integrate:**

| System | API |
|--------|-----|
| **Active Directory** | `Get-ADUser -Filter "samAccountName -eq 'user'"` (PowerShell) |
| **Azure AD** | Microsoft Graph: `/users/{id}?$select=accountEnabled,userPrincipalName` |
| **Okta** | API: `GET /users?search=profile.login eq "user@company.com"` |

**Example Implementation (Azure AD):**

```python
def check_account_status(username: str) -> str:
    """Check account status in Azure AD."""
    
    credential = ClientSecretCredential(
        tenant_id=os.getenv("AZURE_TENANT_ID"),
        client_id=os.getenv("AZURE_CLIENT_ID"),
        client_secret=os.getenv("AZURE_CLIENT_SECRET"),
    )
    client = GraphClient(credential=credential)
    
    try:
        user_upn = f"{username}@{os.getenv('COMPANY_DOMAIN')}"
        user = client.get(
            f"/users?$filter=userPrincipalName eq '{user_upn}'"
        ).json()
        
        if not user["value"]:
            return f"Account not found: {username}"
        
        u = user["value"][0]
        
        status = []
        status.append(f"User: {u['displayName']} ({u['userPrincipalName']})")
        status.append(f"Enabled: {u['accountEnabled']}")
        status.append(f"Last sign-in: {u.get('lastSignInDateTime', 'Never')}")
        
        return "\n".join(status)
        
    except Exception as e:
        return f"Status check failed: {e}"
```

---

### `list_user_groups(username)`

**What it does:** List all groups a user belongs to.

**Systems to integrate:**

| System | API |
|--------|-----|
| **Active Directory** | `Get-ADUser -Identity user \| Get-ADMembership` |
| **Azure AD** | Microsoft Graph: `/users/{id}/memberOf` |
| **Okta** | API: `GET /users/{id}/groups` |

**Example (Azure AD):**

```python
def list_user_groups(username: str) -> str:
    """List groups user belongs to in Azure AD."""
    
    credential = ClientSecretCredential(...)
    client = GraphClient(credential=credential)
    
    try:
        user_upn = f"{username}@{os.getenv('COMPANY_DOMAIN')}"
        user = client.get(
            f"/users?$filter=userPrincipalName eq '{user_upn}'"
        ).json()["value"][0]
        
        groups = client.get(f"/users/{user['id']}/memberOf").json()
        
        group_names = [g["displayName"] for g in groups["value"]]
        return "Groups:\n" + "\n".join(group_names)
        
    except Exception as e:
        return f"Failed to list groups: {e}"
```

---

## Software Management Tools

### `install_app(app_name)`

**What it does:** Deploy an approved application to a device.

**Systems to integrate:**

| System | Method | Use Case |
|--------|--------|----------|
| **Intune** | Assignments + Win32 apps | Windows/macOS cloud-managed |
| **Jamf Pro** | Policies + packages | macOS MDM |
| **SCCM** | Task sequences | Windows on-prem |
| **Brew** (macOS) | `brew install` | Developer tools |
| **Chocolatey** (Windows) | `choco install` | Windows tools |

**Example Implementation (Intune/Win32):**

```python
from msgraph.generated.models.win32_lob_app import Win32LobApp
from msgraph.core import GraphClient

def install_app(app_name: str) -> str:
    """Deploy app via Intune."""
    
    # Map app names to Intune app IDs
    APP_CATALOG = {
        "Google Chrome": "chrome-app-id-uuid",
        "Microsoft Office": "office-app-id-uuid",
        "Slack": "slack-app-id-uuid",
    }
    
    if app_name not in APP_CATALOG:
        return f"App not in catalog: {app_name}"
    
    app_id = APP_CATALOG[app_name]
    
    # In production, you'd:
    # 1. Create/update assignment for the device
    # 2. Trigger immediate sync
    # 3. Wait for result
    
    return f"Install initiated for {app_name} via Intune (app_id={app_id})"
```

**Setup Steps:**

1. Create app packages in Intune/MDM portal
2. Document app IDs and names
3. Create `APP_CATALOG` mapping
4. Authenticate with MDM provider API

---

### `list_updates_available()`

**What it does:** Check for OS and software updates.

**Systems to integrate:**

| OS | API |
|----|-----|
| **macOS** | `softwareupdate -l` (built-in) |
| **Windows** | Windows Update API or `wuauclt.exe` |
| **Linux** | `apt list --upgradable` or `yum check-update` |

**Example (Already Implemented):**

```python
def list_updates_available() -> str:
    """Check for available updates on macOS."""
    result = subprocess.run(
        ["softwareupdate", "-l"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout or "No updates available."
```

---

### `verify_license(app_name)`

**What it does:** Check if an app is properly licensed.

**Systems to integrate:**

| System | API |
|--------|-----|
| **Microsoft 365** | License assignment (Microsoft Graph) |
| **Adobe** | Admin console API |
| **Okta / SSO** | Check license metadata in token |

**Example (Microsoft 365):**

```python
def verify_license(app_name: str) -> str:
    """Check Microsoft 365 license status."""
    
    PRODUCT_SKUS = {
        "Microsoft Office": "O365_BUSINESS_PREMIUM",
        "Microsoft Teams": "TEAMS_COMMERCIAL_TRIAL",
    }
    
    sku = PRODUCT_SKUS.get(app_name)
    if not sku:
        return f"Unknown product: {app_name}"
    
    # Check if current user has license assignment
    # (Implementation would query Microsoft Graph)
    
    return f"License check for {app_name} (SKU: {sku}) — check Graph API"
```

---

## Email & Collaboration Tools

### `clear_email_cache(email_client)`

**What it does:** Clear cache of Outlook, Mail, or other email clients.

**Systems to integrate:**

| Client | Cache Location |
|--------|-----------------|
| **Outlook (macOS)** | `~/Library/Group Containers/UBF8T346G9.Office/` |
| **Outlook (Windows)** | `%APPDATA%\Microsoft\Outlook\` |
| **Mail (macOS)** | `~/Library/Mail Downloads/` |
| **Thunderbird** | `~/.thunderbird/` |

**Example (macOS):**

```python
import shutil
from pathlib import Path

def clear_email_cache(email_client: str) -> str:
    """Clear email client cache on macOS."""
    
    CACHE_PATHS = {
        "outlook": [
            Path.home() / "Library/Group Containers/UBF8T346G9.Office",
            Path.home() / "Library/Caches/com.microsoft.Outlook",
        ],
        "mail": [
            Path.home() / "Library/Mail Downloads",
            Path.home() / "Library/Caches/com.apple.Mail",
        ],
    }
    
    if email_client not in CACHE_PATHS:
        return f"Unknown client: {email_client}"
    
    try:
        for cache_path in CACHE_PATHS[email_client]:
            if cache_path.exists():
                shutil.rmtree(cache_path, ignore_errors=True)
        
        return f"Cache cleared for {email_client}"
    except Exception as e:
        return f"Error clearing cache: {e}"
```

---

### `search_quarantine(sender, subject)`

**What it does:** Search for quarantined emails in Exchange Online.

**Systems to integrate:**

| System | API |
|--------|-----|
| **Exchange Online** | Microsoft Graph: `/me/messages?$search="from:{sender}"` |
| **Proofpoint / Mimecast** | Email security API |

**Example (Exchange Online):**

```python
def search_quarantine(sender: str, subject: str | None = None) -> str:
    """Search quarantined messages in Exchange."""
    
    credential = ClientSecretCredential(...)
    client = GraphClient(credential=credential)
    
    try:
        # Search in user's Junk folder
        filter_str = f"from:{sender}"
        if subject:
            filter_str += f" AND subject:{subject}"
        
        messages = client.get(
            f"/me/messages?$search=\"{filter_str}\"&$filter=parentFolderId eq 'junkmailfolder'"
        ).json()
        
        count = len(messages["value"])
        return f"Found {count} quarantined message(s) from {sender}"
        
    except Exception as e:
        return f"Quarantine search failed: {e}"
```

---

### `release_from_quarantine(message_id)`

**What it does:** Release a message from spam/quarantine.

**Systems to integrate:**

| System | API |
|--------|-----|
| **Exchange Online** | Microsoft Graph: Move to Inbox |
| **Proofpoint / Mimecast** | Release API |

**Example (Exchange Online):**

```python
def release_from_quarantine(message_id: str) -> str:
    """Move message from Junk to Inbox."""
    
    credential = ClientSecretCredential(...)
    client = GraphClient(credential=credential)
    
    try:
        # Get Inbox folder ID
        folders = client.get("/me/mailFolders?$filter=displayName eq 'Inbox'").json()
        inbox_id = folders["value"][0]["id"]
        
        # Move message to Inbox
        client.post(
            f"/me/messages/{message_id}/move",
            json={"destinationId": inbox_id},
        )
        
        return f"Message {message_id} released to Inbox"
        
    except Exception as e:
        return f"Release failed: {e}"
```

---

### `verify_mfa_setup(username)`

**What it does:** Check if MFA is enabled and device is registered.

**Systems to integrate:**

| System | API |
|--------|-----|
| **Azure AD** | Microsoft Graph: `/users/{id}/authentication/methods` |
| **Okta** | API: `/users/{id}/factors` |

**Example (Azure AD):**

```python
def verify_mfa_setup(username: str) -> str:
    """Check MFA status in Azure AD."""
    
    credential = ClientSecretCredential(...)
    client = GraphClient(credential=credential)
    
    try:
        user_upn = f"{username}@{os.getenv('COMPANY_DOMAIN')}"
        user = client.get(
            f"/users?$filter=userPrincipalName eq '{user_upn}'"
        ).json()["value"][0]
        
        methods = client.get(
            f"/users/{user['id']}/authentication/methods"
        ).json()
        
        mfa_enabled = any(
            m["@odata.type"] in [
                "#microsoft.graph.phoneMethods",
                "#microsoft.graph.authenticatorAppMethods",
            ]
            for m in methods["value"]
        )
        
        return f"MFA enabled: {mfa_enabled}"
        
    except Exception as e:
        return f"MFA check failed: {e}"
```

---

## Security Tools

### `scan_for_malware()`

**What it does:** Run EDR/antivirus scan.

**Systems to integrate:**

| System | API |
|--------|-----|
| **Windows Defender / Intune** | Microsoft Graph: Trigger scan |
| **CrowdStrike** | Falcon API: `POST /detects-entities-query` |
| **Sentinel One** | Management API: Trigger scan |
| **macOS** | `/usr/local/bin/MalwareBytes` CLI |

**Example (Windows Defender / Intune):**

```python
def scan_for_malware() -> str:
    """Trigger Windows Defender scan via Intune."""
    
    # In production, you would:
    # 1. Get current device ID
    # 2. Send action to Intune: triggerFullScan
    # 3. Return status
    
    return "Malware scan initiated — monitor Intune console for results"
```

---

### `check_url_reputation(url)`

**What it does:** Check if a URL is malicious.

**Systems to integrate:**

| System | API |
|--------|-----|
| **VirusTotal** | Free API (rate-limited) |
| **URLhaus** | Free API |
| **Microsoft Defender** | Threat Intelligence API |
| **Cisco Umbrella** | Investigate API |

**Example (VirusTotal):**

```python
import requests

def check_url_reputation(url: str) -> str:
    """Check URL reputation on VirusTotal."""
    
    VT_API_KEY = os.getenv("VIRUSTOTAL_API_KEY")
    
    try:
        response = requests.post(
            "https://www.virustotal.com/api/v3/urls",
            headers={"x-apikey": VT_API_KEY},
            data={"url": url},
            timeout=30,
        )
        
        url_id = response.json()["data"]["id"]
        
        # Get analysis results
        analysis = requests.get(
            f"https://www.virustotal.com/api/v3/urls/{url_id}",
            headers={"x-apikey": VT_API_KEY},
        ).json()
        
        stats = analysis["data"]["attributes"]["last_analysis_stats"]
        
        if stats["malicious"] > 0:
            return f"🚨 MALICIOUS: {stats['malicious']} vendors flagged this URL"
        elif stats["suspicious"] > 0:
            return f"⚠️  SUSPICIOUS: {stats['suspicious']} vendors marked as suspicious"
        else:
            return f"✅ SAFE: No threats detected"
            
    except Exception as e:
        return f"URL check failed: {e}"
```

---

### `invalidate_sessions(username)`

**What it does:** Force all sessions to end (sign user out everywhere).

**Systems to integrate:**

| System | API |
|--------|-----|
| **Azure AD** | Microsoft Graph: `/users/{id}/revokeSignInSessions` |
| **Okta** | API: `DELETE /users/{id}/sessions` |

**Example (Azure AD):**

```python
def invalidate_sessions(username: str) -> str:
    """Revoke all sessions for a user in Azure AD."""
    
    credential = ClientSecretCredential(...)
    client = GraphClient(credential=credential)
    
    try:
        user_upn = f"{username}@{os.getenv('COMPANY_DOMAIN')}"
        user = client.get(
            f"/users?$filter=userPrincipalName eq '{user_upn}'"
        ).json()["value"][0]
        
        client.post(f"/users/{user['id']}/revokeSignInSessions")
        
        return f"All sessions revoked for {username}"
        
    except Exception as e:
        return f"Session revocation failed: {e}"
```

---

## Access Management Tools

### `grant_access(username, resource_name, access_level)`

**What it does:** Add user to a group or assign access to a resource.

**Systems to integrate:**

| System | API |
|--------|-----|
| **Active Directory** | `Add-ADGroupMember` (PowerShell) |
| **Azure AD** | Microsoft Graph: `/groups/{id}/members/$ref` |
| **SharePoint** | Site permissions API |
| **Google Workspace** | Directory API |

**Example (Azure AD):**

```python
def grant_access(username: str, resource_name: str, access_level: str = "read") -> str:
    """Add user to a group in Azure AD."""
    
    credential = ClientSecretCredential(...)
    client = GraphClient(credential=credential)
    
    # Map resource_name to group ID
    RESOURCE_TO_GROUP = {
        "Finance Folder": "group-uuid-123",
        "HR System": "group-uuid-456",
    }
    
    group_id = RESOURCE_TO_GROUP.get(resource_name)
    if not group_id:
        return f"Resource not found: {resource_name}"
    
    try:
        user_upn = f"{username}@{os.getenv('COMPANY_DOMAIN')}"
        user = client.get(
            f"/users?$filter=userPrincipalName eq '{user_upn}'"
        ).json()["value"][0]
        
        client.post(
            f"/groups/{group_id}/members/$ref",
            json={"@odata.id": f"https://graph.microsoft.com/v1.0/users/{user['id']}"},
        )
        
        return f"Access granted: {username} → {resource_name} ({access_level})"
        
    except Exception as e:
        return f"Grant failed: {e}"
```

---

### `revoke_access(username, resource_name)`

**What it does:** Remove user from a group.

**Systems to integrate:**

| System | API |
|--------|-----|
| **Active Directory** | `Remove-ADGroupMember` |
| **Azure AD** | Microsoft Graph: `DELETE /groups/{id}/members/{user_id}/$ref` |

---

## Device Management Tools

### `enroll_in_mdm(device_identifier)`

**What it does:** Enroll device in Mobile Device Management.

**Systems to integrate:**

| System | Method |
|--------|--------|
| **Intune** | Device Enrollment: AutoPilot or enrollment link |
| **Jamf Pro** | Jamf Enrollment: PreStage enrollments |
| **Workspace One** | UEM enrollment |

**Example (Jamf Pro):**

```python
import requests

def enroll_in_mdm(device_identifier: str) -> str:
    """Enroll device in Jamf Pro."""
    
    JAMF_URL = os.getenv("JAMF_URL")
    JAMF_USER = os.getenv("JAMF_USER")
    JAMF_PASS = os.getenv("JAMF_PASS")
    
    try:
        # Get device ID
        response = requests.get(
            f"{JAMF_URL}/JSSResource/computers/identifier/{device_identifier}",
            auth=(JAMF_USER, JAMF_PASS),
        )
        device_id = response.json()["computer"]["general"]["id"]
        
        # Trigger MDM enrollment profile
        requests.post(
            f"{JAMF_URL}/JSSResource/computercommands/command/EnableRemoteDesktop/id/{device_id}",
            auth=(JAMF_USER, JAMF_PASS),
        )
        
        return f"MDM enrollment initiated for {device_identifier}"
        
    except Exception as e:
        return f"Enrollment failed: {e}"
```

---

### `check_device_encryption()`

**What it does:** Verify device is encrypted (FileVault, BitLocker).

**Systems to integrate:**

| OS | API |
|----|-----|
| **macOS** | `diskutil info /` (already implemented) |
| **Windows** | `manage-bde.exe` or WMI |

---

### `enable_firewall()`

**What it does:** Enable system firewall.

**Systems to integrate:**

| OS | Command |
|----|---------|
| **macOS** | `defaults write` (already implemented) |
| **Windows** | `netsh advfirewall` |

---

## Implementation Checklist

Use this to track what's implemented:

```
ACCOUNT MANAGEMENT
☐ reset_password() — Integrate with IdP (AD/Azure/Okta/GSuite)
☐ unlock_user_account() — PowerShell/API call
☐ disable_user_account() — Offboarding flow
☐ check_account_status() — Directory query
☐ list_user_groups() — Group membership query

SOFTWARE MANAGEMENT
☐ install_app() — Intune/Jamf/SCCM API
☐ uninstall_app() — MDM uninstall
☐ list_updates_available() — OS update check (partly done)
☐ install_brew_package() — Homebrew (done)
☐ verify_license() — License check API

EMAIL & COLLABORATION
☐ clear_email_cache() — Client-side cache (done for macOS)
☐ check_mailbox_size() — Exchange API
☐ search_quarantine() — Exchange spam folder
☐ release_from_quarantine() — Move message
☐ check_smtp_settings() — Email client validation
☐ verify_mfa_setup() — IdP MFA check

SECURITY
☐ scan_for_malware() — EDR/AV API
☐ check_url_reputation() — VirusTotal/URLhaus
☐ check_email_headers() — Email analysis
☐ invalidate_sessions() — Session revocation
☐ revoke_tokens() — Token revocation
☐ check_endpoint_posture() — Compliance check
☐ quarantine_suspicious_files() — Quarantine API

ACCESS MANAGEMENT
☐ grant_access() — Group membership
☐ revoke_access() — Remove from group
☐ check_resource_access() — Permission check
☐ add_to_group() — Directory API
☐ remove_from_group() — Directory API
☐ set_access_expiration() — Temporary access

DEVICE MANAGEMENT
☐ enroll_in_mdm() — MDM enrollment API
☐ unenroll_from_mdm() — Unenrollment
☐ remote_wipe_device() — Destructive wipe
☐ check_device_encryption() — macOS (done)
☐ enable_firewall() — macOS (done)
☐ check_firewall_status() — macOS (done)
```

---

## Priority Implementation Order

### Phase 1 (MVP) — **Account Management**
Focus on password reset and account unlock (90% of support tickets).

1. Implement `reset_password()` for your IdP
2. Implement `check_account_status()`
3. Implement `unlock_user_account()`

### Phase 2 — **Access Management**
Grant/revoke access to shared resources.

1. Implement `grant_access()`
2. Implement `add_to_group()`
3. Implement `check_resource_access()`

### Phase 3 — **Email Tools**
Email-specific issues (quarantine, MFA).

1. Implement `search_quarantine()`
2. Implement `release_from_quarantine()`
3. Implement `verify_mfa_setup()`

### Phase 4 — **Security & Device**
Advanced security and device management.

1. Implement `invalidate_sessions()`
2. Implement `scan_for_malware()`
3. Implement `enroll_in_mdm()`

---

## Environment Variables Template

Create a `.env` file in the root directory:

```bash
# IDENTITY PROVIDER
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
COMPANY_DOMAIN=company.com

# Alternative IdPs
OKTA_ORG_URL=https://company.okta.com
OKTA_API_TOKEN=

AD_SERVER=192.168.1.10
AD_USERNAME=svc_mspclaw
AD_PASSWORD=

GOOGLE_SERVICE_ACCOUNT_JSON=./google-service-account.json

# EMAIL
EXCHANGE_TENANT_ID=
OFFICE365_CLIENT_ID=
OFFICE365_CLIENT_SECRET=

# MDM
JAMF_URL=https://company.jamf.com
JAMF_USER=
JAMF_PASS=

INTUNE_TENANT_ID=
INTUNE_CLIENT_ID=
INTUNE_CLIENT_SECRET=

# SECURITY
VIRUSTOTAL_API_KEY=
CROWDSTRIKE_CLIENT_ID=
CROWDSTRIKE_CLIENT_SECRET=
```

---

## Testing Tools Locally

Before deploying, test each tool:

```bash
# Test account tools
python3 -c "from agent.tools.account_management import check_account_status; print(check_account_status('testuser'))"

# Test security tools
python3 -c "from agent.tools.security_remediation import check_url_reputation; print(check_url_reputation('https://example.com'))"

# Test device tools
python3 -c "from agent.tools.device_management import check_device_encryption; print(check_device_encryption())"
```

---

## Dependencies by Phase

```bash
# Phase 1
pip install azure-identity msgraph-core python-ldap

# Phase 2
pip install okta

# Phase 3
pip install exchangelib

# Phase 4
pip install requests crowdstrike-falconpy
```

---

## Next Steps

1. Choose your primary IdP (Azure AD / Active Directory / Okta)
2. Create service accounts with appropriate permissions
3. Implement Phase 1 tools (password reset)
4. Test with a small group of users
5. Roll out by phase as tools stabilize
