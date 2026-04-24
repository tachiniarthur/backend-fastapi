"""Script de execução integrada da TestIA Suite.

Executa o fluxo completo:
1. Testes com pytest + coverage (com monitoramento de pico de memória)
2. Geração de coverage JSON
3. Injeção de métricas no pytest_results.json
4. Geração do relatório PDF

Cada etapa é resiliente: se uma falhar, o erro é registrado
e a execução continua com as próximas etapas.
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_VENV_PYTHON = os.path.join(_PROJECT_ROOT, "venv", "Scripts", "python.exe")
if not os.path.exists(_VENV_PYTHON):
    _VENV_PYTHON = sys.executable


class PeakMemoryMonitor:
    """Monitora o pico de memória de um subprocess via psutil, amostrando em thread."""

    def __init__(self, pid: int, interval: float = 0.2):
        self.pid = pid
        self.interval = interval
        self.peak_mb = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self) -> float:
        self._stop.set()
        self._thread.join(timeout=2)
        return self.peak_mb

    def _sample(self):
        try:
            import psutil
        except ImportError:
            return
        try:
            proc = psutil.Process(self.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return
        while not self._stop.is_set():
            try:
                mem = proc.memory_info().rss
                for child in proc.children(recursive=True):
                    try:
                        mem += child.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                mb = mem / (1024 * 1024)
                if mb > self.peak_mb:
                    self.peak_mb = mb
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            self._stop.wait(self.interval)


def run_pytest_with_coverage() -> tuple[int, float]:
    """Executa pytest com coverage e monitora pico de memória.

    Returns:
        (exit_code, peak_memory_mb)
    """
    cmd = [
        _VENV_PYTHON, "-m", "coverage", "run",
        "--rcfile=TestIA/.coveragerc",
        "-m", "pytest", "TestIA/",
        "-c", "TestIA/pytest.ini",
        "--json-report",
        "--json-report-file=pytest_results.json",
    ]
    logger.info("Executando testes: %s", " ".join(cmd))

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    monitor = PeakMemoryMonitor(proc.pid)
    monitor.start()

    stdout, stderr = proc.communicate()
    peak_mb = monitor.stop()

    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)

    logger.info("Testes finalizados (exit=%d, pico memória=%.1f MB)", proc.returncode, peak_mb)
    return proc.returncode, peak_mb


def generate_coverage_json() -> int:
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


def collect_metrics(peak_memory_mb: float) -> dict:
    """Coleta métricas de CPU e injeta junto com pico de memória no pytest_results.json."""
    cpu_time = time.process_time()
    metrics = {"cpu_time": cpu_time, "memory_mb": peak_memory_mb}

    results_path = os.path.join(_PROJECT_ROOT, "pytest_results.json")
    if os.path.exists(results_path):
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["cpu_time"] = cpu_time
            data["memory_mb"] = peak_memory_mb
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            logger.info("Métricas injetadas em pytest_results.json")
        except Exception as e:
            logger.warning("Não foi possível injetar métricas no JSON: %s", e)

    logger.info("Métricas — CPU: %.3fs, Pico Memória: %.1f MB", cpu_time, peak_memory_mb)
    return metrics


def generate_report() -> None:
    """Chama generate_report.main() para gerar o PDF."""
    import importlib.util
    spec_path = os.path.join(_SCRIPT_DIR, "generate_report.py")
    spec = importlib.util.spec_from_file_location("generate_report", spec_path)
    gr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gr)
    gr.main()


def main() -> None:
    """Orquestra o fluxo completo de execução."""
    logger.info("=== Início do fluxo TestIA Suite ===")
    peak_memory_mb = 0.0
    errors: list[str] = []

    # Etapa 1: Testes com coverage + monitoramento de memória
    try:
        logger.info("--- Etapa: Executar testes com coverage ---")
        _exit_code, peak_memory_mb = run_pytest_with_coverage()
    except Exception as exc:
        errors.append(f"Falha na etapa 'Executar testes': {exc}")
        logger.error(errors[-1])

    # Etapa 2: Gerar coverage JSON
    try:
        logger.info("--- Etapa: Gerar coverage JSON ---")
        generate_coverage_json()
    except Exception as exc:
        errors.append(f"Falha na etapa 'Gerar coverage JSON': {exc}")
        logger.error(errors[-1])

    # Etapa 3: Coletar e injetar métricas
    try:
        logger.info("--- Etapa: Coletar métricas ---")
        collect_metrics(peak_memory_mb)
    except Exception as exc:
        errors.append(f"Falha na etapa 'Coletar métricas': {exc}")
        logger.error(errors[-1])

    # Etapa 4: Gerar relatório PDF
    try:
        logger.info("--- Etapa: Gerar relatório PDF ---")
        generate_report()
    except Exception as exc:
        errors.append(f"Falha na etapa 'Gerar relatório PDF': {exc}")
        logger.error(errors[-1])

    if errors:
        logger.warning("Erros registrados:")
        for err in errors:
            logger.warning("  • %s", err)
    else:
        logger.info("Todas as etapas concluídas com sucesso.")


if __name__ == "__main__":
    main()
