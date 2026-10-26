#!/usr/bin/env bash
set -euo pipefail

package_path="${1:-outputs/smoke_demo}"

PYTHONPATH=src python3 -m cosmos_robot_simgen.cli simcheck "${package_path}"
