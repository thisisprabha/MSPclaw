.PHONY: install test server agent enduser cli

install:
	pip install -r requirements.txt

test:
	pytest -q

server:
	python -m server.main

agent:
	python -m agent.main

enduser:
	python -m enduser.cli $(filter-out $@,$(MAKECMDGOALS))

cli:
	python msp-cli/main.py $(filter-out $@,$(MAKECMDGOALS))

%:
	@:
