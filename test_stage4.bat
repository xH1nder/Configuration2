@echo off
echo Stage 4: real dependency load order (JUnit)
python src\main.py --config config.yaml --order
echo.
echo Stage 3: graph for the same package
python src\main.py --config config.yaml
echo.
echo Stage 4: branching load order
python src\main.py --config config_test.yaml --order
echo.
echo Stage 4: cycle load order
python src\main.py --config config_test_cycle.yaml --order
echo.
echo Stage 4: depth limit 2
python src\main.py --config config_test_depth.yaml --order
echo.
echo Stage 4: full chain
python src\main.py --config config_test_deep.yaml --order
echo.
echo Stage 4: self-dependency
python src\main.py --config config_test_self.yaml --order
echo.
echo Stage 2: direct dependencies
python src\main.py --config config.yaml --direct
echo.
echo Stage 1: config parameters
python src\main.py --config config.yaml --show-config
echo.
echo Error: --direct and --order together
python src\main.py --config config.yaml --direct --order
echo.
echo Done
exit /b 0
