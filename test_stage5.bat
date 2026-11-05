@echo off
echo Stage 5: Mermaid and ASCII tree for JUnit
python src\main.py --config config.yaml --mermaid
echo.
echo Stage 5: Mermaid and ASCII tree for branching graph A
python src\main.py --config config_visual_tree.yaml --mermaid
echo.
echo Stage 5: Mermaid and ASCII tree for cycle X
python src\main.py --config config_visual_cycle.yaml --mermaid
echo.
echo Stage 5: Mermaid only when ascii_tree is false
python src\main.py --config config_test.yaml --mermaid
echo.
echo Stage 3: edge list is still available
python src\main.py --config config_test.yaml
echo.
echo Stage 1: config parameters
python src\main.py --config config_visual_tree.yaml --show-config
echo.
echo Done
exit /b 0
