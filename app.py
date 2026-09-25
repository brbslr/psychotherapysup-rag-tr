"""Psikolojik Destek Asistan — Streamlit arayüzü (Türkçe).

Streamlit Community Cloud'da ücretsiz yayınlanabilir.
Secrets yönetimi için: .streamlit/secrets.toml veya .env
"""
from __future__ import annotations

import streamlit as st

from src.config import get_settings
from src.engine import WellnessEngine

st.set_page_config(
    page_title="Psikolojik Destek Asistan",
    page_icon="🌱",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── Secrets → env köprüsü (Streamlit Cloud için) ─────────────────
try:
    for k, v in st.secrets.items():  # type: ignore[union-attr]
        import os

        os.environ.setdefault(k.upper(), str(v))
except Exception:  # noqa: BLE001
    pass


@st.cache_resource
def load_engine():
    from src.ingest import load_markdown_dir, write_local_index
    from src.config import get_settings

    s = get_settings()
    if not s.local_index_path.exists():
        with st.spinner("Bilgi tabanı hazırlanıyor..."):
            passages = load_markdown_dir(s.clinical_docs_dir)
            write_local_index(passages, s.local_index_path)
    return WellnessEngine(s)


engine = load_engine()
settings = get_settings()

# ── Oturum durumu ────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "consent" not in st.session_state:
    st.session_state.consent = False
if "crisis_locked" not in st.session_state:
    st.session_state.crisis_locked = False

# ── Kenar çubuğu ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🌱 Psikolojik Destek Asistan")
    mode_label = {
        ("local", "echo"): "🟢 Ücretsiz demo (LLM kapalı)",
        ("local", "ollama"): "🟢 Yerel model (ücretsiz)",
        ("azure", "azure"): "🔵 Azure modu",
    }.get((settings.app_mode, settings.llm_provider), f"⚙️ {settings.app_mode}/{settings.llm_provider}")
    st.caption(mode_label)

    if engine.crisis.protocol.get("meta", {}).get("reviewed_by", "BEKLENİYOR") == "BEKLENİYOR":
        st.warning(
            "⚠️ Kriz protokolü henüz klinik olarak onaylanmadı. "
            "Bu sistem şu an yalnızca test amaçlıdır.",
            icon="⚠️",
        )

    st.divider()
    st.markdown("**Acil durumda**")
    st.error("112'yi ara\n\nTürkiye'de 112 acil çağrı merkezidir.")
    st.divider()

    if st.session_state.messages:
        st.download_button(
            "Sohbeti indir (JSON)",
            data=str(st.session_state.messages),
            file_name="sohbet.json",
            mime="application/json",
        )
    if st.button("Sohbeti temizle"):
        st.session_state.messages = []
        st.session_state.crisis_locked = False
        st.rerun()

    with st.expander("Bu sistem nedir / ne değildir?"):
        st.markdown(
            """
**Nedir:** Günlük stres ve kaygı ile baş etmeye yönelik, psikoeğitim
bilgileri paylaşan bir iyi oluş aracı.

**Ne değildir:** Terapi değildir. Teşhis koymaz. İlaç önermez.
Bir terapistin yerini almaz.

**Verileriniz:** Mesajlarınızdaki isim, telefon, e-posta, TC kimlik
numarası gibi tanımlayıcılar gönderilmeden önce otomatik olarak
gizlenir. Sohbetler klinik kalite incelemesi için anonim olarak
kaydedilir.
            """
        )

# ── Başlık ───────────────────────────────────────────────────────
st.title("🌱 Psikolojik Destek Asistan")
st.caption("Günlük psikoloji destekleyici bir araç. Psikoterapi değildir.")

# ── KVKK açık rıza kapısı ────────────────────────────────────────
if not st.session_state.consent:
    st.info(
        "Devam etmek için lütfen aşağıdaki bilgilendirmeyi okuyun ve onaylayın.",
        icon="ℹ️",
    )
    with st.expander("KVKK Aydınlatma ve Açık Rıza Metni", expanded=True):
        st.markdown(
            """
**Veri sorumlusu:** [Şirket/kişi adı — doldurulacak]

**İşlenen veriler:** Sohbet mesajlarınız. Sağlık verisi KVKK md.6
kapsamında **özel nitelikli kişisel veri** sayılır ve yalnızca
**açık rızanız** ile işlenebilir.

**Amaç:** Size destekleyici yanıt üretmek ve sistemin klinik
kalitesini iyileştirmek.

**Aktarım:** Yanıt üretmek için mesajlar yurt dışındaki sunucularda
işlenir. Gönderim öncesinde isim, telefon, e-posta, TC kimlik numarası
gibi doğrudan tanımlayıcılar otomatik olarak gizlenir.

**Saklama:** Anonimleştirilmiş sohbet kayıtları [süre] boyunca saklanır.

**Haklarınız:** KVKK md.11 kapsamındaki haklarınız için
[iletişim adresi] adresine başvurabilirsiniz.

**Onay:** Aşağıdaki kutuyu işaretleyerek yukarıdaki bilgilendirmeyi
okuduğunuzu ve verilerinizin belirtilen şekilde işlenmesine açık rıza
verdiğinizi beyan edersiniz.

> Bu metin bir hukukçu tarafından incelenmemiştir. Yayına almadan
> önce KVKK konusunda uzman bir avukata danışın.
            """
        )
    if st.checkbox("Okudum, anladım ve açık rıza veriyorum."):
        st.session_state.consent = True
        st.rerun()
    st.stop()

# ── Kriz kilidi ──────────────────────────────────────────────────
if st.session_state.crisis_locked:
    st.error(
        "### Şu an yanında gerçek bir insanın olması önemli\n\n"
        "Lütfen **112**'yi ara. Türkiye'de 112 acil çağrı merkezidir ve "
        "psikiyatrik acil durumlar için de kullanılır.\n\n"
        "Bu bir yapay zekâ aracıdır ve acil durumlarda yeterli değildir.",
        icon="🚨",
    )
    st.stop()

# ── Geçmiş mesajlar ──────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander(f"📚 Kaynaklar ({len(msg['sources'])})"):
                for i, s in enumerate(msg["sources"], start=1):
                    st.markdown(f"**[{i}] {s.heading_path or s.title or s.source}** — skor `{s.score:.3f}`")
                    st.markdown(s.content)
                    if i < len(msg["sources"]):
                        st.divider()

# ── Giriş ────────────────────────────────────────────────────────
if prompt := st.chat_input("Nasıl hissediyorsun?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
    ]

    with st.chat_message("assistant"):
        with st.spinner("Düşünüyorum..."):
            reply = engine.reply(prompt, history=history)

        if reply.crisis.should_block_ai:
            st.session_state.crisis_locked = True
            st.rerun()

        st.markdown(reply.text)

        if reply.redaction and reply.redaction.had_identifiers:
            st.caption(
                "🔒 Gizlenen tanımlayıcılar: "
                + ", ".join(f"{k}×{v}" for k, v in reply.redaction.counts.items())
            )

        if reply.sources:
            with st.expander(f"📚 Kaynaklar ({len(reply.sources)})"):
                for i, s in enumerate(reply.sources, start=1):
                    st.markdown(f"**[{i}] {s.heading_path or s.title or s.source}** — skor `{s.score:.3f}`")
                    st.markdown(s.content)
                    if i < len(reply.sources):
                        st.divider()

        if reply.degraded:
            st.caption("⚠️ Bazı bileşenler geçici olarak kullanılamıyor.")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": reply.text,
            "sources": reply.sources,
        }
    )

st.divider()
st.caption(
    "Bu araç terapi değildir, teşhis koymaz. Acil durumda 112'yi arayın. "
    "Klinik sorumlu: [ad] — Protokol sürümü: "
    f"{engine.crisis.protocol.get('meta', {}).get('version', '-')}"
)