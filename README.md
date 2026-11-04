# Инструмент визуализации графа зависимостей (Вариант №19)

Проект разработан в рамках дисциплины «Конфигурационное управление».
Выполнил: Сопталев Никита Дмитриевич, ИКБО-32-25.

Вариант №19: инструмент визуализации графа зависимостей
для менеджера пакетов.
Текущее состояние: **Этап 2 (получение прямых зависимостей)**.

---

## 1. Общее описание

CLI-приложение на Python, которое читает параметры из YAML-файла,
проверяет их и получает список прямых зависимостей указанного
Maven-пакета.

На втором этапе приложение:

- принимает координаты пакета в формате `group:artifact:version`;
- собирает URL файла `.pom` в Maven-репозитории;
- скачивает POM средствами стандартной библиотеки Python;
- разбирает XML и печатает все прямые зависимости пакета;
- поддерживает свойства POM, `dependencyManagement` и координаты
  из родительского блока `parent`;
- умеет работать в тестовом режиме по локальному файлу графа,
  чтобы проверять логику без сети.

Менеджеры пакетов (Maven, Gradle) и сторонние библиотеки для
получения зависимостей не используются. POM скачивается через
`urllib.request`, а разбирается через `xml.etree.ElementTree`.
Единственная внешняя зависимость проекта - PyYAML для чтения
конфигурации.

### История этапов

- Этап 1: CLI-прототип, проверка YAML-конфига и вывод параметров
  (коммит `1d8b23a`).
- Этап 2: получение и вывод прямых зависимостей Maven-пакета.
- Этапы 3-5: в следующих коммитах.

---

## 2. Параметры командной строки

| Параметр | Описание |
|----------|----------|
| `--config`, `-c` | Путь к YAML-файлу конфигурации |
| `--show-config` | Показать параметры конфига (режим этапа 1) |
| `--help`, `-h` | Вывод подсказки по запуску |

Если `--config` не указан, берется файл `config.yaml` из текущей папки.
Без `--show-config` приложение получает и печатает зависимости.

---

## 3. Настраиваемые параметры

| Ключ | Тип | Описание | Проверка |
|------|-----|----------|----------|
| `package` | строка | координаты анализируемого пакета | в режиме `real` - `group:artifact:version`, в режиме `test` - короткое имя; не пустое, только латиница, цифры и `. _ - :` |
| `repository` | строка | URL Maven-репозитория или путь к файлу тестового графа | URL с http/https или существующий файл |
| `repository_mode` | строка | режим работы с репозиторием | только `real` или `test` |
| `ascii_tree` | логический | вывод в виде ASCII-дерева (для следующих этапов) | только `true` или `false` |
| `max_depth` | целое | максимальная глубина анализа (для следующих этапов) | целое число от 1 до 100 |

Пример основного конфига `config.yaml`:

```yaml
package: junit:junit:4.13.2
repository: https://repo1.maven.org/maven2
repository_mode: real
ascii_tree: true
max_depth: 3
```

Пример тестового конфига `config_test.yaml`:

```yaml
package: A
repository: test_repo.txt
repository_mode: test
ascii_tree: false
max_depth: 2
```

В режиме `test` параметр `repository` указывает на существующий файл
с графом. Строка `A B C` означает, что пакет `A` напрямую зависит
от `B` и `C`. Строки, начинающиеся с `#`, считаются комментариями.

### Внутренние константы

| Константа | Значение | Назначение |
|-----------|----------|------------|
| `default_config` | `config.yaml` | конфиг по умолчанию |
| `min_depth` | 1 | минимальная глубина |
| `max_depth_limit` | 100 | максимальная глубина |
| `gav_parts` | 3 | число частей координат |
| `timeout` | 30 | таймаут скачивания POM, секунды |
| `max_subst` | 5 | предельное число подстановок свойств |
| `http_not_found` | 404 | код ответа «пакет не найден» |

---

## 4. Как получаются зависимости

1. Конфиг читается и проверяется, координаты делятся на
   `group`, `artifact` и `version`.
2. Из адреса репозитория собирается путь вида
   `group/with/slashes/artifact/version/artifact-version.pom`.
3. POM скачивается через `urllib.request` с таймаутом.
4. XML разбирается через `xml.etree.ElementTree`; namespace
   Maven отбрасывается.
5. Значения `${...}` заменяются свойствами из блока
   `<properties>`, а также `project.version`, `pom.version` и
   другими координатами проекта.
6. Если у зависимости нет версии, она берется из
   `dependencyManagement` этого же POM.
7. Если у проекта нет своей версии или группы, они берутся из
   блока `<parent>`.
8. Каждая прямая зависимость печатается отдельной строкой в
   формате `group:artifact:version`. Если версия не определена,
   печатается `group:artifact`.

Учитываются только прямые зависимости из блока `<dependencies>`.
Транзитивные зависимости не запрашиваются: это задача следующих
этапов. Параметры `ascii_tree` и `max_depth` на втором этапе
принимаются и проверяются, но на вывод пока не влияют.

Родительский POM не скачивается. Поэтому версия, заданная только
в родительском `dependencyManagement`, может остаться неизвестной,
и зависимость будет напечатана без версии.

---

## 5. Обработка ошибок

Проверяется не только значение каждого параметра, но и сам файл:

