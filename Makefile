.PHONY: setup seed run test

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

seed:
	. .venv/bin/activate && python -m itr_workspace.seed

run:
	. .venv/bin/activate && streamlit run app.py

test:
	. .venv/bin/activate && python -m pytest
