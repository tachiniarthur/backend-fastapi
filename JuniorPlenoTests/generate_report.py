"""
Gerador de Relatório PDF — Suite de Testes Júnior/Pleno

Lê os resultados de teste e cobertura e gera um PDF consolidado
com métricas de qualidade.
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


@dataclass
class ReportData:
    """Dados consolidados para o relatório PDF."""

    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    coverage_percent: float = 0.0
    total_time: float = 0.0
    avg_time: float = 0.0
    cpu_time: float = 0.0
    memory_mb: float = 0.0
    covered_lines: int = 0
    total_lines: int = 0
    per_module_coverage: dict = field(default_factory=dict)
    top_covered: list = field(default_factory=list)
    least_covered: list = field(default_factory=list)
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))


def load_coverage_data(path: str) -> dict:
    """Lê o arquivo coverage.json e retorna os dados de cobertura.

    Args:
        path: Caminho para o arquivo coverage.json.

    Returns:
        Dicionário com os dados de cobertura.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo de cobertura não encontrado: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def load_test_results(path: str) -> dict:
    """Lê o arquivo pytest_results.json e retorna os resultados dos testes.

    Args:
        path: Caminho para o arquivo pytest_results.json.

    Returns:
        Dicionário com os resultados dos testes.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo de resultados não encontrado: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def generate_pdf(data: ReportData, output_path: str) -> None:
    """Gera o relatório PDF com as métricas consolidadas.

    O PDF contém as seções:
    1. Cabeçalho com título e data
    2. Cobertura de código
    3. Resultados dos testes
    4. Tempo de execução
    5. Uso de recursos

    Args:
        data: Dados consolidados do relatório.
        output_path: Caminho para salvar o arquivo PDF.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=20,
        spaceAfter=6,
        textColor=colors.HexColor("#2c3e50"),
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#2980b9"),
    )
    normal_style = styles["Normal"]

    elements = []

    # --- Seção 1: Cabeçalho ---
    elements.append(Paragraph("Relatório de Testes — Júnior/Pleno", title_style))
    elements.append(Paragraph(f"Data: {data.date}", normal_style))
    elements.append(Spacer(1, 12))

    # --- Seção 2: Cobertura ---
    elements.append(Paragraph("Cobertura de Código", section_style))
    coverage_data = [
        ["Métrica", "Valor"],
        ["Cobertura Geral", f"{data.coverage_percent:.1f}%"],
        ["Linhas Cobertas / Total", f"{data.covered_lines} / {data.total_lines}"],
    ]
    coverage_table = Table(coverage_data, colWidths=[10 * cm, 6 * cm])
    coverage_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2980b9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(coverage_table)
    elements.append(Spacer(1, 12))

    # --- Seção 2b: Cobertura por Módulo ---
    if data.per_module_coverage:
        elements.append(Paragraph("Cobertura por Módulo", section_style))
        mod_rows = [["Módulo", "Cobertura", "Testes"]]
        for module, value in sorted(data.per_module_coverage.items()):
            pct, count = value if isinstance(value, tuple) else (value, 0)
            mod_rows.append([module.capitalize(), f"{pct:.1f}%", str(count)])
        mod_table = Table(mod_rows, colWidths=[6 * cm, 4 * cm, 6 * cm])
        mod_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8e44ad")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ])
        )
        elements.append(mod_table)
        elements.append(Spacer(1, 12))

    # --- Seção 2c: Arquivos com Maior/Menor Cobertura ---
    if data.top_covered:
        elements.append(Paragraph("Arquivos com Maior Cobertura", section_style))
        top_rows = [["Arquivo", "Cobertura"]]
        for fname, pct in data.top_covered:
            top_rows.append([fname, f"{pct:.1f}%"])
        top_table = Table(top_rows, colWidths=[10 * cm, 6 * cm])
        top_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27ae60")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ])
        )
        elements.append(top_table)
        elements.append(Spacer(1, 12))

    if data.least_covered:
        elements.append(Paragraph("Arquivos com Menor Cobertura", section_style))
        least_rows = [["Arquivo", "Cobertura"]]
        for fname, pct in data.least_covered:
            least_rows.append([fname, f"{pct:.1f}%"])
        least_table = Table(least_rows, colWidths=[10 * cm, 6 * cm])
        least_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e74c3c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ])
        )
        elements.append(least_table)
        elements.append(Spacer(1, 12))

    # --- Seção 3: Resultados dos Testes ---
    elements.append(Paragraph("Resultados dos Testes", section_style))
    results_data = [
        ["Métrica", "Valor"],
        ["Total de Testes", str(data.total_tests)],
        ["Aprovados", str(data.passed)],
        ["Falhados", str(data.failed)],
    ]
    results_table = Table(results_data, colWidths=[10 * cm, 6 * cm])
    results_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27ae60")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(results_table)
    elements.append(Spacer(1, 12))

    # --- Seção 4: Tempo de Execução ---
    elements.append(Paragraph("Tempo de Execução", section_style))
    time_data = [
        ["Métrica", "Valor"],
        ["Tempo Total", f"{data.total_time:.2f}s"],
        ["Tempo Médio por Teste", f"{data.avg_time:.2f}s"],
    ]
    time_table = Table(time_data, colWidths=[10 * cm, 6 * cm])
    time_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8e44ad")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(time_table)
    elements.append(Spacer(1, 12))

    # --- Seção 5: Uso de Recursos ---
    elements.append(Paragraph("Uso de Recursos", section_style))
    resource_data = [
        ["Métrica", "Valor"],
        ["Tempo de CPU", f"{data.cpu_time:.2f}s"],
        ["Pico de Memória", f"{data.memory_mb:.1f} MB"],
    ]
    resource_table = Table(resource_data, colWidths=[10 * cm, 6 * cm])
    resource_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e67e22")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(resource_table)

    doc.build(elements)