- файл не найден или не читается;
- файл пустой;
- синтаксическая ошибка YAML;
- конфиг не является словарём, а списком или строкой;
- пропущен обязательный ключ;
- указан лишний ключ;
- неверный формат координат пакета;
- пакет не найден в репозитории;
- репозиторий недоступен;
- POM содержит некорректный XML.

Примеры ошибок:

```
> run.bat --config bad_configs\bad_package.yaml
error: package must not be empty

> run.bat --config bad_configs\bad_package_format.yaml
error: package must be group:artifact:version

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

При успехе приложение возвращает код 0, при любой ошибке - код 1.

---

## 6. Функции

| Функция | Описание |
|---------|----------|
| `load_config` | читает YAML-файл и возвращает словарь |
| `check_keys` | проверяет наличие нужных ключей и отсутствие лишних |
| `check_package` | проверяет имя пакета и формат GAV |
| `check_mode` | проверяет режим `real` или `test` |
| `check_url` | проверяет URL реального репозитория |
| `check_repo_file` | проверяет путь к файлу тестового репозитория |
| `check_repository` | выбирает проверку URL или файла по режиму |
| `check_tree` | проверяет логический параметр `ascii_tree` |
| `check_depth` | проверяет диапазон `max_depth` |
| `check_params` | проверяет все параметры вместе |
| `local_name` | убирает namespace из имени XML-тега |
| `find_child` | находит первого ребенка с нужным именем |
| `get_text` | берет текст ребенка или пустую строку |
| `read_properties` | собирает свойства POM в словарь |
| `substitute` | подставляет свойства в строку |
| `project_value` | берет значение проекта с учетом `parent` |
| `fill_project_props` | добавляет координаты проекта в свойства |
| `managed_versions` | собирает версии из `dependencyManagement` |
| `make_dependency` | собирает строку одной прямой зависимости |
| `read_dependencies` | читает блок `<dependencies>` |
| `parse_pom` | разбирает POM и возвращает прямые зависимости |
| `build_pom_url` | собирает URL файла POM в репозитории |
| `download_text` | скачивает текст по URL |
| `read_test_graph` | читает прямые зависимости из тестового файла |
| `fetch_real_deps` | получает зависимости из Maven-репозитория |
| `get_direct_deps` | выбирает способ получения по режиму |
| `show_deps` | печатает зависимости по одной в строке |
| `show_params` | печатает параметры в формате ключ-значение |
| `parse_args` | разбирает аргументы командной строки |
| `main` | запускает приложение и возвращает код выхода |

---

## 7. Команды для сборки и запуска

Нужен Python 3.10+ и библиотека PyYAML. Maven устанавливать не нужно.

Установка зависимости:

```bat
pip install -r requirements.txt
```

Запуск с конфигом по умолчанию (JUnit из Maven Central):

```bat
run.bat
```

Запуск с другим конфигом:

```bat
run.bat --config config_test.yaml
```

Показ параметров конфига без обращения к сети:

```bat
run.bat --show-config
```

Запуск тестов:

```bat
python -m unittest discover -s tests -v
```

Демонстрация этапа 1:

```bat
test_stage1.bat
```

Демонстрация этапа 2:

```bat
test_stage2.bat
```

Для реального режима нужен доступ в интернет. Тестовый режим
работает полностью офлайн.

---

## 8. Структура проекта

```
├── src/
│   └── main.py              # весь код этапов 1-2
├── tests/
│   └── test_main.py         # unit-тесты (73 теста)
├── bad_configs/
│   ├── bad_package.yaml     # пустое имя пакета
│   ├── bad_package_format.yaml  # неверный формат GAV
│   ├── bad_repository.yaml  # неверный URL
│   ├── bad_mode.yaml        # неверный режим
│   ├── bad_tree.yaml        # неверный ascii_tree
│   ├── bad_depth.yaml       # неверная глубина
│   ├── missing_key.yaml     # нет max_depth
│   ├── unknown_key.yaml     # лишний ключ
│   ├── bad_yaml.yaml        # ошибка синтаксиса YAML
│   ├── empty.yaml           # пустой файл
│   └── missing_repo_file.yaml  # нет файла тестового репозитория
├── config.yaml              # основной конфиг (JUnit, режим real)
├── config_test.yaml         # конфиг для режима test
├── test_repo.txt            # тестовый граф зависимостей
├── test_stage1.bat          # демонстрация этапа 1
├── test_stage2.bat          # демонстрация этапа 2
├── run.bat                  # запуск приложения
├── requirements.txt         # зависимость PyYAML
├── .gitignore               # служебные файлы Python
└── README.md                # документация
```

---

## 9. Примеры использования

Прямые зависимости JUnit 4.13.2:

```
> run.bat
org.hamcrest:hamcrest-core:1.3
org.hamcrest:hamcrest-library:1.3
```

Тестовый граф: пакет `A` зависит от `B` и `C`.

```
> run.bat --config config_test.yaml
B
C
```

Показ параметров конфига:

```
> run.bat --show-config
package=junit:junit:4.13.2
repository=https://repo1.maven.org/maven2
repository_mode=real
ascii_tree=true
max_depth=3
```

Подсказка:

```
> run.bat --help
usage: run.bat [--config PATH] [--show-config]
```

Неизвестный аргумент:

```
> run.bat --vfs vfs.json
error: unknown argument: --vfs
usage: run.bat [--config PATH] [--show-config]
```
