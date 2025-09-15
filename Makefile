PY_V=3.11
PYTHON=python$(PY_V)
VENV_DIR=pyenv
VENV_PIP=$(VENV_DIR)/bin/pip
VENV_PYTHON=$(VENV_DIR)/bin/python
VENV_PYLINT=$(VENV_DIR)/bin/pylint


.PHONY: setup
setup:
	@ sudo apt install -y python$(PY_V)-dev python$(PY_V)-venv
	python$(PY_V) -m venv $(VENV_DIR) && \
	$(VENV_PIP) install --upgrade pip && \
	$(VENV_PIP) install -r dev/requirements.txt


.PHONY: run
run:
	PYTHONPATH=src $(VENV_PYTHON) -m src.main

.PHONY: $(VENV_DIR)
lint: $(VENV_DIR)
	PYTHONPATH=src $(VENV_PYLINT) --rcfile=dev/.pylintrc src/


.PHONY: gen-dev-requirements
gen-dev-requirements: $(VENV_DIR)
	$(VENV_PIP) freeze > dev/requirements.txt


.PHONY: install-build
install-build:
	$(VENV_PIP) install --upgrade build


.PHONY: package
package: install-build
	$(VENV_PYTHON) -m build


.PHONY: clean
clean:
	rm -rf $(VENV_DIR)
	rm -rf downloads extracted pdfs