def main():
    """Ponto de entrada principal do gerador de relatório.

    Lê coverage.json e pytest_results.json, monta o ReportData
    e gera o PDF em JuniorPlenoTests/relatorio_YYYY-MM-DD.pdf.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)

    coverage_path = os.path.join(project_root, "coverage.json")
    results_path = os.path.join(project_root, "pytest_results.json")

    # Tratamento de erro para arquivos ausentes
    missing = []
    if not os.path.exists(coverage_path):
        missing.append(f"coverage.json ({coverage_path})")
    if not os.path.exists(results_path):
        missing.append(f"pytest_results.json ({results_path})")

    if missing:
        print("Erro: Arquivos necessários não encontrados:")
        for m in missing:
            print(f"  - {m}")
        print("\nExecute os testes com coverage antes de gerar o relatório:")
        print("  coverage run -m pytest JuniorPlenoTests/")
        print("  coverage json")
        sys.exit(1)

    # Carregar dados
    try:
        coverage_data = load_coverage_data(coverage_path)
        test_results = load_test_results(results_path)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Erro ao ler dados: {e}")
        sys.exit(1)

    # Extrair métricas de cobertura
    totals = coverage_data.get("totals", {})
    coverage_percent = totals.get("percent_covered", 0.0)
    covered_lines = totals.get("covered_lines", 0)
    total_lines = totals.get("num_statements", 0)

    # Cobertura por arquivo (raw)
    per_file_coverage = {}
    files_coverage = coverage_data.get("files", {})
    for filepath, file_data in files_coverage.items():
        summary_f = file_data.get("summary", {})
        per_file_coverage[filepath] = {
            "pct": summary_f.get("percent_covered", 0.0),
            "covered": summary_f.get("covered_lines", 0),
            "total": summary_f.get("num_statements", 0),
        }

    # Cobertura por domínio (módulo de negócio)
    MODULE_KEYWORDS = {
        "auth":    ["auth"],
        "user":    ["user"],
        "product": ["product"],
        "cart":    ["cart"],
        "order":   ["order"],
    }

    EXCLUDED_MODULES = {"admin", "outros"}

    def _classify_module(filepath: str) -> str:
        normalized = filepath.replace("\\", "/").lower()
        for module, keywords in MODULE_KEYWORDS.items():
            if any(kw in normalized for kw in keywords):
                return module
        return "outros"

    module_covered: dict = {}
    module_total: dict = {}
    for filepath, info in per_file_coverage.items():
        mod = _classify_module(filepath)
        module_covered[mod] = module_covered.get(mod, 0) + info["covered"]
        module_total[mod] = module_total.get(mod, 0) + info["total"]

    # Count tests per module from pytest_results (classified by test nodeid)
    module_test_count: dict = {}
    tests_list = test_results.get("tests", [])
    for t in tests_list:
        nodeid = t.get("nodeid", "").lower()
        mod = _classify_module(nodeid)
        module_test_count[mod] = module_test_count.get(mod, 0) + 1

    per_module_coverage = {
        mod: (
            (module_covered[mod] / module_total[mod] * 100) if module_total.get(mod, 0) > 0 else 0.0,
            module_test_count.get(mod, 0),
        )
        for mod in sorted(set(list(module_covered.keys()) + list(module_test_count.keys())))
        if mod not in EXCLUDED_MODULES
    }

    sorted_files = sorted(per_file_coverage.items(), key=lambda x: x[1]["pct"], reverse=True)
    top_covered = [(fp, info["pct"]) for fp, info in sorted_files[:5]] if sorted_files else []
    least_covered = [(fp, info["pct"]) for fp, info in sorted_files[-5:][::-1]] if len(sorted_files) > 5 else []

    # Extrair métricas de testes
    summary = test_results.get("summary", {})
    total_tests = len(tests_list) if tests_list else summary.get("total", 0)
    passed = sum(1 for t in tests_list if t.get("outcome") == "passed") if tests_list else summary.get("passed", 0)
    failed = sum(1 for t in tests_list if t.get("outcome") == "failed") if tests_list else summary.get("failed", 0)
    total_time = test_results.get("duration", 0.0)
    avg_time = total_time / total_tests if total_tests > 0 else 0.0

    # Métricas de recursos (coletadas pelo run_tests.py ou estimadas)
    cpu_time = test_results.get("cpu_time", time.process_time())
    memory_mb = test_results.get("memory_mb", 0.0)

    # Montar dados do relatório
    today = datetime.now().strftime("%Y-%m-%d")
    report_data = ReportData(
        total_tests=total_tests,
        passed=passed,
        failed=failed,
        coverage_percent=coverage_percent,
        covered_lines=covered_lines,
        total_lines=total_lines,
        total_time=total_time,
        avg_time=avg_time,
        cpu_time=cpu_time,
        memory_mb=memory_mb,
        per_module_coverage=per_module_coverage,
        top_covered=top_covered,
        least_covered=least_covered,
        date=today,
    )

    # Gerar PDF com número de execução incremental
    import glob
    suite_name = "junior"
    existing = glob.glob(os.path.join(base_dir, f"relatorio_{suite_name}_{today}_*.pdf"))
    run_number = len(existing) + 1
    output_path = os.path.join(base_dir, f"relatorio_{suite_name}_{today}_{run_number}.pdf")
    generate_pdf(report_data, output_path)
    print(f"Relatório PDF gerado com sucesso: {output_path}")


if __name__ == "__main__":
    main()
