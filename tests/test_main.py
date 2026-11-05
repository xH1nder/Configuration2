"""Тесты первого и второго этапов."""

import contextlib
import io
import os
import pathlib
import tempfile
import unittest

from src.main import build_pom_url, check_depth, check_keys
from src.main import check_mode, check_package, check_params
from src.main import check_repository, check_tree, download_text
from src.main import fetch_real_deps, get_direct_deps, load_config
from src.main import main, parse_args, parse_pom, read_test_graph
from src.main import show_deps, show_params


def good_config():
    """Собрать правильный конфиг."""
    return {
        "package": "org.example:app:1.0",
        "repository": "https://repo1.maven.org/maven2",
        "repository_mode": "real",
        "ascii_tree": True,
        "max_depth": 3,
    }


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


SIMPLE_POM = (
    '<project xmlns="http://maven.apache.org/POM/4.0.0">'
    "<properties><hamcrest.version>1.3</hamcrest.version></properties>"
    "<dependencies>"
    "<dependency><groupId>org.hamcrest</groupId>"
    "<artifactId>hamcrest-core</artifactId>"
    "<version>${hamcrest.version}</version></dependency>"
    "</dependencies>"
    "</project>"
)

MANAGED_POM = (
    '<project xmlns="http://maven.apache.org/POM/4.0.0">'
    "<dependencyManagement><dependencies>"
    "<dependency><groupId>org.example</groupId>"
    "<artifactId>lib</artifactId><version>2.0</version></dependency>"
    "</dependencies></dependencyManagement>"
    "<dependencies><dependency><groupId>org.example</groupId>"
    "<artifactId>lib</artifactId></dependency></dependencies>"
    "</project>"
)

PARENT_POM = (
    '<project xmlns="http://maven.apache.org/POM/4.0.0">'
    "<parent><groupId>org.example</groupId>"
    "<artifactId>parent</artifactId><version>1.0</version></parent>"
    "<artifactId>child</artifactId>"
    "<dependencies><dependency><groupId>org.example</groupId>"
    "<artifactId>lib</artifactId>"
    "<version>${project.version}</version></dependency></dependencies>"
    "</project>"
)


class TestLoadConfig(unittest.TestCase):
    """Проверка чтения YAML."""

    def test_good(self):
        """Хороший конфиг читается."""
        path = write_file("package: app\n", ".yaml")
        data, bad = load_config(path)
        remove_file(path)
        self.assertEqual(data["package"], "app")
        self.assertIsNone(bad)

    def test_missing(self):
        """Нет файла конфига."""
        path = os.path.join(tempfile.gettempdir(), "no_such_config.yaml")
        data, bad = load_config(path)
        self.assertIsNone(data)
        self.assertIn("cannot read config", bad)

    def test_bad_yaml(self):
        """Кривой YAML не читается."""
        path = write_file("package: [\n", ".yaml")
        data, bad = load_config(path)
        remove_file(path)
        self.assertIsNone(data)
        self.assertIn("bad YAML", bad)

    def test_empty(self):
        """Пустой конфиг не читается."""
        path = write_file("", ".yaml")
        data, bad = load_config(path)
        remove_file(path)
        self.assertIsNone(data)
        self.assertIn("empty", bad)

    def test_not_mapping(self):
        """Список вместо словаря не подходит."""
        path = write_file("- one\n- two\n", ".yaml")
        data, bad = load_config(path)
        remove_file(path)
        self.assertIsNone(data)
        self.assertIn("mapping", bad)


