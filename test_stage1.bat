@echo off
echo Good config, real mode
python src\main.py --config config.yaml
echo.
echo Good config, test mode
python src\main.py --config config_test.yaml
echo.
echo Help
python src\main.py --help
echo.
echo Bad package
python src\main.py --config bad_configs\bad_package.yaml
echo.
echo Bad repository
python src\main.py --config bad_configs\bad_repository.yaml
echo.
echo Bad mode
python src\main.py --config bad_configs\bad_mode.yaml
echo.
echo Bad ascii_tree
python src\main.py --config bad_configs\bad_tree.yaml
echo.
echo Bad max_depth
python src\main.py --config bad_configs\bad_depth.yaml
echo.
echo Missing parameter
python src\main.py --config bad_configs\missing_key.yaml
echo.
echo Unknown parameter
python src\main.py --config bad_configs\unknown_key.yaml
echo.
echo Bad YAML
python src\main.py --config bad_configs\bad_yaml.yaml
echo.
echo Empty config
python src\main.py --config bad_configs\empty.yaml
echo.
echo Missing test repository
python src\main.py --config bad_configs\missing_repo_file.yaml
echo.
echo Done
exit /b 0
