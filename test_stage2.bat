@echo off
echo Stage 2: direct dependencies of junit:junit:4.13.2
python src\main.py --config config.yaml --direct
echo.
echo Stage 2: direct dependencies from test graph
python src\main.py --config config_test.yaml --direct
echo.
echo Stage 1: config parameters
python src\main.py --config config.yaml --show-config
echo.
echo Bad package format
python src\main.py --config bad_configs\bad_package_format.yaml
echo.
echo Done
exit /b 0