class TestCheckPackage(unittest.TestCase):
    """Проверка имени пакета."""

    def test_good(self):
        """Координаты group:artifact:version подходят."""
        value, bad = check_package("org.example:app:1.0", "real")
        self.assertEqual(value, "org.example:app:1.0")
        self.assertIsNone(bad)

    def test_spaces(self):
        """Пробелы вокруг имени убираются."""
        value, bad = check_package(" org.example:app:1.0 ", "real")
        self.assertEqual(value, "org.example:app:1.0")
        self.assertIsNone(bad)

    def test_empty(self):
        """Пустое имя не подходит."""
        value, bad = check_package("  ", "real")
        self.assertIsNone(value)
        self.assertIn("empty", bad)

    def test_type(self):
        """Число вместо имени не подходит."""
        value, bad = check_package(19, "real")
        self.assertIsNone(value)
        self.assertIn("string", bad)

    def test_bad_chars(self):
        """Плохие символы в имени не подходят."""
        value, bad = check_package("bad name:app:1.0", "real")
        self.assertIsNone(value)
        self.assertIn("bad characters", bad)

    def test_no_version(self):
        """Без версии пакет не подходит."""
        value, bad = check_package("org.example:app", "real")
        self.assertIsNone(value)
        self.assertIn("group:artifact:version", bad)

    def test_empty_part(self):
        """Пустая часть координат не подходит."""
        value, bad = check_package("org.example::1.0", "real")
        self.assertIsNone(value)
        self.assertIn("group:artifact:version", bad)

    def test_test_mode(self):
        """В режиме test хватает имени A."""
        value, bad = check_package("A", "test")
        self.assertEqual(value, "A")
        self.assertIsNone(bad)


class TestCheckMode(unittest.TestCase):
    """Проверка режима репозитория."""

    def test_good(self):
        """Режимы real и test подходят."""
        self.assertEqual(check_mode("real"), ("real", None))
        self.assertEqual(check_mode("test"), ("test", None))

    def test_bad(self):
        """Другой режим не подходит."""
        value, bad = check_mode("online")
        self.assertIsNone(value)
        self.assertIn("real or test", bad)


class TestCheckRepository(unittest.TestCase):
    """Проверка URL и файла репозитория."""

    def test_url(self):
        """Хороший URL подходит."""
        value, bad = check_repository(
            "https://repo1.maven.org/maven2", "real")
        self.assertEqual(value, "https://repo1.maven.org/maven2")
        self.assertIsNone(bad)

    def test_bad_scheme(self):
        """FTP не подходит."""
        value, bad = check_repository("ftp://example.com/repo", "real")
        self.assertIsNone(value)
        self.assertIn("http", bad)

    def test_no_host(self):
        """URL без хоста не подходит."""
        value, bad = check_repository("https://", "real")
        self.assertIsNone(value)
        self.assertIn("no host", bad)

    def test_spaces(self):
        """Пробелы в URL не подходят."""
        value, bad = check_repository("https://exa mple.com", "real")
        self.assertIsNone(value)
        self.assertIn("spaces", bad)

    def test_file(self):
        """Существующий файл подходит."""
        path = os.path.abspath(__file__)
        value, bad = check_repository(path, "test")
        self.assertEqual(value, path)
        self.assertIsNone(bad)

    def test_no_file(self):
        """Нет файла тестового репозитория."""
        path = os.path.join(tempfile.gettempdir(), "no_repo_12345.txt")
        value, bad = check_repository(path, "test")
        self.assertIsNone(value)
        self.assertIn("not found", bad)

    def test_empty(self):
        """Пустой repository не подходит."""
        value, bad = check_repository("  ", "real")
        self.assertIsNone(value)
        self.assertIn("empty", bad)

    def test_type(self):
        """Число вместо repository не подходит."""
        value, bad = check_repository(3, "real")
        self.assertIsNone(value)
        self.assertIn("string", bad)


class TestCheckTree(unittest.TestCase):
    """Проверка ASCII-дерева."""

    def test_good(self):
        """True и False подходят."""
        self.assertEqual(check_tree(True), (True, None))
        self.assertEqual(check_tree(False), (False, None))

    def test_bad(self):
        """Строка не подходит."""
        value, bad = check_tree("yes")
        self.assertIsNone(value)
        self.assertIn("true or false", bad)


