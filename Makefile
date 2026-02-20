.PHONY: setup test build-pict build-exe clean

setup:
	pip install pytest pyinstaller

test:
	pytest -v

build-pict-linux:
	./scripts/build_pict.sh

build-pict-macos:
	./scripts/build_pict.sh

build-exe-unix:
	./scripts/build_exe.sh

clean:
	rm -rf build/ dist/ *.spec .pytest_cache/ __pycache__/ *.pict *.csv
