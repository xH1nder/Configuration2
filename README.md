# Инструмент визуализации графа зависимостей (Вариант №19)

Проект разработан в рамках дисциплины «Конфигурационное управление».
Выполнил: Сопталев Никита Дмитриевич, ИКБО-32-25.

Вариант №19: инструмент визуализации графа зависимостей
для менеджера пакетов.
Текущее состояние: **Этап 1 (минимальный прототип)**.

---

## 1. Общее описание

CLI-приложение на Python, которое читает параметры из YAML-файла,
проверяет их и печатает в формате ключ-значение. На первом этапе
граф зависимостей ещё не строится: приложение только проверяет
конфигурацию, как требует задание.

### Реализованные возможности

- запуск из командной строки, путь к конфигу задается `--config`;
- все пять параметров берутся из YAML-файла;
- каждый параметр проверяется, при ошибке выводится понятное сообщение;
- вывод параметров в формате `ключ=значение`;
- код возврата 0 при успехе и 1 при ошибке.

### История этапов

- Этап 1: CLI-прототип и проверка YAML-конфига.
- Этапы 2-5: в следующих коммитах.

---

## 2. Параметры командной строки

| Параметр | Описание |
|----------|----------|
| `--config`, `-c` | Путь к YAML-файлу конфигурации |
| `--help`, `-h` | Вывод подсказки по запуску |

Если `--config` не указан, берется файл `config.yaml` из текущей папки.

---

## 3. Настраиваемые параметры

| Ключ | Тип | Описание | Проверка |
|------|-----|----------|----------|
| `package` | строка | имя анализируемого пакета | не пустое, только латиница, цифры и `. _ - :` |
| `repository` | строка | URL репозитория или путь к файлу тестового графа | URL с http/https или существующий файл |
| `repository_mode` | строка | режим работы с репозиторием | только `real` или `test` |
| `ascii_tree` | логический | вывод зависимостей в виде ASCII-дерева | только `true` или `false` |
| `max_depth` | целое | максимальная глубина анализа | целое число от 1 до 100 |

Пример конфига `config.yaml`:

```yaml
package: org.apache.commons:commons-lang3
repository: https://repo1.maven.org/maven2
repository_mode: real
ascii_tree: true
max_depth: 3
```

В режиме `test` параметр `repository` должен указывать на существующий
файл. Пример есть в `config_test.yaml`, файл графа - `test_repo.txt`.

---

## 4. Обработка ошибок

Проверяется не только значение каждого параметра, но и сам файл:

- файл не найден или не читается;
- файл пустой;
- синтаксическая ошибка YAML;
- конфиг не является словарём, а списком или строкой;
- пропущен обязательный ключ;
- указан лишний ключ.

Примеры ошибок:

```
> run.bat --config bad_configs\bad_package.yaml
error: package must not be empty

> run.bat --config bad_configs\bad_repository.yaml
error: repository URL must start with http:// or https://

> run.bat --config bad_configs\bad_mode.yaml
error: repository_mode must be real or test

> run.bat --config bad_configs\bad_tree.yaml
error: ascii_tree must be true or false

> run.bat --config bad_configs\bad_depth.yaml
error: max_depth must be from 1 to 100

> run.bat --config bad_configs\missing_key.yaml
error: missing parameter: max_depth
```

---

## 5. Функции

| Функция | Описание |
|---------|----------|
| `load_config` | читает YAML-файл и возвращает словарь |
| `check_keys` | проверяет наличие нужных ключей и отсутствие лишних |
| `check_package` | проверяет имя пакета |
| `check_mode` | проверяет режим `real` или `test` |
| `check_url` | проверяет URL реального репозитория |
| `check_repo_file` | проверяет путь к файлу тестового репозитория |
| `check_repository` | выбирает проверку URL или файла по режиму |
| `check_tree` | проверяет логический параметр `ascii_tree` |
| `check_depth` | проверяет диапазон `max_depth` |
| `check_params` | проверяет все параметры вместе |
| `show_params` | печатает параметры в формате ключ-значение |
| `parse_args` | разбирает аргументы командной строки |
| `main` | запускает приложение и возвращает код выхода |

---

## 6. Команды для сборки и запуска

Нужен Python 3.10+ и библиотека PyYAML.

Установка зависимости:

```bat
pip install -r requirements.txt
```

Запуск с конфигом по умолчанию:

```bat
run.bat
```

Запуск с другим конфигом:

```bat
run.bat --config config_test.yaml
```

Запуск тестов:

```bat
python -m unittest discover -s tests -v
```

Демонстрация всех ошибок:

```bat
test_stage1.bat
```

---

## 7. Структура проекта

```
├── src/
│   └── main.py              # весь код этапа 1
├── tests/
│   └── test_main.py         # unit-тесты (48 тестов)
├── bad_configs/
│   ├── bad_package.yaml     # пустое имя пакета
│   ├── bad_repository.yaml  # неверный URL
│   ├── bad_mode.yaml        # неверный режим
│   ├── bad_tree.yaml        # неверный ascii_tree
│   ├── bad_depth.yaml       # неверная глубина
│   ├── missing_key.yaml     # нет max_depth
│   ├── unknown_key.yaml     # лишний ключ
│   ├── bad_yaml.yaml        # ошибка синтаксиса YAML
│   ├── empty.yaml           # пустой файл
│   └── missing_repo_file.yaml  # нет файла тестового репозитория
├── config.yaml              # основной конфиг (режим real)
├── config_test.yaml         # конфиг для режима test
├── test_repo.txt            # тестовый граф зависимостей
├── test_stage1.bat          # демонстрация запуска и ошибок
├── run.bat                  # запуск приложения
├── requirements.txt         # зависимость PyYAML
├── .gitignore               # служебные файлы Python
└── README.md                # документация
```

---

## 8. Примеры использования

Запуск с основным конфигом:

```
> run.bat
package=org.apache.commons:commons-lang3
repository=https://repo1.maven.org/maven2
repository_mode=real
ascii_tree=true
max_depth=3
```

Запуск с тестовым репозиторием:

```
> run.bat --config config_test.yaml
package=A
repository=test_repo.txt
repository_mode=test
ascii_tree=false
max_depth=2
```

Подсказка:

```
> run.bat --help
usage: run.bat [--config PATH]
```

Неизвестный аргумент:

```
> run.bat --vfs vfs.json
error: unknown argument: --vfs
usage: run.bat [--config PATH]
```