class TestCheckDepth(unittest.TestCase):
    """Проверка максимальной глубины."""

    def test_good(self):
        """Границы 1 и 100 подходят."""
        self.assertEqual(check_depth(1), (1, None))
        self.assertEqual(check_depth(100), (100, None))

    def test_zero(self):
        """Ноль не подходит."""
        value, bad = check_depth(0)
        self.assertIsNone(value)
        self.assertIn("from 1 to 100", bad)

    def test_big(self):
        """101 не подходит."""
        value, bad = check_depth(101)
        self.assertIsNone(value)
        self.assertIn("from 1 to 100", bad)

    def test_type(self):
        """Строка не подходит."""
        value, bad = check_depth("3")
        self.assertIsNone(value)
        self.assertIn("integer", bad)

    def test_bool(self):
        """True не считается числом."""
        value, bad = check_depth(True)
        self.assertIsNone(value)
        self.assertIn("integer", bad)


class TestCheckKeys(unittest.TestCase):
    """Проверка набора ключей."""

    def test_good(self):
        """Все ключи на месте."""
        self.assertIsNone(check_keys(good_config()))

    def test_missing(self):
        """Нет max_depth."""
        data = good_config()
        del data["max_depth"]
        bad = check_keys(data)
        self.assertIn("missing parameter: max_depth", bad)

    def test_unknown(self):
        """Лишний ключ не подходит."""
        data = good_config()
        data["depth"] = 3
        bad = check_keys(data)
        self.assertIn("unknown parameter: depth", bad)


class TestCheckParams(unittest.TestCase):
    """Проверка всего конфига."""

    def test_good(self):
        """Правильный конфиг проверяется."""
        params, bad = check_params(good_config())
        self.assertIsNone(bad)
        self.assertEqual(params["package"], "org.example:app:1.0")
        self.assertTrue(params["ascii_tree"])

    def test_bad_package(self):
        """Плохой package дает ошибку."""
        data = good_config()
        data["package"] = ""
        params, bad = check_params(data)
        self.assertIsNone(params)
        self.assertIn("package", bad)

    def test_bad_package_format(self):
        """В real нужны три части координат."""
        data = good_config()
        data["package"] = "junit"
        params, bad = check_params(data)
        self.assertIsNone(params)
        self.assertIn("group:artifact:version", bad)

    def test_bad_repository(self):
        """Плохой repository дает ошибку."""
        data = good_config()
        data["repository"] = "ftp://example.com"
        params, bad = check_params(data)
        self.assertIsNone(params)
        self.assertIn("http", bad)

    def test_bad_mode(self):
        """Плохой режим дает ошибку."""
        data = good_config()
        data["repository_mode"] = "online"
        params, bad = check_params(data)
        self.assertIsNone(params)
        self.assertIn("real or test", bad)

    def test_bad_tree(self):
        """Плохой ascii_tree дает ошибку."""
        data = good_config()
        data["ascii_tree"] = "yes"
        params, bad = check_params(data)
        self.assertIsNone(params)
        self.assertIn("true or false", bad)

    def test_bad_depth(self):
        """Плохая глубина дает ошибку."""
        data = good_config()
        data["max_depth"] = 0
        params, bad = check_params(data)
        self.assertIsNone(params)
        self.assertIn("from 1 to 100", bad)

    def test_test_mode(self):
        """В режиме test проверяется файл."""
        data = good_config()
        data["repository_mode"] = "test"
        data["repository"] = os.path.abspath(__file__)
        params, bad = check_params(data)
        self.assertIsNone(bad)
        self.assertEqual(params["repository_mode"], "test")


class TestShowParams(unittest.TestCase):
    """Проверка вывода параметров."""

    def test_output(self):
        """Параметры печатаются по порядку."""
        params, bad = check_params(good_config())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_params(params)
        lines = out.getvalue().splitlines()
        repo = "repository=https://repo1.maven.org/maven2"
        self.assertEqual(lines[0], "package=org.example:app:1.0")
        self.assertEqual(lines[1], repo)
        self.assertEqual(lines[2], "repository_mode=real")
        self.assertEqual(lines[3], "ascii_tree=true")
        self.assertEqual(lines[4], "max_depth=3")
        self.assertEqual(len(lines), 5)


