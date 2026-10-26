.PHONY: test coverage smoke validate-smoke doctor simcheck import-real2motrix validate-real2motrix pull-cosmos-assets serve-cosmos-vllm

test:
	PYTHONPATH=src python3 -m unittest discover -s tests

coverage:
	PYTHONPATH=src python3 -m coverage run -m unittest discover -s tests
	PYTHONPATH=src python3 -m coverage report

smoke:
	PYTHONPATH=src python3 -m cosmos_robot_simgen.cli generate \
		--name smoke_demo \
		--prompt "A robot arm picks a blue cube from a work table and places it into a yellow bin." \
		--out outputs \
		--skip-cosmos

validate-smoke:
	PYTHONPATH=src python3 -m cosmos_robot_simgen.cli validate outputs/smoke_demo

doctor:
	PYTHONPATH=src python3 -m cosmos_robot_simgen.cli doctor

simcheck:
	PYTHONPATH=src python3 -m cosmos_robot_simgen.cli simcheck outputs/smoke_demo

import-real2motrix:
	scripts/import_to_real2motrix.sh outputs/smoke_demo/motrix_scene

validate-real2motrix:
	scripts/validate_with_real2motrix.sh outputs/smoke_demo/motrix_scene

pull-cosmos-assets:
	scripts/pull_cosmos3_nano_assets.sh

serve-cosmos-vllm:
	scripts/serve_cosmos3_nano_vllm.sh
