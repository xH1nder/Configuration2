"""Тесты пятого этапа: Mermaid и ASCII-дерево."""

import contextlib
import io
import os
import pathlib
import shutil
import tempfile
import unittest

from src.main import main, mermaid_ids, mermaid_lines
from src.main import parse_args, run_mermaid, show_mermaid, show_tree
from src.main import tree_lines


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


def run_main(argv):
    """Запустить main и вернуть код, stdout и stderr."""
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


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


BRANCH_MERMAID = (
    "graph TD\n"
    '    n0["A"]\n'
    '    n1["B"]\n'
    '    n2["D"]\n'
    '    n3["C"]\n'
    "    n0 --> n1\n"
    "    n0 --> n3\n"
    "    n1 --> n2\n"
    "    n3 --> n2\n"
)

BRANCH_TREE = (
    "A\n"
    "+-- B\n"
    "|   `-- D\n"
    "`-- C\n"
    "    `-- D (already shown)\n"
)


class TestMermaidIds(unittest.TestCase):
    """Проверка идентификаторов Mermaid."""

    def test_order(self):
        """Идентификаторы идут в порядке появления узлов."""
        graph = {"A": ["B", "C"], "B": ["D"], "D": [], "C": []}
        ids = mermaid_ids(graph)
        expected = {"A": "n0", "B": "n1", "D": "n2", "C": "n3"}
        self.assertEqual(ids, expected)

    def test_dangling(self):
        """Зависимость без своей записи тоже получает номер."""
        ids = mermaid_ids({"A": ["Z"]})
        self.assertEqual(ids, {"A": "n0", "Z": "n1"})

    def test_empty(self):
        """Пустой граф не получает идентификаторов."""
        self.assertEqual(mermaid_ids({}), {})


class TestMermaidLines(unittest.TestCase):
    """Проверка сборки Mermaid-описания."""

    def test_branch(self):
        """Узлы и ребра печатаются в порядке графа."""
        graph = {"A": ["B", "C"], "B": ["D"], "D": [], "C": ["D"]}
        self.assertEqual(mermaid_lines(graph), BRANCH_MERMAID.splitlines())

    def test_no_deps(self):
        """Граф без ребер содержит объявление корня."""
        graph = {"A": []}
        expected = ["graph TD", '    n0["A"]']
        self.assertEqual(mermaid_lines(graph), expected)

    def test_cycle(self):
        """Цикл задается обычным замыкающим ребром."""
        graph = {"X": ["Y"], "Y": ["Z"], "Z": ["X"]}
        lines = mermaid_lines(graph)
        self.assertIn("    n2 --> n0", lines)


class TestShowMermaid(unittest.TestCase):
    """Проверка вывода Mermaid."""

    def test_output(self):
        """Описание печатается целиком."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_mermaid({"A": []})
        self.assertEqual(out.getvalue(), 'graph TD\n    n0["A"]\n')


class TestTreeLines(unittest.TestCase):
    """Проверка сборки ASCII-дерева."""

    def test_branch(self):
        """Ветвление и общая зависимость помечаются."""
        graph = {"A": ["B", "C"], "B": ["D"], "D": [], "C": ["D"]}
        self.assertEqual(tree_lines("A", graph), BRANCH_TREE.splitlines())

    def test_chain(self):
        """Цепочка выводится с нарастающим отступом."""
        graph = {"P": ["Q"], "Q": ["R"], "R": []}
        expected = ["P", "`-- Q", "    `-- R"]
        self.assertEqual(tree_lines("P", graph), expected)

    def test_cycle(self):
        """Замыкание цикла помечается и не раскрывается."""
        graph = {"X": ["Y"], "Y": ["Z"], "Z": ["X"]}
        expected = ["X", "`-- Y", "    `-- Z", "        `-- X (cycle)"]
        self.assertEqual(tree_lines("X", graph), expected)

    def test_self_cycle(self):
        """Самозависимость сразу помечается как цикл."""
        self.assertEqual(tree_lines("W", {"W": ["W"]}),
                         ["W", "`-- W (cycle)"])

    def test_no_deps(self):
        """Пакет без зависимостей дает только корень."""
        self.assertEqual(tree_lines("A", {"A": []}), ["A"])

    def test_missing_node(self):
        """Неизвестный узел считается листом."""
        self.assertEqual(tree_lines("A", {}), ["A"])


class TestShowTree(unittest.TestCase):
    """Проверка вывода ASCII-дерева."""

    def test_output(self):
        """Дерево печатается по строкам."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_tree("A", {"A": ["B"], "B": []})
        self.assertEqual(out.getvalue(), "A\n`-- B\n")