class TestParseArgs(unittest.TestCase):
    """Проверка аргументов командной строки."""

    def test_default(self):
        """Без аргументов берется config.yaml."""
        opts, bad = parse_args([])
        self.assertEqual(opts["config"], "config.yaml")
        self.assertFalse(opts["show"])
        self.assertFalse(opts["direct"])
        self.assertFalse(opts["order"])
        self.assertIsNone(bad)

    def test_long(self):
        """Длинный параметр --config."""
        opts, bad = parse_args(["--config", "my.yaml"])
        self.assertEqual(opts["config"], "my.yaml")
        self.assertIsNone(bad)

    def test_short(self):
        """Короткий параметр -c."""
        opts, bad = parse_args(["-c", "my.yaml"])
        self.assertEqual(opts["config"], "my.yaml")
        self.assertIsNone(bad)

    def test_show(self):
        """Флаг --show-config включается."""
        opts, bad = parse_args(["--show-config"])
        self.assertTrue(opts["show"])
        self.assertIsNone(bad)

    def test_direct(self):
        """Флаг --direct включается."""
        opts, bad = parse_args(["--direct"])
        self.assertTrue(opts["direct"])
        self.assertIsNone(bad)

    def test_order(self):
        """Флаг --order включается."""
        opts, bad = parse_args(["--order"])
        self.assertTrue(opts["order"])
        self.assertIsNone(bad)

    def test_direct_order_conflict(self):
        """--direct и --order нельзя использовать вместе."""
        opts, bad = parse_args(["--direct", "--order"])
        self.assertIsNone(opts)
        self.assertIn("cannot be used together", bad)

    def test_no_value(self):
        """--config без значения ошибка."""
        opts, bad = parse_args(["--config"])
        self.assertIsNone(opts)
        self.assertIn("needs a value", bad)

    def test_unknown(self):
        """Неизвестный аргумент ошибка."""
        opts, bad = parse_args(["--vfs", "v.json"])
        self.assertIsNone(opts)
        self.assertIn("unknown argument", bad)


