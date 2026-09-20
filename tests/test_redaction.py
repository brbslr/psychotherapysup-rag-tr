from src.redaction import Redactor


def test_tckn_with_valid_checksum_is_redacted():
    r = Redactor()
    # Bilinen geçerli test TCKN'si
    out = r.redact("TC kimlik numaram 10000000146.")
    assert "10000000146" not in out.text
    assert "TCKN_1" in out.text


def test_invalid_tckn_is_not_redacted():
    r = Redactor()
    out = r.redact("Sipariş numarası 12345678901.")
    assert "12345678901" in out.text


def test_phone_is_redacted():
    r = Redactor()
    out = r.redact("Beni 0532 123 45 67 numarasından arayabilirsin.")
    assert "0532" not in out.text
    assert "TELEFON_1" in out.text


def test_placeholder_is_stable_within_session():
    r = Redactor()
    out = r.redact("Ayşe Hanım dün aradı. Bugün Ayşe Hanım tekrar aradı.")
    assert out.text.count("KISI_1") == 2


def test_email_and_handle():
    r = Redactor()
    out = r.redact("bana ali@example.com veya @aliyilmaz yaz")
    assert "ali@example.com" not in out.text
    assert "@aliyilmaz" not in out.text