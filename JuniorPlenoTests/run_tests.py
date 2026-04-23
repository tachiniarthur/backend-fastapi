"""Script de automação para execução completa do fluxo de testes.

Orquestra: testes com coverage → geração de coverage.json → coleta de métricas → PDF.
Uso: python JuniorPlenoTests/run_tests.py  (a partir da raiz do projeto)
"""

import os
import subprocess
import sys
import time


def run_tests() -> int:
    """Executa pytest com coverage via subprocess.

    Returns:
        Código de saída do pytest (0 = todos passaram, != 0 = falhas).
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

    result = subprocess.run(cmd)
    return result.returncode


def generate_coverage() -> int:
    """Executa coverage json para gerar coverage.json.

    Returns:
        Código de saída do comando coverage.
    """
    cmd = [
        sys.executable, "-m", "coverage", "json",
        "--rcfile=JuniorPlenoTests/.coveragerc",
    ]
    print("\n" + "=" * 60)
    print("Gerando relatório de cobertura (coverage.json)...")
    print("=" * 60)

    result = subprocess.run(cmd)
    return result.returncode


def collect_metrics() -> dict:
    """Coleta métricas de uso de recursos (CPU e memória).

    Returns:
        Dicionário com cpu_time (segundos) e memory_mb (MB).
    """
    cpu_time = time.process_time()

    memory_mb = 0.0
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / (1024 * 1024)
    except ImportError:
        # psutil não disponível — tenta via resource (Linux/macOS)
        try:
            import resource
            # maxrss em KB no Linux, em bytes no macOS
            maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform == "darwin":
                memory_mb = maxrss / (1024 * 1024)
            else:
                memory_mb = maxrss / 1024
        except ImportError:
            memory_mb = 0.0

    return {"cpu_time": cpu_time, "memory_mb": memory_mb}


def main() -> None:
    """Orquestra o fluxo completo: testes → cobertura → métricas → PDF."""
    start_time = time.time()

    # 1. Executar testes com coverage
    test_exit_code = run_tests()
    if test_exit_code != 0:
        print(f"\nAlguns testes falharam (exit code: {test_exit_code}).")
        print("Continuando para gerar o relatório...\n")

    # 2. Gerar coverage.json
    cov_exit_code = generate_coverage()
    if cov_exit_code != 0:
        print("Aviso: Falha ao gerar coverage.json. O relatório pode ficar incompleto.")

    # 3. Coletar métricas de recursos
    metrics = collect_metrics()
    elapsed = time.time() - start_time
    print(f"\nMétricas coletadas — CPU: {metrics['cpu_time']:.2f}s | "
          f"Memória: {metrics['memory_mb']:.1f} MB | "
          f"Tempo total: {elapsed:.2f}s")

    # 4. Gerar relatório PDF
    print("\n" + "=" * 60)
    print("Gerando relatório PDF...")
    print("=" * 60)

    try:
        # Adiciona o diretório raiz ao path para importar o módulo
        project_root = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(project_root)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        from JuniorPlenoTests.generate_report import main as generate_report_main
        generate_report_main()
    except SystemExit:
        # generate_report.main() chama sys.exit(1) se arquivos estão ausentes
        print("Aviso: Geração do relatório PDF falhou (arquivos ausentes).")
    except Exception as e:
        print(f"Erro ao gerar relatório PDF: {e}")

    print("\n" + "=" * 60)
    print("Fluxo completo finalizado.")
    print("=" * 60)


if __name__ == "__main__":
    main()