class TestMermaidMain(unittest.TestCase):
    """Проверка режима --mermaid через main."""

    def test_ascii_false(self):
        """Без ascii_tree печатается только Mermaid."""
        graph = write_file("A B C\nB D\nC D\n", ".txt")
        path = write_file(
            "package: A\n"
            "repository: " + graph + "\n"
            "repository_mode: test\n"
            "ascii_tree: false\n"
            "max_depth: 3\n",
            ".yaml")
        code, out, err = run_main(["--config", path, "--mermaid"])
        remove_file(path)
        remove_file(graph)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(out, BRANCH_MERMAID)

    def test_ascii_true(self):
        """С ascii_tree печатаются Mermaid и дерево."""
        graph = write_file("A B C\nB D\nC D\n", ".txt")
        path = write_file(
            "package: A\n"
            "repository: " + graph + "\n"
            "repository_mode: test\n"
            "ascii_tree: true\n"
            "max_depth: 3\n",
            ".yaml")
        code, out, err = run_main(["--config", path, "--mermaid"])
        remove_file(path)
        remove_file(graph)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(out, BRANCH_MERMAID + "\n" + BRANCH_TREE)

    def test_cycle(self):
        """Цикл виден в Mermaid и в дереве."""
        graph = write_file("X Y\nY Z\nZ X\n", ".txt")
        path = write_file(
            "package: X\n"
            "repository: " + graph + "\n"
            "repository_mode: test\n"
            "ascii_tree: true\n"
            "max_depth: 10\n",
            ".yaml")
        code, out, err = run_main(["--config", path, "--mermaid"])
        remove_file(path)
        remove_file(graph)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("n2 --> n0", out)
        self.assertIn("`-- X (cycle)", out)

    def test_missing_package(self):
        """Ошибка графа возвращается и в режиме --mermaid."""
        graph = write_file("A B\n", ".txt")
        path = write_file(
            "package: M\n"
            "repository: " + graph + "\n"
            "repository_mode: test\n"
            "ascii_tree: true\n"
            "max_depth: 3\n",
            ".yaml")
        code, out, err = run_main(["--config", path, "--mermaid"])
        remove_file(path)
        remove_file(graph)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("not found", err)

    def test_real_local_repo(self):
        """Mermaid строится по локальному Maven-репозиторию."""
        root = tempfile.mkdtemp()
        make_repo(
            root, "org.example", "a", "1.0",
            [("org.example", "b", "1.0")])
        make_repo(root, "org.example", "b", "1.0", [])
        params = {
            "package": "org.example:a:1.0",
            "repository": pathlib.Path(root).as_uri(),
            "repository_mode": "real",
            "ascii_tree": True,
            "max_depth": 5,
        }
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            bad = run_mermaid(params)
        shutil.rmtree(root, ignore_errors=True)
        self.assertIsNone(bad)
        expected = (
            "graph TD\n"
            '    n0["org.example:a:1.0"]\n'
            '    n1["org.example:b:1.0"]\n'
            "    n0 --> n1\n"
            "\n"
            "org.example:a:1.0\n"
            "`-- org.example:b:1.0\n")
        self.assertEqual(out.getvalue(), expected)


class TestMermaidArgs(unittest.TestCase):
    """Проверка флагов этапа 5."""

    def test_flag(self):
        """Флаг --mermaid включается."""
        opts, bad = parse_args(["--mermaid"])
        self.assertIsNone(bad)
        self.assertTrue(opts["mermaid"])

    def test_direct_conflict(self):
        """--mermaid и --direct несовместимы."""
        opts, bad = parse_args(["--mermaid", "--direct"])
        self.assertIsNone(opts)
        self.assertIn("cannot be used together", bad)

    def test_order_conflict(self):
        """--mermaid и --order несовместимы."""
        opts, bad = parse_args(["--mermaid", "--order"])
        self.assertIsNone(opts)
        self.assertIn("cannot be used together", bad)


if __name__ == "__main__":
    unittest.main()
