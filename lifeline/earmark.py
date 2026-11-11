"""Optional "help a specific family" earmark.

The note is untrusted plain text. It never reaches the judge and never changes a verdict.
It is cleaned (control chars, markup, links removed), checked with the same prompt-injection
detector the appeals go through, and stripped of phone numbers, emails and street addresses
before it is stored anywhere (payout note, receipt, trace). It is a request to the charity,
not a guarantee: Lifeline never pays individuals directly.
"""
import re
import unicodedata
from urllib.parse import urlsplit

from . import agents

MAX_NOTE = 200
MAX_FAMILY = 80

_URL = re.compile(r"(?i)\b(?:https?://|ftp://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|org|net|io|co|ly|me|info|biz|xyz|gov|edu|us|app|link|gl)(?:/\S*)?\b")
_EMAIL = re.compile(r"(?i)\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)")
_STREET = re.compile(
    r"(?i)\b\d{1,6}\s+(?:[A-Za-z0-9.'-]+\s+){0,4}?"
    r"(?:street|st|avenue|ave|road|rd|lane|ln|drive|dr|boulevard|blvd|court|ct|way|place|pl|highway|hwy|"
    r"parkway|pkwy|circle|cir|terrace|trail|trl)\b\.?(?:\s*(?:apt|unit|#)\s*\w+)?")
_INVISIBLE = re.compile(r"[​-‏⁠‪-‮﻿]")

_IDNUM = re.compile(r"(?<!\w)(?:\d{3}-\d{2}-\d{4}|\d[\d -]{6,}\d)(?!\w)")  # SSN-style or 8+ digit runs
BAD_NOTE = ("Please leave out phone numbers, email addresses, street addresses and ID numbers. "
            "The charity contacts the family through its own channels.")


class NoteRejected(ValueError):
    pass


def personal_details(text):
    t = str(text or "")
    return [k for k, rx in (("email", _EMAIL), ("phone", _PHONE), ("address", _STREET), ("id number", _IDNUM)) if rx.search(t)]


ETHICS = ("The charity checks on the family first and decides how best to help. "
          "Lifeline never pays individuals directly.")


def _plain(text, limit):
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = "".join(ch if ch.isprintable() or ch == " " else " " for ch in text)
    text = re.sub(r"<[^>]*>", " ", text)          # drop markup
    text = text.replace("<", " ").replace(">", " ")
    return re.sub(r"\s+", " ", text).strip()[:limit * 2]


def redact(text):
    """Remove contact details before anything is stored or logged."""
    text = _EMAIL.sub("[email removed]", text)
    text = _URL.sub("[link removed]", text)
    text = _PHONE.sub("[phone removed]", text)
    text = _STREET.sub("[address removed]", text)
    return re.sub(r"\s+", " ", text).strip()


ALLOWED_HOSTS = ("x.com", "twitter.com", "instagram.com", "facebook.com", "threads.net")
BAD_LINK = ("That link can't be used. Please paste an https link to the original post on "
            "X, Twitter, Instagram, Facebook or Threads, or leave the field empty.")


class LinkRejected(ValueError):
    pass


def post_link(url):
    """Only https links to the original social post. Returns a normalised plain-text link or None."""
    url = _INVISIBLE.sub("", str(url or "")).strip()
    if not url:
        return None
    if len(url) > 300 or any(c.isspace() or c in "<>\"'`\\" for c in url):
        raise LinkRejected(BAD_LINK)
    try:
        u = urlsplit(url)
        host = (u.hostname or "").lower()
        port = u.port
    except ValueError:
        raise LinkRejected(BAD_LINK)
    if u.scheme != "https" or u.username or u.password or port not in (None, 443) or \
            not any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS):
        raise LinkRejected(BAD_LINK)
    path = re.sub(r"[^A-Za-z0-9/_.~%@-]", "", u.path)[:200]
    return f"https://{host}{path}"


def clean(family=None, note=None, link=None):
    """Returns None when nothing was given, otherwise a dict safe to store, log and hash."""
    raw_f, raw_n = _plain(family, MAX_FAMILY), _plain(note, MAX_NOTE)
    link = post_link(link)  # raises LinkRejected
    if personal_details(f"{family or ''} {note or ''}"):
        raise NoteRejected(BAD_NOTE)
    if not raw_f and not raw_n and not link:
        return None
    hits = agents.detect_injection(f"{family or ''}\n{note or ''}")
    if hits:
        return {"status": "DROPPED", "reason": "PROMPT_INJECTION", "family": None, "note": None, "post_link": None}
    f = redact(_INVISIBLE.sub("", raw_f))[:MAX_FAMILY].strip()
    n = redact(_INVISIBLE.sub("", raw_n))[:MAX_NOTE].strip()
    body = n or (f"Please help the {f} household" if f else "Please help the family in the original post")
    return {"status": "FORWARDED_TO_CHARITY", "family": f or None, "note": n or None, "post_link": link,
            "receipt_text": f"Follow-up request: {body.rstrip('. ')}. {RECEIPT_LINE} {ETHICS}"}


RECEIPT_LINE = "Follow-up request sent to the charities (advisory, not verified by Lifeline)."


def payout_note(base, em):
    if not em or em.get("status") != "FORWARDED_TO_CHARITY":
        return base
    who = f" ({em['family']})" if em.get("family") else ""
    src = f" · Original post: {em['post_link']}" if em.get("post_link") else ""
    return f"{base} · Follow-up request{who} (advisory, not verified by Lifeline): {em['note'] or 'please check on this household'}{src} · {ETHICS}"
