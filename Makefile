# agent-ready — the same commands any agent should run, in one place.
.PHONY: help test audit badge install ci

help:
	@echo "make test    run the test suite (no dependencies needed)"
	@echo "make audit   score this repository with the tool it ships"
	@echo "make badge   regenerate assets/agent-ready.svg"
	@echo "make install install the agent-ready console script"
	@echo "make ci      everything CI runs, locally"

test:
	python3 -m unittest discover -s tests -v

audit:
	python3 agent_ready.py .

badge:
	python3 agent_ready.py . --badge assets/agent-ready.svg

install:
	python3 -m pip install -e .

ci: test audit
