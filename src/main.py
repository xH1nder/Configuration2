"""Инструмент визуализации графа зависимостей. Этап 2."""

import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import yaml

default_config = "config.yaml"
min_depth = 1
max_depth_limit = 100
gav_parts = 3
timeout = 30
max_subst = 5
http_not_found = 404
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
usage = "usage: run.bat [--config PATH] [--show-config]"


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


def check_package(value, mode):
    """Проверить имя анализируемого пакета."""
    if not isinstance(value, str):
        return None, "package must be a string"
    name = value.strip()
    if name == "":
        return None, "package must not be empty"
    if re.match(package_pattern, name) is None:
        return None, "package has bad characters: " + name
    if mode == "real":
        parts = name.split(":")
        if len(parts) != gav_parts or "" in parts:
            return None, "package must be group:artifact:version"
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
    package, bad = check_package(data["package"], mode)
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


def local_name(tag):
    """Оставить у тега только имя без namespace."""
    if "}" in tag:
        return tag.split("}")[1]
    return tag


def find_child(node, name):
    """Найти первого ребенка с нужным именем."""
    for kid in node:
        if local_name(kid.tag) == name:
            return kid
    return None


def get_text(node, name):
    """Взять текст ребенка или пустую строку."""
    kid = find_child(node, name)
    if kid is None or kid.text is None:
        return ""
    return kid.text.strip()


def read_properties(root):
    """Собрать свойства POM в словарь."""
    props = {}
    node = find_child(root, "properties")
    if node is None:
        return props
    for kid in node:
        if kid.text is not None:
            props[local_name(kid.tag)] = kid.text.strip()
    return props


def substitute(text, props):
    """Подставить свойства в строку."""
    result = text
    for _ in range(max_subst):
        old = result
        for key in props:
            result = result.replace("${" + key + "}", props[key])
        if result == old:
            break
    return result


def project_value(root, name, props):
    """Взять значение проекта, учитывая parent."""
    text = get_text(root, name)
    if text != "":
        return substitute(text, props)
    parent = find_child(root, "parent")
    if parent is None:
        return ""
    return substitute(get_text(parent, name), props)


def fill_project_props(root, props):
    """Дописать координаты проекта в свойства."""
    group = project_value(root, "groupId", props)
    artifact = project_value(root, "artifactId", props)
    version = project_value(root, "version", props)
    props["project.groupId"] = group
    props["project.artifactId"] = artifact
    props["project.version"] = version
    props["pom.groupId"] = group
    props["pom.artifactId"] = artifact
    props["pom.version"] = version


def managed_versions(root, props):
    """Собрать версии из dependencyManagement."""
    result = {}
    node = find_child(root, "dependencyManagement")
    if node is None:
        return result
    deps = find_child(node, "dependencies")
    if deps is None:
        return result
    for kid in deps:
        if local_name(kid.tag) != "dependency":
            continue
        group = substitute(get_text(kid, "groupId"), props)
        artifact = substitute(get_text(kid, "artifactId"), props)
        version = substitute(get_text(kid, "version"), props)
        if group != "" and artifact != "" and version != "":
            result[group + ":" + artifact] = version
    return result


def make_dependency(node, props, managed):
    """Собрать одну прямую зависимость."""
    group = substitute(get_text(node, "groupId"), props)
    artifact = substitute(get_text(node, "artifactId"), props)
    version = substitute(get_text(node, "version"), props)
    if version == "":
        version = managed.get(group + ":" + artifact, "")
    if group == "" or artifact == "":
        return None
    if version == "":
        return group + ":" + artifact
    return group + ":" + artifact + ":" + version


def read_dependencies(root, props, managed):
    """Прочитать прямые зависимости из POM."""
    node = find_child(root, "dependencies")
    if node is None:
        return []
    deps = []
    for kid in node:
        if local_name(kid.tag) != "dependency":
            continue
        dep = make_dependency(kid, props, managed)
        if dep is not None:
            deps.append(dep)
    return deps


def parse_pom(text):
    """Разобрать POM и вернуть прямые зависимости."""
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, ValueError):
        return None, "bad POM: bad XML"
    props = read_properties(root)
    fill_project_props(root, props)
    managed = managed_versions(root, props)
    return read_dependencies(root, props, managed), None


def build_pom_url(repo, group, artifact, version):
    """Собрать URL файла POM в Maven-репозитории."""
    base = repo.rstrip("/")
    group_path = group.replace(".", "/")
    name = artifact + "-" + version + ".pom"
    path = group_path + "/" + artifact + "/" + version + "/" + name
    return base + "/" + path


def download_text(url):
    """Скачать текст по URL."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == http_not_found:
            return None, "package not found in repository"
        return None, "cannot download POM: HTTP " + str(exc.code)
    except (urllib.error.URLError, OSError):
        return None, "cannot download POM: " + url
    try:
        return data.decode("utf-8"), None
    except UnicodeError:
        return None, "cannot download POM: bad encoding"


def read_test_graph(params):
    """Прочитать прямые зависимости из тестового файла."""
    path = params["repository"]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except (OSError, UnicodeError):
        return None, "cannot read test repository: " + path
    target = params["package"]
    for line in lines:
        parts = line.split()
        if parts == [] or parts[0].startswith("#"):
            continue
        if parts[0] == target:
            return parts[1:], None
    return None, "package not found in test repository: " + target


def fetch_real_deps(params):
    """Получить прямые зависимости из Maven-репозитория."""
    parts = params["package"].split(":")
    if len(parts) != gav_parts:
        return None, "package must be group:artifact:version"
    group, artifact, version = parts
    url = build_pom_url(params["repository"], group, artifact, version)
    text, bad = download_text(url)
    if bad is not None:
        return None, bad
    return parse_pom(text)


def get_direct_deps(params):
    """Получить прямые зависимости по режиму."""
    if params["repository_mode"] == "test":
        return read_test_graph(params)
    return fetch_real_deps(params)


def show_deps(deps):
    """Напечатать зависимости по одной в строке."""
    if deps == []:
        print("no dependencies")
        return
    for dep in deps:
        print(dep)


def show_params(params):
    """Напечатать параметры в формате ключ-значение."""
    for key in param_keys:
        value = params[key]
        if isinstance(value, bool):
            value = str(value).lower()
        print(key + "=" + str(value))


def parse_args(argv):
    """Разобрать параметры командной строки."""
    opts = {"config": default_config, "show": False}
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--config" or arg == "-c":
            next_index = index + step
            if next_index >= len(argv):
                return None, "option needs a value: " + arg
            opts["config"] = argv[next_index]
            index = next_index + step
        elif arg == "--show-config":
            opts["show"] = True
            index = index + step
        else:
            return None, "unknown argument: " + arg
    return opts, None


def main(argv=None):
    """Точка входа приложения."""
    if argv is None:
        argv = sys.argv[1:]
    if "-h" in argv or "--help" in argv:
        print(usage)
        return 0
    opts, bad = parse_args(argv)
    if bad is not None:
        print("error: " + bad, file=sys.stderr)
        print(usage, file=sys.stderr)
        return 1
    data, bad = load_config(opts["config"])
    if bad is not None:
        print("error: " + bad, file=sys.stderr)
        return 1
    params, bad = check_params(data)
    if bad is not None:
        print("error: " + bad, file=sys.stderr)
        return 1
    if opts["show"]:
        show_params(params)
        return 0
    deps, bad = get_direct_deps(params)
    if bad is not None:
        print("error: " + bad, file=sys.stderr)
        return 1
    show_deps(deps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