class TestMain(unittest.TestCase):
    """Проверка запуска приложения."""

    def test_show_config(self):
        """Флаг --show-config печатает параметры без сети."""
        path = write_file(
            "package: org.example:app:1.0\n"
            "repository: https://example.com\n"
            "repository_mode: real\n"
            "ascii_tree: false\n"
            "max_depth: 2\n",
            ".yaml")
        code, out, err = run_main(["--config", path, "--show-config"])
        remove_file(path)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("package=org.example:app:1.0", out)
        self.assertIn("ascii_tree=false", out)

    def test_test_mode(self):
        """В режиме test печатается весь граф зависимостей."""
        graph = write_file("A B C\nB D\nC D\n", ".txt")
        path = write_file(
            "package: A\n"
            "repository: " + graph + "\n"
            "repository_mode: test\n"
            "ascii_tree: false\n"
            "max_depth: 2\n",
            ".yaml")
        code, out, err = run_main(["--config", path])
        remove_file(path)
        remove_file(graph)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        expected = "A -> B\nA -> C\nB -> D\nC -> D\n"
        self.assertEqual(out, expected)

    def test_direct_mode(self):
        """Флаг --direct печатает только соседей."""
        graph = write_file("A B C\nB D\nC D\n", ".txt")
        path = write_file(
            "package: A\n"
            "repository: " + graph + "\n"
            "repository_mode: test\n"
            "ascii_tree: false\n"
            "max_depth: 2\n",
            ".yaml")
        code, out, err = run_main(["--config", path, "--direct"])
        remove_file(path)
        remove_file(graph)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(out, "B\nC\n")

    def test_cycle(self):
        """Цикл не приводит к зацикливанию."""
        graph = write_file("X Y\nY X\n", ".txt")
        path = write_file(
            "package: X\n"
            "repository: " + graph + "\n"
            "repository_mode: test\n"
            "ascii_tree: false\n"
            "max_depth: 3\n",
            ".yaml")
        code, out, err = run_main(["--config", path])
        remove_file(path)
        remove_file(graph)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        expected = "X -> Y\nY -> X\ncycle: X -> Y -> X\n"
        self.assertEqual(out, expected)

    def test_no_deps(self):
        """Пакет без зависимостей так и пишется."""
        graph = write_file("A\n", ".txt")
        path = write_file(
            "package: A\n"
            "repository: " + graph + "\n"
            "repository_mode: test\n"
            "ascii_tree: false\n"
            "max_depth: 2\n",
            ".yaml")
        code, out, err = run_main(["--config", path])
        remove_file(path)
        remove_file(graph)
        self.assertEqual(code, 0)
        self.assertEqual(out, "no dependencies\n")

    def test_missing_config(self):
        """Нет конфига возвращает код 1."""
        path = os.path.join(tempfile.gettempdir(), "no_such_cfg_2.yaml")
        code, out, err = run_main(["--config", path])
        self.assertEqual(code, 1)
        self.assertIn("cannot read config", err)

    def test_bad_param(self):
        """Плохой параметр возвращает код 1."""
        path = write_file(
            "package: junit:junit:4.13.2\n"
            "repository: https://example.com\n"
            "repository_mode: real\n"
            "ascii_tree: true\n"
            "max_depth: 0\n",
            ".yaml")
        code, out, err = run_main(["--config", path])
        remove_file(path)
        self.assertEqual(code, 1)
        self.assertIn("max_depth", err)
        self.assertEqual(out, "")

    def test_help(self):
        """Help возвращает код 0."""
        code, out, err = run_main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("usage", out)

    def test_bad_arg(self):
        """Неизвестный аргумент возвращает код 1."""
        code, out, err = run_main(["--nope"])
        self.assertEqual(code, 1)
        self.assertIn("unknown argument", err)
        self.assertIn("usage", err)


class TestPom(unittest.TestCase):
    """Проверка разбора POM."""

    def test_simple(self):
        """Свойство версии подставляется."""
        deps, bad = parse_pom(SIMPLE_POM)
        self.assertIsNone(bad)
        self.assertEqual(deps, ["org.hamcrest:hamcrest-core:1.3"])

    def test_managed(self):
        """Версия берется из dependencyManagement."""
        deps, bad = parse_pom(MANAGED_POM)
        self.assertIsNone(bad)
        self.assertEqual(deps, ["org.example:lib:2.0"])

    def test_parent_version(self):
        """Версия проекта берется из parent."""
        deps, bad = parse_pom(PARENT_POM)
        self.assertIsNone(bad)
        self.assertEqual(deps, ["org.example:lib:1.0"])

    def test_no_deps(self):
        """POM без зависимостей дает пустой список."""
        text = '<project xmlns="http://maven.apache.org/POM/4.0.0"/>'
        deps, bad = parse_pom(text)
        self.assertIsNone(bad)
        self.assertEqual(deps, [])

    def test_bad_xml(self):
        """Кривой XML не разбирается."""
        deps, bad = parse_pom("<project>")
        self.assertIsNone(deps)
        self.assertIn("bad POM", bad)


class TestBuildUrl(unittest.TestCase):
    """Проверка URL файла POM."""

    def test_simple(self):
        """Точки группы заменяются на слэши."""
        url = build_pom_url(
            "https://repo1.maven.org/maven2",
            "org.apache.commons",
            "commons-lang3",
            "3.14.0")
        self.assertEqual(
            url,
            "https://repo1.maven.org/maven2/org/apache/commons/"
            "commons-lang3/3.14.0/commons-lang3-3.14.0.pom")

    def test_slash(self):
        """Слэш в конце репозитория не мешает."""
        url = build_pom_url(
            "https://repo.test/maven2/", "junit", "junit", "4.13.2")
        self.assertEqual(
            url,
            "https://repo.test/maven2/junit/junit/4.13.2/"
            "junit-4.13.2.pom")


