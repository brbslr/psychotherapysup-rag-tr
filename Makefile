.PHONY: setup index run test smoke azure-index azure-upload clean

setup:
	pip install -r requirements.txt

index:
	python scripts/ingest_docs.py

run:
	streamlit run app.py

test:
	pytest -q

smoke:
	python scripts/smoke_test.py

azure-index:
	python scripts/create_index.py --recreate

azure-upload:
	python scripts/ingest_docs.py --upload

clean:
	rm -rf data/local_index.jsonl logs/*.jsonl