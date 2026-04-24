"""Script de automação para execução completa do fluxo de testes.

Orquestra: testes com coverage → geração de coverage.json → coleta de métricas → PDF.
Uso: python JuniorPlenoTests/run_tests.py  (a partir da raiz do projeto)
"""

import json
import os
import subprocess
import sys
import threading
import time


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


def run_tests() -> tuple[int, float]:
    """Executa pytest com coverage e monitora pico de memória.

    Returns:
        (exit_code, peak_memory_mb)
    """
    cmd = [
        sys.executable, "-m", "coverage", "run",
        "--rcfile=JuniorPlenoTests/.coveragerc",
        "-m", "pytest",
        "JuniorPlenoTests/",
        "-c", "JuniorPlenoTests/pytest.ini",
        "--json-report",
        "--json-report-file=pytest_results.json",
    ]
    print("=" * 60)
    print("Executando testes com coverage...")
    print(f"Comando: {' '.join(cmd)}")
    print("=" * 60)

    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    monitor = PeakMemoryMonitor(proc.pid)
    monitor.start()

    proc.wait()
    peak_mb = monitor.stop()

    print(f"\nPico de memória durante execução: {peak_mb:.1f} MB")
    return proc.returncode, peak_mb


def generate_coverage() -> int:
    """Executa coverage json para gerar coverage.json."""
    cmd = [
        sys.executable, "-m", "coverage", "json",
        "--rcfile=JuniorPlenoTests/.coveragerc",
    ]
    print("\n" + "=" * 60)
    print("Gerando relatório de cobertura (coverage.json)...")
    print("=" * 60)

    result = subprocess.run(cmd)
    return result.returncode


def inject_metrics(peak_memory_mb: float) -> dict:
    """Coleta CPU time e injeta métricas no pytest_results.json."""
    cpu_time = time.process_time()
    metrics = {"cpu_time": cpu_time, "memory_mb": peak_memory_mb}

    results_path = "pytest_results.json"
    if os.path.exists(results_path):
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["cpu_time"] = cpu_time
            data["memory_mb"] = peak_memory_mb
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            print(f"Métricas injetadas — CPU: {cpu_time:.2f}s | Pico Memória: {peak_memory_mb:.1f} MB")
        except Exception as e:
            print(f"Aviso: Não foi possível injetar métricas no JSON: {e}")

    return metrics


def main() -> None:
    """Orquestra o fluxo completo: testes → cobertura → métricas → PDF."""
    start_time = time.time()

    # 1. Executar testes com coverage + monitoramento de memória
    peak_memory_mb = 0.0
    test_exit_code = 1
    try:
        test_exit_code, peak_memory_mb = run_tests()
        if test_exit_code != 0:
            print(f"\nAlguns testes falharam (exit code: {test_exit_code}).")
            print("Continuando para gerar o relatório...\n")
    except Exception as e:
        print(f"Erro ao executar testes: {e}")

    # 2. Gerar coverage.json
    try:
        cov_exit_code = generate_coverage()
        if cov_exit_code != 0:
            print("Aviso: Falha ao gerar coverage.json.")
    except Exception as e:
        print(f"Erro ao gerar coverage: {e}")

    # 3. Coletar e injetar métricas
    try:
        inject_metrics(peak_memory_mb)
    except Exception as e:
        print(f"Erro ao injetar métricas: {e}")

    # 4. Gerar relatório PDF
    print("\n" + "=" * 60)
    print("Gerando relatório PDF...")
    print("=" * 60)

    try:
        project_root = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(project_root)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        from JuniorPlenoTests.generate_report import main as generate_report_main
        generate_report_main()
    except SystemExit:
        print("Aviso: Geração do relatório PDF falhou (arquivos ausentes).")
    except Exception as e:
        print(f"Erro ao gerar relatório PDF: {e}")

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"Fluxo completo finalizado em {elapsed:.2f}s.")
    print("=" * 60)


if __name__ == "__main__":
    main()
