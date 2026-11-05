"""Инструмент визуализации графа зависимостей. Этап 5."""

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
root_depth = 0
unseen_depth = max_depth_limit + step
frame_node = 0
frame_depth = 1
frame_deps = 2
frame_index = 3
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
test_name_pattern = r"^[A-Z]+$"
edge_sep = " -> "
cycle_prefix = "cycle: "
order_sep = ". "
order_start = 1
no_deps_text = "no dependencies"
mermaid_header = "graph TD"
mermaid_indent = "    "
mermaid_prefix = "n"
mermaid_arrow = " --> "
tree_kind = 0
tree_name = 1
tree_prefix = 2
tree_last_flag = 3
tree_enter = 0
tree_exit = 1
tree_branch = "+-- "
tree_end = "`-- "
tree_pipe = "|   "
tree_space = "    "
tree_cycle = " (cycle)"
tree_repeat = " (already shown)"
usage = ("usage: run.bat [--config PATH] [--show-config] "
         "[--direct] [--order] [--mermaid]")


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


def check_test_name(name):
    """Проверить имя пакета тестового графа."""
    if re.match(test_name_pattern, name) is None:
        return "test repository names must be uppercase Latin letters"
    return None


def load_test_repo(path):
    """Прочитать тестовый граф в словарь смежности."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except (OSError, UnicodeError):
        return None, "cannot read test repository: " + path
    graph = {}
    for line in lines:
        parts = line.split()
        if parts == [] or parts[0].startswith("#"):
            continue
        for name in parts:
            bad = check_test_name(name)
            if bad is not None:
                return None, bad
        graph[parts[0]] = parts[1:]
    return graph, None


def read_test_graph(params):
    """Прочитать прямые зависимости из тестового файла."""
    graph, bad = load_test_repo(params["repository"])
    if bad is not None:
        return None, bad
    target = params["package"]
    if target not in graph:
        return None, "package not found in test repository: " + target
    return graph[target], None


def fetch_node_deps(node, repo):
    """Получить прямые зависимости одного Maven-пакета."""
    parts = node.split(":")
    if len(parts) != gav_parts:
        return [], None
    group, artifact, version = parts
    url = build_pom_url(repo, group, artifact, version)
    text, bad = download_text(url)
    if bad is not None:
        return None, bad
    return parse_pom(text)


def fetch_real_deps(params):
    """Получить прямые зависимости из Maven-репозитория."""
    parts = params["package"].split(":")
    if len(parts) != gav_parts:
        return None, "package must be group:artifact:version"
    return fetch_node_deps(params["package"], params["repository"])


def get_direct_deps(params):
    """Получить прямые зависимости по режиму."""
    if params["repository_mode"] == "test":
        return read_test_graph(params)
    return fetch_real_deps(params)


def get_node_deps(params, test_graph, node):
    """Получить зависимости узла по режиму работы."""
    if params["repository_mode"] == "test":
        return test_graph.get(node, []), None
    return fetch_node_deps(node, params["repository"])


def make_cycle(stack, dep):
    """Собрать путь цикла по стеку DFS."""
    nodes = [frame[frame_node] for frame in stack]
    start = nodes.index(dep)
    return nodes[start:] + [dep]


def note_cycle(cycles, seen, stack, dep):
    """Записать цикл, если он еще не встречался."""
    cycle = make_cycle(stack, dep)
    key = tuple(cycle)
    if key in seen:
        return
    seen.add(key)
    cycles.append(cycle)


def read_frame_deps(params, test_graph, frame):
    """Прочитать зависимости узла для кадра стека."""
    if frame[frame_deps] is not None:
        return None
    deps, bad = get_node_deps(params, test_graph, frame[frame_node])
    if bad is not None:
        return bad
    frame[frame_deps] = deps
    return None


def take_depth(best, node, depth):
    """Запомнить глубину узла, если она меньше прежней."""
    if depth >= best.get(node, unseen_depth):
        return False
    best[node] = depth
    return True


def walk_graph(start, max_depth, params, test_graph):
    """Обойти граф зависимостей в глубину без рекурсии."""
    graph = {start: []}
    best = {start: root_depth}
    on_path = {start}
    cycles = []
    seen = set()
    stack = [[start, root_depth, None, 0]]
    while stack != []:
        frame = stack[-1]
        node = frame[frame_node]
        bad = read_frame_deps(params, test_graph, frame)
        if bad is not None:
            return None, None, bad
        deps = frame[frame_deps]
        if frame[frame_index] >= len(deps):
            on_path.discard(node)
            stack.pop()
            continue
        dep = deps[frame[frame_index]]
        frame[frame_index] += step
        if dep not in graph[node]:
            graph[node].append(dep)
        if dep in on_path:
            note_cycle(cycles, seen, stack, dep)
            continue
        next_depth = frame[frame_depth] + step
        if not take_depth(best, dep, next_depth):
            continue
        if dep not in graph:
            graph[dep] = []
        if next_depth >= max_depth:
            continue
        on_path.add(dep)
        stack.append([dep, next_depth, None, 0])
    return graph, cycles, None


def build_graph(params):
    """Построить граф зависимостей по режиму работы."""
    start = params["package"]
    test_graph = None
    if params["repository_mode"] == "test":
        test_graph, bad = load_test_repo(params["repository"])
        if bad is not None:
            return None, None, bad
        if start not in test_graph:
            return None, None, "package not found in test repository: " + start
    return walk_graph(start, params["max_depth"], params, test_graph)


def walk_order(start, graph):
    """Построить порядок загрузки пакета и зависимостей."""
    order = [start]
    seen = {start}
    stack = list(reversed(graph.get(start, [])))
    while stack != []:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        order.append(node)
        for dep in reversed(graph.get(node, [])):
            stack.append(dep)
    return order


def show_order(order):
    """Напечатать порядок загрузки зависимостей."""
    if order == []:
        print(no_deps_text)
        return
    for index, node in enumerate(order, order_start):
        print(str(index) + order_sep + node)


def mermaid_ids(graph):
    """Присвоить узлам графа короткие идентификаторы Mermaid."""
    ids = {}
    for node in graph:
        ids[node] = mermaid_prefix + str(len(ids))
    for node in graph:
        for dep in graph[node]:
            if dep not in ids:
                ids[dep] = mermaid_prefix + str(len(ids))
    return ids


def mermaid_lines(graph):
    """Собрать строки описания графа на языке Mermaid."""
    ids = mermaid_ids(graph)
    lines = [mermaid_header]
    for node in ids:
        text = ids[node] + '["' + node + '"]'
        lines.append(mermaid_indent + text)
    for node in graph:
        for dep in graph[node]:
            text = ids[node] + mermaid_arrow + ids[dep]
            lines.append(mermaid_indent + text)
    return lines


def show_mermaid(graph):
    """Напечатать описание графа на языке Mermaid."""
    for line in mermaid_lines(graph):
        print(line)


def push_tree_children(stack, node, prefix, graph):
    """Положить в стек детей узла в обратном порядке."""
    deps = graph.get(node, [])
    last = len(deps) - step
    for index in reversed(range(len(deps))):
        frame = [tree_enter, deps[index], prefix, index == last]
        stack.append(frame)


def tree_lines(start, graph):
    """Построить строки ASCII-дерева зависимостей."""
    lines = [start]
    expanded = {start}
    on_path = {start}
    stack = []
    push_tree_children(stack, start, "", graph)
    while stack != []:
        frame = stack.pop()
        node = frame[tree_name]
        if frame[tree_kind] == tree_exit:
            on_path.discard(node)
            continue
        prefix = frame[tree_prefix]
        is_last = frame[tree_last_flag]
        if is_last:
            line = prefix + tree_end + node
        else:
            line = prefix + tree_branch + node
        if node in on_path:
            lines.append(line + tree_cycle)
            continue
        if node in expanded:
            lines.append(line + tree_repeat)
            continue
        lines.append(line)
        expanded.add(node)
        on_path.add(node)
        stack.append([tree_exit, node, "", False])
        if is_last:
            prefix += tree_space
        else:
            prefix += tree_pipe
        push_tree_children(stack, node, prefix, graph)
    return lines


def show_tree(start, graph):
    """Напечатать ASCII-дерево зависимостей."""
    for line in tree_lines(start, graph):
        print(line)


def show_graph(graph, cycles):
    """Напечатать граф зависимостей и найденные циклы."""
    edges = 0
    for node in graph:
        for dep in graph[node]:
            print(node + edge_sep + dep)
            edges += step
    if not edges:
        print(no_deps_text)
    for cycle in cycles:
        print(cycle_prefix + edge_sep.join(cycle))


def show_deps(deps):
    """Напечатать зависимости по одной в строке."""
    if deps == []:
        print(no_deps_text)
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


def check_opts(opts):
    """Проверить совместимость флагов командной строки."""
    pairs = [
        ("direct", "order"),
        ("mermaid", "direct"),
        ("mermaid", "order"),
    ]
    for first, second in pairs:
        if opts[first] and opts[second]:
            text = "options --" + first + " and --" + second
            return text + " cannot be used together"
    return None


def parse_args(argv):
    """Разобрать параметры командной строки."""
    flags = {"--show-config": "show", "--direct": "direct",
             "--order": "order", "--mermaid": "mermaid"}
    opts = {"config": default_config, "show": False,
            "direct": False, "order": False, "mermaid": False}
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--config" or arg == "-c":
            next_index = index + step
            if next_index >= len(argv):
                return None, "option needs a value: " + arg
            opts["config"] = argv[next_index]
            index = next_index + step
        elif arg in flags:
            opts[flags[arg]] = True
            index = index + step
        else:
            return None, "unknown argument: " + arg
    bad = check_opts(opts)
    if bad is not None:
        return None, bad
    return opts, None


def run_direct(params):
    """Напечатать прямые зависимости пакета."""
    deps, bad = get_direct_deps(params)
    if bad is not None:
        return bad
    show_deps(deps)
    return None


def run_graph(params):
    """Построить и напечатать граф зависимостей."""
    graph, cycles, bad = build_graph(params)
    if bad is not None:
        return bad
    show_graph(graph, cycles)
    return None


def run_order(params):
    """Построить и напечатать порядок загрузки зависимостей."""
    graph, cycles, bad = build_graph(params)
    if bad is not None:
        return bad
    show_order(walk_order(params["package"], graph))
    return None


def run_mermaid(params):
    """Напечатать Mermaid-диаграмму и ASCII-дерево, если включено."""
    graph, _cycles, bad = build_graph(params)
    if bad is not None:
        return bad
    show_mermaid(graph)
    if not params["ascii_tree"]:
        return None
    print()
    show_tree(params["package"], graph)
    return None


def run_action(opts, params):
    """Выполнить действие, выбранное пользователем."""
    if opts["show"]:
        show_params(params)
        return 0
    if opts["direct"]:
        bad = run_direct(params)
    elif opts["order"]:
        bad = run_order(params)
    elif opts["mermaid"]:
        bad = run_mermaid(params)
    else:
        bad = run_graph(params)
    if bad is not None:
        print("error: " + bad, file=sys.stderr)
        return 1
    return 0


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
    return run_action(opts, params)


if __name__ == "__main__":
    sys.exit(main())
