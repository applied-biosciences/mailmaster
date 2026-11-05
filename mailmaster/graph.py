"""Thin wrapper around the Microsoft Graph mail API."""
import time
from urllib.parse import quote
import requests

GRAPH = "https://graph.microsoft.com/v1.0"
SELECT = ("id,subject,from,receivedDateTime,bodyPreview,isRead,importance,"
          "inferenceClassification,internetMessageHeaders,flag,webLink")


class GraphError(Exception):
    pass


def _request(method, url, token, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    for attempt in range(5):
        r = requests.request(method, url, headers=headers, timeout=60, **kwargs)
        if r.status_code == 429 or r.status_code >= 500:  # throttled / transient
            time.sleep(int(r.headers.get("Retry-After", 2 ** attempt)))
            continue
        if r.status_code >= 400:
            raise GraphError(f"{r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}
    raise GraphError("Microsoft Graph kept throttling the request, try again shortly.")


def get_me(token):
    return _request("GET", f"{GRAPH}/me?$select=displayName,mail,userPrincipalName", token)


def list_messages(token, folder, limit):
    """folder: 'inbox', 'junkemail' or 'deleteditems'. limit=None loads every email in the folder."""
    url = f"{GRAPH}/me/mailFolders/{folder}/messages"
    page = 200 if limit is None else min(200, limit)
    params = {"$select": SELECT, "$top": page, "$orderby": "receivedDateTime desc"}
    out = []
    while url and (limit is None or len(out) < limit):
        data = _request("GET", url, token, params=params)
        out.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
        params = None  # nextLink already contains the query
    return out if limit is None else out[:limit]


def delete_messages(token, ids, permanent=False):
    """Deletes in JSON batches of 20. Normal delete moves to Deleted Items."""
    deleted, failed = [], []
    for i in range(0, len(ids), 20):
        chunk = ids[i:i + 20]
        reqs = []
        for n, mid in enumerate(chunk):
            path = f"/me/messages/{quote(mid, safe='')}"
            if permanent:
                reqs.append({"id": str(n), "method": "POST", "url": path + "/permanentDelete",
                             "headers": {"Content-Type": "application/json"}, "body": {}})
            else:
                reqs.append({"id": str(n), "method": "DELETE", "url": path})
        res = _request("POST", f"{GRAPH}/$batch", token, json={"requests": reqs})
        for item in res.get("responses", []):
            mid = chunk[int(item["id"])]
            (deleted if item.get("status", 500) < 300 else failed).append(mid)
    return deleted, failed


def send_mail(token, to, subject, body):
    payload = {"message": {"subject": subject or "unsubscribe",
                           "body": {"contentType": "Text", "content": body or "unsubscribe"},
                           "toRecipients": [{"emailAddress": {"address": to}}]},
               "saveToSentItems": False}
    _request("POST", f"{GRAPH}/me/sendMail", token, json=payload)
