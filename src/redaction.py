"""KVKK uyumluluk katmanı.

Sağlık verisi KVKK md.6 kapsamında 'özel nitelikli' kişisel veridir.
Bu modül, metin Azure/LLM'e gönderilmeden ÖNCE doğrudan tanımlayıcıları
sabit yer tutucularla değiştirir. Böylece yurt dışına aktarım (md.9)
riski teknik olarak azaltılır.

SINIRLILIK: İsim tespiti regex ile kusurludur. Üretim ortamında
Azure AI Language PII tespiti veya yerel bir NER modeli eklenmelidir.
Ancak bu ek bir bulut çağrısı demektir; bu bir mahremiyet/servis
ödünleşmesidir ve partner ile birlikte kararlaştırılmalıdır.
"""
from __future__ import annotations

import re
from itertools import count

from .schemas import RedactionResult

# ── TC Kimlik No doğrulama (checksum) ────────────────────────────
def _valid_tckn(v: str) -> bool:
    if len(v) != 11 or v[0] == "0" or not v.isdigit():
        return False
    d = [int(c) for c in v]
    odd = d[0] + d[2] + d[4] + d[6] + d[8]
    even = d[1] + d[3] + d[5] + d[7]
    if (odd * 7 - even) % 10 != d[9]:
        return False
    return sum(d[:10]) % 10 == d[10]


# ── Kalıplar (sıra önemli: telefon, TCKN'den ÖNCE çalışır) ───────
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_IBAN = re.compile(r"\bTR\d{2}[\s]?(?:\d{4}[\s]?){5}\d{2}\b", re.IGNORECASE)
_URL = re.compile(r"https?://\S+|www\.\S+")
_HANDLE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{3,}")
# Türk telefon: +90 5xx..., 0090..., 0 5xx..., 5xx xxx xx xx
_PHONE = re.compile(
    r"(?:(?:\+|00)90[\s.-]?)?(?:0[\s.-]?)?5\d{2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}"
)
_TCKN = re.compile(r"\b[1-9]\d{10}\b")
# "Sayın Ahmet Yılmaz" / "Sn. Ayşe K."
_HONORIFIC = re.compile(
    r"\b(?:Sayın|Sn\.?)\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)?)"
)
# "Ahmet Bey" / "Ayşe Hanım"
_BEY_HANIM = re.compile(
    r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,})\s+(Bey|Hanım|Hanımefendi|Beyefendi)\b"
)

_TYPE_ORDER = [
    ("EMAIL", _EMAIL, lambda m: True),
    ("IBAN", _IBAN, lambda m: True),
    ("URL", _URL, lambda m: True),
    ("KULLANICI_ADI", _HANDLE, lambda m: True),
    ("TELEFON", _PHONE, lambda m: True),
    ("TCKN", _TCKN, lambda m: _valid_tckn(m.group(0))),
]


class Redactor:
    """Oturum boyunca tutarlı yer tutucular üretir.

    Aynı kişi ikinci kez geçtiğinde aynı yer tutucuyu alır
    (örn. [KISI_1]), böylece LLM bağlamı takip edebilir ama
    gerçek kimlik hiçbir zaman dışarı çıkmaz.
    """

    def __init__(self) -> None:
        self._map: dict[str, str] = {}
        self._counters: dict[str, count] = {}

    def _placeholder(self, kind: str, original: str) -> str:
        key = f"{kind}:{original.strip().lower()}"
        if key not in self._map:
            if kind not in self._counters:
                self._counters[kind] = count(1)
            self._map[key] = f"[{kind}_{next(self._counters[kind])}]"
        return self._map[key]

    def redact(self, text: str) -> RedactionResult:
        if not text:
            return RedactionResult(text=text)

        counts: dict[str, int] = {}
        out = text

        for kind, pattern, validator in _TYPE_ORDER:
            def _sub(m: re.Match, _kind=kind, _val=validator) -> str:
                if not _val(m):
                    return m.group(0)
                counts[_kind] = counts.get(_kind, 0) + 1
                return self._placeholder(_kind, m.group(0))

            out = pattern.sub(_sub, out)

        # İsimler: unvan kalıpları
        def _hon(m: re.Match) -> str:
            counts["KISI"] = counts.get("KISI", 0) + 1
            return f"Sayın {self._placeholder('KISI', m.group(1))}"

        out = _HONORIFIC.sub(_hon, out)

        def _bh(m: re.Match) -> str:
            counts["KISI"] = counts.get("KISI", 0) + 1
            return f"{self._placeholder('KISI', m.group(1))} {m.group(2)}"

        out = _BEY_HANIM.sub(_bh, out)

        return RedactionResult(text=out, mapping=dict(self._map), counts=counts)


_default = Redactor()


def redact(text: str) -> RedactionResult:
    return _default.redact(text)