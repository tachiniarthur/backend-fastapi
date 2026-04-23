"""Script de execução integrada da TestIA Suite.

Executa o fluxo completo:
1. Testes com pytest + coverage
2. Geração de coverage JSON
3. Coleta de métricas de CPU e memória
4. Geração do relatório PDF

Cada etapa é resiliente: se uma falhar, o erro é registrado
e a execução continua com as próximas etapas.
"""

import logging
import os
import subprocess
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Resolve the venv Python executable
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_VENV_PYTHON = os.path.join(_PROJECT_ROOT, "venv", "Scripts", "python.exe")
if not os.path.exists(_VENV_PYTHON):
    _VENV_PYTHON = sys.executable  # fallback


def run_pytest_with_coverage() -> int:
    """Executa pytest com coverage e json-report.

    Returns:
        O código de retorno do processo.
    """
    cmd = [
        _VENV_PYTHON, "-m", "coverage", "run",
        "-m", "pytest", "TestIA/",
        "-c", "TestIA/pytest.ini",
        "--json-report",
        "--json-report-file=pytest_results.json",
    ]
    logger.info("Executando testes: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    logger.info("Testes finalizados com código de retorno: %d", result.returncode)
    return result.returncode


def generate_coverage_json() -> int:
    """Gera o arquivo coverage.json.

    Returns:
        O código de retorno do processo.
    """
    cmd = [
        _VENV_PYTHON, "-m", "coverage", "json",
        "--rcfile=TestIA/.coveragerc",
    ]
    logger.info("Gerando coverage JSON: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    logger.info("Coverage JSON finalizado com código de retorno: %d", result.returncode)
    return result.returncode


def collect_metrics() -> dict:
    """Coleta métricas de CPU e memória.

    Returns:
        Dicionário com cpu_time (s) e memory_mb (MB).
    """
    cpu_time = time.process_time()

    memory_mb = 0.0
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)
    except ImportError:
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            memory_mb = usage.ru_maxrss / 1024  # KB -> MB on Linux
        except ImportError:
            logger.warning("Nem psutil nem resource disponíveis; memória não coletada.")

    logger.info("Métricas coletadas — CPU: %.3fs, Memória: %.2f MB", cpu_time, memory_mb)
    return {"cpu_time": cpu_time, "memory_mb": memory_mb}


def generate_report() -> None:
    """Chama generate_report.main() para gerar o PDF."""
    import importlib.util
    import os
    spec_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_report.py")
    spec = importlib.util.spec_from_file_location("generate_report", spec_path)
    gr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gr)
    gr.main()


def main() -> None:
    """Orquestra o fluxo completo de execução."""
    logger.info("=== Início do fluxo TestIA Suite ===")
    start = time.process_time()

    steps = [
        ("Executar testes com coverage", run_pytest_with_coverage),
        ("Gerar coverage JSON", generate_coverage_json),
        ("Coletar métricas", collect_metrics),
        ("Gerar relatório PDF", generate_report),
    ]

    errors: list[str] = []

    for name, step_fn in steps:
        try:
            logger.info("--- Etapa: %s ---", name)
            step_fn()
        except Exception as exc:
            msg = f"Falha na etapa '{name}': {exc}"
            logger.error(msg)
            errors.append(msg)

    elapsed = time.process_time() - start
    logger.info("=== Fluxo finalizado em %.3fs ===", elapsed)

    if errors:
        logger.warning("Erros registrados durante a execução:")
        for err in errors:
            logger.warning("  • %s", err)
    else:
        logger.info("Todas as etapas concluídas com sucesso.")


if __name__ == "__main__":
    main()
