"""Microsoft sign-in (MSAL) for Outlook.com / Hotmail / Microsoft 365 accounts.
Supports several Microsoft accounts. Tokens are cached in token_cache.json on your machine only."""
import os
import config


def _load_cache():
    import msal
    cache = msal.SerializableTokenCache()
    if os.path.exists(config.TOKEN_CACHE_FILE):
        with open(config.TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            cache.deserialize(f.read())
    return cache


def _save_cache(cache):
    if cache.has_state_changed:
        with open(config.TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(cache.serialize())


def _app(cache=None):
    import msal
    if config.CLIENT_SECRET:
        return msal.ConfidentialClientApplication(
            config.CLIENT_ID, authority=config.AUTHORITY,
            client_credential=config.CLIENT_SECRET, token_cache=cache)
    return msal.PublicClientApplication(config.CLIENT_ID, authority=config.AUTHORITY, token_cache=cache)


def start_login():
    return _app().initiate_auth_code_flow(
        config.SCOPES, redirect_uri=config.REDIRECT_URI, prompt="select_account")


def finish_login(flow, query_args):
    """Returns (account_info, error). account_info = {home_account_id, username, name}."""
    cache = _load_cache()
    app = _app(cache)
    result = app.acquire_token_by_auth_code_flow(flow, query_args)
    _save_cache(cache)
    if "error" in result:
        return None, f"{result.get('error')}: {result.get('error_description')}"
    claims = result.get("id_token_claims", {})
    username = claims.get("preferred_username") or claims.get("email") or ""
    matches = app.get_accounts(username=username) or app.get_accounts()
    if not matches:
        return None, "Signed in, but the account was not found in the token cache."
    return {"home_account_id": matches[0]["home_account_id"], "username": username,
            "name": claims.get("name") or username}, None


def _find(app, home_account_id):
    return next((a for a in app.get_accounts() if a["home_account_id"] == home_account_id), None)


def get_token(home_account_id):
    if not os.path.exists(config.TOKEN_CACHE_FILE):
        return None
    cache = _load_cache()
    app = _app(cache)
    acc = _find(app, home_account_id)
    if not acc:
        return None
    result = app.acquire_token_silent(config.SCOPES, account=acc)
    _save_cache(cache)
    return result.get("access_token") if result else None


def remove(home_account_id):
    if not os.path.exists(config.TOKEN_CACHE_FILE):
        return
    cache = _load_cache()
    app = _app(cache)
    acc = _find(app, home_account_id)
    if acc:
        app.remove_account(acc)
    _save_cache(cache)
