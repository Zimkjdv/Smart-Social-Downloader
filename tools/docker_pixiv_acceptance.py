"""Run synthetic Pixiv path tests inside the reviewed network-disabled image."""
from .check_docker import clean_container, decode_json, ordinary, require

MODULES = ("tests.test_pixiv_paths",)
FILES = ("tests/__init__.py", "tests/helpers/__init__.py", "tests/helpers/pixiv.py",
         "tests/test_pixiv_paths.py")
EXPECTED_TESTS = 9


def validate(value, receipt):
    result = decode_json(value)
    require(isinstance(result, dict) and set(result) == {"receipt", "passed", "tests", "failures", "errors", "skipped"}
            and result.get("receipt") == receipt
            and result.get("passed") is True and result.get("tests") == EXPECTED_TESTS
            and all(type(result.get(key)) is int for key in ("tests", "failures", "errors", "skipped"))
            and result.get("failures") == 0
            and result.get("errors") == 0 and result.get("skipped") == 0,
            "pixiv_probe_failed")
    return result


def run_checks(docker, image, receipt, root, report):
    sources = {}
    for name in FILES:
        path = root / name
        ordinary(path, root)
        require(path.is_file() and path.stat().st_size < 64 * 1024, "unsafe_pixiv_fixture")
        sources[name] = path.read_text(encoding="utf-8")
    # Stream only these reviewed test modules, never mount a checkout or state.
    script = ("sources = " + repr(sources) + "\nmodules = " + repr(MODULES)
              + "\nreceipt = " + repr(receipt) + "\n" + """import json, pathlib, sys, tempfile, unittest
import ssdl
assert pathlib.Path(ssdl.__file__).resolve().is_relative_to(pathlib.Path('/app/ssdl'))
with tempfile.TemporaryDirectory(dir='/work') as temporary:
    root = pathlib.Path(temporary)
    for name, text in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    sys.path.insert(0, str(root))
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    result = unittest.TestResult()
    suite.run(result)
    passed = result.wasSuccessful() and not result.skipped and not result.expectedFailures
    print(json.dumps(dict(receipt=receipt, passed=passed, tests=result.testsRun,
                          failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped))))
    sys.exit(0 if passed else 1)
""")
    name = "ssdl-pixiv-" + receipt
    try:
        args = ["run", "--rm", "--name", name, "--label", "ssdl.acceptance=" + receipt,
                "--platform", "linux/amd64", "--network", "none", "--read-only", "--user", "10001:10001",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", "64",
                "--memory", "256m", "--cpus", "2", "--no-healthcheck",
                "--tmpfs", "/work:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=0700",
                "--env", "TMPDIR=/work", "--env", "HOME=/work", "--env", "SSDL_DOWNLOAD_DIR=/work/media",
                "--env", "SSDL_MEDIA_ROOT=/work", "--entrypoint", "python", "-i", image, "-"]
        code, output = docker.run(args, timeout=90, data=script.encode("utf-8"), check=False)
        result = validate(output, receipt)
        require(code == 0, "pixiv_probe_exit_failed")
        report["pixiv"] = {key: value for key, value in result.items() if key != "receipt"}
        report["checks"].append("pixiv_author_paths")
    finally:
        clean_container(docker, name, receipt)
