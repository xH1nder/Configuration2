"""Инструмент визуализации графа зависимостей. Этап 1."""

import os
import re
import sys
from urllib.parse import urlparse

import yaml

default_config = "config.yaml"
min_depth = 1
max_depth_limit = 100
step = 1
param_keys = [
    "package",
    "repository",
    "repository_mode",
    "ascii_tree",
    "max_depth",
]
modes = ["real", "test"]
url_schemes = ["http", "https"]
package_pattern = r"^[A-Za-z0-9._:-]+$"
usage = "usage: run.bat [--config PATH]"


def load_config(path):
    """Прочитать YAML-конфиг и вернуть словарь."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeError):
        return None, "cannot read config file: " + path
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None, "bad YAML in config file: " + path
    if data is None:
        return None, "config file is empty: " + path
    if not isinstance(data, dict):
        return None, "config must be a YAML mapping"
    return data, None


def check_keys(data):
    """Проверить, что в конфиге ровно нужные ключи."""
    missing = []
    for key in param_keys:
        if key not in data:
            missing.append(key)
    if missing != []:
        return "missing parameter: " + ", ".join(missing)
    extra = []
    for key in data:
        if key not in param_keys:
            extra.append(key)
    if extra != []:
        names = sorted(str(key) for key in extra)
        return "unknown parameter: " + ", ".join(names)
    return None


def check_package(value):
    """Проверить имя анализируемого пакета."""
    if not isinstance(value, str):
        return None, "package must be a string"
    name = value.strip()
    if name == "":
        return None, "package must not be empty"
    if re.match(package_pattern, name) is None:
        return None, "package has bad characters: " + name
    return name, None


def check_mode(value):
    """Проверить режим работы с репозиторием."""
    if value not in modes:
        return None, "repository_mode must be real or test"
    return value, None


def check_url(text):
    """Проверить URL реального репозитория."""
    if " " in text:
        return None, "repository URL must not have spaces"
    parsed = urlparse(text)
    if parsed.scheme not in url_schemes:
        return None, "repository URL must start with http:// or https://"
    if parsed.netloc == "":
        return None, "repository URL has no host"
    return text, None


def check_repo_file(text):
    """Проверить путь к файлу тестового репозитория."""
    if not os.path.isfile(text):
        return None, "test repository file not found: " + text
    return text, None


def check_repository(value, mode):
    """Проверить URL или путь к тестовому репозиторию."""
    if not isinstance(value, str):
        return None, "repository must be a string"
    text = value.strip()
    if text == "":
        return None, "repository must not be empty"
    if mode == "real":
        return check_url(text)
    return check_repo_file(text)


def check_tree(value):
    """Проверить режим вывода ASCII-дерева."""
    if not isinstance(value, bool):
        return None, "ascii_tree must be true or false"
    return value, None


def check_depth(value):
    """Проверить максимальную глубину анализа."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None, "max_depth must be an integer"
    if value < min_depth or value > max_depth_limit:
        msg = "max_depth must be from " + str(min_depth)
        return None, msg + " to " + str(max_depth_limit)
    return value, None


def check_params(data):
    """Проверить все параметры из конфига."""
    bad = check_keys(data)
    if bad is not None:
        return None, bad
    mode, bad = check_mode(data["repository_mode"])
    if bad is not None:
        return None, bad
    package, bad = check_package(data["package"])
    if bad is not None:
        return None, bad
    repository, bad = check_repository(data["repository"], mode)
    if bad is not None:
        return None, bad
    ascii_tree, bad = check_tree(data["ascii_tree"])
    if bad is not None:
        return None, bad
    depth, bad = check_depth(data["max_depth"])
    if bad is not None:
        return None, bad
    params = {
        "package": package,
        "repository": repository,
        "repository_mode": mode,
        "ascii_tree": ascii_tree,
        "max_depth": depth,
    }
    return params, None


def show_params(params):
    """Напечатать параметры в формате ключ-значение."""
    for key in param_keys:
        value = params[key]
        if isinstance(value, bool):
            value = str(value).lower()
        print(key + "=" + str(value))


def parse_args(argv):
    """Разобрать параметры командной строки."""
    path = default_config
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--config" or arg == "-c":
            next_index = index + step
            if next_index >= len(argv):
                return None, "option needs a value: " + arg
            path = argv[next_index]
            index = next_index + step
        else:
            return None, "unknown argument: " + arg
    return path, None


def main(argv=None):
    """Точка входа приложения."""
    if argv is None:
        argv = sys.argv[1:]
    if "-h" in argv or "--help" in argv:
        print(usage)
        return 0
    path, bad = parse_args(argv)
    if bad is not None:
        print("error: " + bad, file=sys.stderr)
        print(usage, file=sys.stderr)
        return 1
    data, bad = load_config(path)
    if bad is not None:
        print("error: " + bad, file=sys.stderr)
        return 1
    params, bad = check_params(data)
    if bad is not None:
        print("error: " + bad, file=sys.stderr)
        return 1
    show_params(params)
    return 0


if __name__ == "__main__":
    sys.exit(main())
