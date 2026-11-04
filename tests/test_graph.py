"""Тесты третьего этапа: граф зависимостей."""

import contextlib
import io
import os
import pathlib
import shutil
import tempfile
import unittest

from src.main import build_graph, check_test_name
from src.main import fetch_node_deps, load_test_repo
from src.main import show_graph, walk_graph


def write_file(text, suffix):
    """Записать временный файл и вернуть путь."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8")
    tmp.write(text)
    tmp.close()
    return tmp.name


def remove_file(path):
    """Удалить временный файл без падения."""
    try:
        os.remove(path)
    except OSError:
        pass


def make_pom(deps):
    """Собрать простой POM с зависимостями."""
    body = ""
    for group, artifact, version in deps:
        body += (
            "<dependency><groupId>" + group + "</groupId>"
            "<artifactId>" + artifact + "</artifactId>"
            "<version>" + version + "</version></dependency>")
    return (
        '<project xmlns="http://maven.apache.org/POM/4.0.0">'
        "<dependencies>" + body + "</dependencies></project>")


def make_repo(root, group, artifact, version, deps):
    """Создать POM в локальном Maven-репозитории."""
    folder = os.path.join(root, *group.split("."), artifact, version)
    os.makedirs(folder, exist_ok=True)
    name = artifact + "-" + version + ".pom"
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        fh.write(make_pom(deps))


def test_params(package, depth=3):
    """Собрать параметры тестового режима."""
    return {
        "package": package,
        "repository": "test_repo.txt",
        "repository_mode": "test",
        "ascii_tree": False,
        "max_depth": depth,
    }


class TestCheckTestName(unittest.TestCase):
    """Проверка имен тестового графа."""

    def test_good(self):
        """Большие латинские буквы подходят."""
        self.assertIsNone(check_test_name("AB"))

    def test_bad(self):
        """Строчные буквы не подходят."""
        bad = check_test_name("Ab")
        self.assertIn("uppercase", bad)

    def test_digit(self):
        """Цифры не подходят."""
        bad = check_test_name("A1")
        self.assertIn("uppercase", bad)


class TestLoadTestRepo(unittest.TestCase):
    """Проверка чтения тестового графа."""

    def test_graph(self):
        """Комментарии и пустые строки пропускаются."""
        path = write_file("# comment\nA B C\nB D\n\n", ".txt")
        graph, bad = load_test_repo(path)
        remove_file(path)
        self.assertIsNone(bad)
        self.assertEqual(graph, {"A": ["B", "C"], "B": ["D"]})

    def test_bad_name(self):
        """Строчное имя пакета не подходит."""
        path = write_file("a B\n", ".txt")
        graph, bad = load_test_repo(path)
        remove_file(path)
        self.assertIsNone(graph)
        self.assertIn("uppercase", bad)

    def test_missing_file(self):
        """Нет файла графа."""
        path = os.path.join(tempfile.gettempdir(), "no_graph_2.txt")
        graph, bad = load_test_repo(path)
        self.assertIsNone(graph)
        self.assertIn("cannot read", bad)


class TestWalkGraph(unittest.TestCase):
    """Проверка обхода графа без рекурсии."""

    def test_branch(self):
        """Ветвление и общая зависимость обходятся один раз."""
        params = test_params("A")
        source = {
            "A": ["B", "C"],
            "B": ["D"],
            "C": ["D"],
            "D": [],
        }
        graph, cycles, bad = walk_graph("A", 5, params, source)
        self.assertIsNone(bad)
        self.assertEqual(cycles, [])
        self.assertEqual(graph["A"], ["B", "C"])
        self.assertEqual(graph["B"], ["D"])
        self.assertEqual(graph["C"], ["D"])
        self.assertEqual(graph["D"], [])
        self.assertEqual(len(graph), 4)

    def test_depth(self):
        """Глубина ограничивает обход."""
        params = test_params("P")
        source = {
            "P": ["Q"],
            "Q": ["R"],
            "R": ["S"],
            "S": ["T"],
            "T": [],
        }
        graph, cycles, bad = walk_graph("P", 2, params, source)
        self.assertIsNone(bad)
        self.assertEqual(cycles, [])
        self.assertEqual(graph, {"P": ["Q"], "Q": ["R"], "R": []})

    def test_cycle(self):
        """Цикл обнаруживается и не повторяется."""
        params = test_params("X")
        source = {"X": ["Y"], "Y": ["Z"], "Z": ["X"]}
        graph, cycles, bad = walk_graph("X", 10, params, source)
        self.assertIsNone(bad)
        self.assertEqual(graph["X"], ["Y"])
        self.assertEqual(graph["Y"], ["Z"])
        self.assertEqual(graph["Z"], ["X"])
        self.assertEqual(cycles, [["X", "Y", "Z", "X"]])

    def test_self_cycle(self):
        """Самозависимость считается циклом."""
        params = test_params("W")
        graph, cycles, bad = walk_graph("W", 5, params, {"W": ["W"]})
        self.assertIsNone(bad)
        self.assertEqual(graph, {"W": ["W"]})
        self.assertEqual(cycles, [["W", "W"]])

    def test_no_deps(self):
        """Пакет без зависимостей дает пустой граф."""
        params = test_params("A")
        graph, cycles, bad = walk_graph("A", 5, params, {"A": []})
        self.assertIsNone(bad)
        self.assertEqual(graph, {"A": []})
        self.assertEqual(cycles, [])

    def test_lower_depth(self):
        """Узел переобходится, если найден на меньшей глубине."""
        params = test_params("A")
        source = {
            "A": ["B", "D"],
            "B": ["C"],
            "C": ["D"],
            "D": ["E"],
            "E": [],
        }
        graph, cycles, bad = walk_graph("A", 2, params, source)
        self.assertIsNone(bad)
        self.assertEqual(cycles, [])
        self.assertEqual(graph["D"], ["E"])
        self.assertIn("E", graph)


class TestBuildGraph(unittest.TestCase):
    """Проверка построения графа по режиму."""

    def test_test_mode(self):
        """В режиме test граф читается из файла."""
        path = write_file("A B C\nB D\n", ".txt")
        params = test_params("A", 3)
        params["repository"] = path
        graph, cycles, bad = build_graph(params)
        remove_file(path)
        self.assertIsNone(bad)
        self.assertEqual(cycles, [])
        self.assertEqual(graph["A"], ["B", "C"])
        self.assertEqual(graph["B"], ["D"])

    def test_missing_root(self):
        """Нет начального пакета в файле."""
        path = write_file("A B\n", ".txt")
        params = test_params("Z", 3)
        params["repository"] = path
        graph, cycles, bad = build_graph(params)
        remove_file(path)
        self.assertIsNone(graph)
        self.assertIn("not found", bad)

    def test_bad_name(self):
        """Плохие имена в файле дают ошибку."""
        path = write_file("a B\n", ".txt")
        params = test_params("A", 3)
        params["repository"] = path
        graph, cycles, bad = build_graph(params)
        remove_file(path)
        self.assertIsNone(graph)
        self.assertIn("uppercase", bad)

    def test_real_local_repo(self):
        """Реальный режим работает с локальным file URL."""
        root = tempfile.mkdtemp()
        make_repo(
            root, "org.example", "a", "1.0",
            [("org.example", "b", "1.0")])
        make_repo(root, "org.example", "b", "1.0", [])
        params = {
            "package": "org.example:a:1.0",
            "repository": pathlib.Path(root).as_uri(),
            "repository_mode": "real",
            "ascii_tree": False,
            "max_depth": 5,
        }
        graph, cycles, bad = build_graph(params)
        shutil.rmtree(root, ignore_errors=True)
        self.assertIsNone(bad)
        self.assertEqual(cycles, [])
        self.assertEqual(
            graph["org.example:a:1.0"], ["org.example:b:1.0"])
        self.assertEqual(graph["org.example:b:1.0"], [])


class TestFetchNode(unittest.TestCase):
    """Проверка получения зависимостей одного узла."""

    def test_file_url(self):
        """POM читается из локального репозитория."""
        root = tempfile.mkdtemp()
        make_repo(
            root, "org.example", "a", "1.0",
            [("org.example", "b", "1.0")])
        deps, bad = fetch_node_deps(
            "org.example:a:1.0", pathlib.Path(root).as_uri())
        shutil.rmtree(root, ignore_errors=True)
        self.assertIsNone(bad)
        self.assertEqual(deps, ["org.example:b:1.0"])

    def test_no_version(self):
        """Неполные координаты дают пустой список."""
        deps, bad = fetch_node_deps(
            "org.example:a", "https://example.com")
        self.assertIsNone(bad)
        self.assertEqual(deps, [])


class TestShowGraph(unittest.TestCase):
    """Проверка вывода графа."""

    def test_edges(self):
        """Ребра печатаются по одному в строке."""
        graph = {
            "A": ["B", "C"],
            "B": ["D"],
            "C": ["D"],
            "D": [],
        }
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_graph(graph, [])
        expected = "A -> B\nA -> C\nB -> D\nC -> D\n"
        self.assertEqual(out.getvalue(), expected)

    def test_empty(self):
        """Граф без ребер печатает no dependencies."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_graph({"A": []}, [])
        self.assertEqual(out.getvalue(), "no dependencies\n")

    def test_cycle(self):
        """Цикл печатается после ребер."""
        graph = {"X": ["Y"], "Y": ["X"]}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_graph(graph, [["X", "Y", "X"]])
        expected = "X -> Y\nY -> X\ncycle: X -> Y -> X\n"
        self.assertEqual(out.getvalue(), expected)


if __name__ == "__main__":
    unittest.main()
