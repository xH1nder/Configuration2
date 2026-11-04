@echo off
echo Stage 3: real dependency graph
python src\main.py --config config.yaml
echo.
echo Stage 3: branching and shared dependency
python src\main.py --config config_test.yaml
echo.
echo Stage 3: cyclic dependencies
python src\main.py --config config_test_cycle.yaml
echo.
echo Stage 3: depth limit 2
python src\main.py --config config_test_depth.yaml
echo.
echo Stage 3: depth limit 10
python src\main.py --config config_test_deep.yaml
echo.
echo Stage 3: self-dependency
python src\main.py --config config_test_self.yaml
echo.
echo Bad test package name
python src\main.py --config bad_configs\bad_test_name.yaml
echo.
echo Missing test package
python src\main.py --config bad_configs\missing_test_package.yaml
echo.
echo Stage 2: direct dependencies
python src\main.py --config config.yaml --direct
echo.
echo Stage 1: config parameters
python src\main.py --config config.yaml --show-config
echo.
echo Done
exit /b 0
