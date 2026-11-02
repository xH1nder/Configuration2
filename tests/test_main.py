"""Тесты первого этапа."""

import contextlib
import io
import os
import tempfile
import unittest

from src.main import check_depth, check_keys, check_mode
from src.main import check_package, check_params, check_repository
from src.main import check_tree, load_config, main, parse_args
from src.main import show_params


def good_config():
    """Собрать правильный конфиг."""
    return {
        "package": "org.example:app",
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
        """Имя с группой и артефактом подходит."""
        value, bad = check_package("org.example:app")
        self.assertEqual(value, "org.example:app")
        self.assertIsNone(bad)

    def test_spaces(self):
        """Пробелы вокруг имени убираются."""
        value, bad = check_package(" app ")
        self.assertEqual(value, "app")
        self.assertIsNone(bad)

    def test_empty(self):
        """Пустое имя не подходит."""
        value, bad = check_package("  ")
        self.assertIsNone(value)
        self.assertIn("empty", bad)

    def test_type(self):
        """Число вместо имени не подходит."""
        value, bad = check_package(19)
        self.assertIsNone(value)
        self.assertIn("string", bad)

    def test_bad_chars(self):
        """Плохие символы в имени не подходят."""
        value, bad = check_package("bad name")
        self.assertIsNone(value)
        self.assertIn("bad characters", bad)


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
        self.assertEqual(params["package"], "org.example:app")
        self.assertTrue(params["ascii_tree"])

    def test_bad_package(self):
        """Плохой package дает ошибку."""
        data = good_config()
        data["package"] = ""
        params, bad = check_params(data)
        self.assertIsNone(params)
        self.assertIn("package", bad)

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
        self.assertEqual(lines[0], "package=org.example:app")
        self.assertEqual(lines[1], repo)
        self.assertEqual(lines[2], "repository_mode=real")
        self.assertEqual(lines[3], "ascii_tree=true")
        self.assertEqual(lines[4], "max_depth=3")
        self.assertEqual(len(lines), 5)


class TestParseArgs(unittest.TestCase):
    """Проверка аргументов командной строки."""

    def test_default(self):
        """Без аргументов берется config.yaml."""
        path, bad = parse_args([])
        self.assertEqual(path, "config.yaml")
        self.assertIsNone(bad)

    def test_long(self):
        """Длинный параметр --config."""
        path, bad = parse_args(["--config", "my.yaml"])
        self.assertEqual(path, "my.yaml")
        self.assertIsNone(bad)

    def test_short(self):
        """Короткий параметр -c."""
        path, bad = parse_args(["-c", "my.yaml"])
        self.assertEqual(path, "my.yaml")
        self.assertIsNone(bad)

    def test_no_value(self):
        """--config без значения ошибка."""
        path, bad = parse_args(["--config"])
        self.assertIsNone(path)
        self.assertIn("needs a value", bad)

    def test_unknown(self):
        """Неизвестный аргумент ошибка."""
        path, bad = parse_args(["--vfs", "v.json"])
        self.assertIsNone(path)
        self.assertIn("unknown argument", bad)


class TestMain(unittest.TestCase):
    """Проверка запуска приложения."""

    def test_good(self):
        """Правильный конфиг печатает параметры."""
        path = write_file(
            "package: app\n"
            "repository: https://example.com\n"
            "repository_mode: real\n"
            "ascii_tree: false\n"
            "max_depth: 2\n",
            ".yaml")
        code, out, err = run_main(["--config", path])
        remove_file(path)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("package=app", out)
        self.assertIn("ascii_tree=false", out)

    def test_missing_config(self):
        """Нет конфига возвращает код 1."""
        path = os.path.join(tempfile.gettempdir(), "no_such_cfg_2.yaml")
        code, out, err = run_main(["--config", path])
        self.assertEqual(code, 1)
        self.assertIn("cannot read config", err)

    def test_bad_param(self):
        """Плохой параметр возвращает код 1."""
        path = write_file(
            "package: app\n"
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


if __name__ == "__main__":
    unittest.main()