class TestDownload(unittest.TestCase):
    """Проверка скачивания POM."""

    def test_file_url(self):
        """Локальный file URL читается."""
        path = write_file(SIMPLE_POM, ".pom")
        url = pathlib.Path(path).as_uri()
        text, bad = download_text(url)
        remove_file(path)
        self.assertIsNone(bad)
        self.assertIn("hamcrest", text)

    def test_missing(self):
        """Нет файла по URL."""
        path = os.path.join(tempfile.gettempdir(), "no_pom_12345.pom")
        url = pathlib.Path(path).as_uri()
        text, bad = download_text(url)
        self.assertIsNone(text)
        self.assertIn("cannot download", bad)

    def test_bad_encoding(self):
        """Битый UTF-8 не читается."""
        path = os.path.join(tempfile.gettempdir(), "bad_enc.pom")
        with open(path, "wb") as fh:
            fh.write(b"\xff\xfe")
        url = pathlib.Path(path).as_uri()
        text, bad = download_text(url)
        remove_file(path)
        self.assertIsNone(text)
        self.assertIn("bad encoding", bad)


class TestTestGraph(unittest.TestCase):
    """Проверка тестового графа."""

    def test_direct(self):
        """Прямые зависимости берутся из строки пакета."""
        path = write_file("# comment\nA B C\nB D\n\nD\n", ".txt")
        params = {"package": "A", "repository": path}
        deps, bad = read_test_graph(params)
        remove_file(path)
        self.assertIsNone(bad)
        self.assertEqual(deps, ["B", "C"])

    def test_empty(self):
        """Пакет без соседей дает пустой список."""
        path = write_file("A\n", ".txt")
        params = {"package": "A", "repository": path}
        deps, bad = read_test_graph(params)
        remove_file(path)
        self.assertIsNone(bad)
        self.assertEqual(deps, [])

    def test_missing_package(self):
        """Нет пакета в графе."""
        path = write_file("A B\n", ".txt")
        params = {"package": "Z", "repository": path}
        deps, bad = read_test_graph(params)
        remove_file(path)
        self.assertIsNone(deps)
        self.assertIn("not found", bad)

    def test_missing_file(self):
        """Нет файла графа."""
        path = os.path.join(tempfile.gettempdir(), "no_graph_12345.txt")
        params = {"package": "A", "repository": path}
        deps, bad = read_test_graph(params)
        self.assertIsNone(deps)
        self.assertIn("cannot read", bad)


class TestShowDeps(unittest.TestCase):
    """Проверка вывода зависимостей."""

    def test_list(self):
        """Список печатается по строкам."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_deps(["a:b:1", "c:d:2"])
        self.assertEqual(out.getvalue(), "a:b:1\nc:d:2\n")

    def test_empty(self):
        """Пустой список печатает no dependencies."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_deps([])
        self.assertEqual(out.getvalue(), "no dependencies\n")


class TestFetchReal(unittest.TestCase):
    """Проверка получения зависимостей."""

    def test_bad_package(self):
        """Без версии fetch_real_deps дает ошибку."""
        params = {
            "package": "junit:junit",
            "repository": "https://repo1.maven.org/maven2",
        }
        deps, bad = fetch_real_deps(params)
        self.assertIsNone(deps)
        self.assertIn("group:artifact:version", bad)


class TestGetDirectDeps(unittest.TestCase):
    """Проверка выбора режима."""

    def test_test_mode(self):
        """В режиме test используется файл."""
        path = write_file("A B\n", ".txt")
        params = {
            "package": "A",
            "repository": path,
            "repository_mode": "test",
        }
        deps, bad = get_direct_deps(params)
        remove_file(path)
        self.assertIsNone(bad)
        self.assertEqual(deps, ["B"])


if __name__ == "__main__":
    unittest.main()
