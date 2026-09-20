# Wellness RAG TR

Türkçe destekleyici iyi oluş asistanı. Klinik dokümanlara dayalı
RAG (Retrieval-Augmented Generation) mimarisi.

**Uyarı:** Bu bir terapi aracı değildir. Klinik inceleme tamamlanmadan
gerçek kullanıcılara açılmamalıdır.

## Hızlı başlangıç

    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    python scripts/ingest_docs.py
    streamlit run app.py