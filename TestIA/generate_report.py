"""
Gerador de Relatório PDF — TestIA Suite

Lê os resultados de teste e cobertura e gera um PDF consolidado
com métricas de qualidade incluindo cobertura por módulo.
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


def _make_table_style(header_color: str) -> TableStyle:
    """Helper to create a consistent table style with the given header color."""
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]
    )


def generate_pdf(data: ReportData, output_path: str) -> None:
    """Gera o relatório PDF com as métricas consolidadas.

    O PDF contém as seções:
    1. Cabeçalho com título e data
    2. Resumo de execução dos testes (total, aprovados, reprovados, tempo)
    3. Cobertura de código (geral, linhas cobertas/total)
    4. Cobertura por módulo
    5. Arquivos com maior/menor cobertura
    6. Métricas de CPU/memória

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
    elements.append(Paragraph("Relatório de Testes — TestIA Suite", title_style))
    elements.append(Paragraph(f"Data: {data.date}", normal_style))
    elements.append(Spacer(1, 12))

    # --- Seção 2: Resumo de Execução ---
    elements.append(Paragraph("Resumo de Execução", section_style))
    exec_data = [
        ["Métrica", "Valor"],
        ["Total de Testes", str(data.total_tests)],
        ["Aprovados", str(data.passed)],
        ["Reprovados", str(data.failed)],
        ["Tempo Total", f"{data.total_time:.2f}s"],
        ["Tempo Médio por Teste", f"{data.avg_time:.2f}s"],
    ]
    exec_table = Table(exec_data, colWidths=[10 * cm, 6 * cm])
    exec_table.setStyle(_make_table_style("#27ae60"))
    elements.append(exec_table)
    elements.append(Spacer(1, 12))

    # --- Seção 3: Cobertura de Código ---
    elements.append(Paragraph("Cobertura de Código", section_style))
    cov_data = [
        ["Métrica", "Valor"],
        ["Cobertura Geral", f"{data.coverage_percent:.1f}%"],
        ["Linhas Cobertas / Total", f"{data.covered_lines} / {data.total_lines}"],
    ]
    cov_table = Table(cov_data, colWidths=[10 * cm, 6 * cm])
    cov_table.setStyle(_make_table_style("#2980b9"))
    elements.append(cov_table)
    elements.append(Spacer(1, 12))

    # --- Seção 4: Cobertura por Módulo ---
    if data.per_module_coverage:
        elements.append(Paragraph("Cobertura por Módulo", section_style))
        mod_rows = [["Módulo", "Cobertura"]]
        for module, pct in sorted(data.per_module_coverage.items()):
            mod_rows.append([module, f"{pct:.1f}%"])
        mod_table = Table(mod_rows, colWidths=[10 * cm, 6 * cm])
        mod_table.setStyle(_make_table_style("#8e44ad"))
        elements.append(mod_table)
        elements.append(Spacer(1, 12))

    # --- Seção 5: Arquivos com Maior/Menor Cobertura ---
    if data.top_covered:
        elements.append(Paragraph("Arquivos com Maior Cobertura", section_style))
        top_rows = [["Arquivo", "Cobertura"]]
        for fname, pct in data.top_covered:
            top_rows.append([fname, f"{pct:.1f}%"])
        top_table = Table(top_rows, colWidths=[10 * cm, 6 * cm])
        top_table.setStyle(_make_table_style("#27ae60"))
        elements.append(top_table)
        elements.append(Spacer(1, 12))

    if data.least_covered:
        elements.append(Paragraph("Arquivos com Menor Cobertura", section_style))
        least_rows = [["Arquivo", "Cobertura"]]
        for fname, pct in data.least_covered:
            least_rows.append([fname, f"{pct:.1f}%"])
        least_table = Table(least_rows, colWidths=[10 * cm, 6 * cm])
        least_table.setStyle(_make_table_style("#e74c3c"))
        elements.append(least_table)
        elements.append(Spacer(1, 12))

    # --- Seção 6: Uso de Recursos ---
    elements.append(Paragraph("Uso de Recursos", section_style))
    resource_data = [
        ["Métrica", "Valor"],
        ["Tempo de CPU", f"{data.cpu_time:.2f}s"],
        ["Uso de Memória", f"{data.memory_mb:.1f} MB"],
    ]
    resource_table = Table(resource_data, colWidths=[10 * cm, 6 * cm])
    resource_table.setStyle(_make_table_style("#e67e22"))
    elements.append(resource_table)

    doc.build(elements)


def main():
    """Ponto de entrada principal do gerador de relatório.

    Lê coverage.json e pytest_results.json, monta o ReportData
    e gera o PDF em TestIA/relatorio_YYYY-MM-DD.pdf.
    Trata arquivos ausentes com aviso e valores padrão.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)

    coverage_path = os.path.join(project_root, "coverage.json")
    results_path = os.path.join(project_root, "pytest_results.json")

    coverage_data = {}
    test_results = {}

    # Carregar coverage.json (gracioso)
    if os.path.exists(coverage_path):
        try:
            coverage_data = load_coverage_data(coverage_path)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Aviso: Erro ao ler coverage.json: {e}")
    else:
        print(f"Aviso: coverage.json não encontrado em {coverage_path}. Usando valores padrão.")

    # Carregar pytest_results.json (gracioso)
    if os.path.exists(results_path):
        try:
            test_results = load_test_results(results_path)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Aviso: Erro ao ler pytest_results.json: {e}")
    else:
        print(f"Aviso: pytest_results.json não encontrado em {results_path}. Usando valores padrão.")

    # Extrair métricas de cobertura
    totals = coverage_data.get("totals", {})
    coverage_percent = totals.get("percent_covered", 0.0)
    covered_lines = totals.get("covered_lines", 0)
    total_lines = totals.get("num_statements", 0)

    # Cobertura por módulo
    per_module_coverage = {}
    files_coverage = coverage_data.get("files", {})
    for filepath, file_data in files_coverage.items():
        summary = file_data.get("summary", {})
        pct = summary.get("percent_covered", 0.0)
        per_module_coverage[filepath] = pct

    # Top/least covered files
    sorted_files = sorted(per_module_coverage.items(), key=lambda x: x[1], reverse=True)
    top_covered = sorted_files[:5] if sorted_files else []
    least_covered = sorted_files[-5:][::-1] if sorted_files else []
    # Avoid overlap when few files
    if len(sorted_files) <= 5:
        least_covered = []

    # Extrair métricas de testes (compatível com pytest-json-report)
    summary = test_results.get("summary", {})
    tests_list = test_results.get("tests", [])

    # pytest-json-report: count from the tests array for accuracy
    if tests_list:
        total_tests = len(tests_list)
        passed = sum(1 for t in tests_list if t.get("outcome") == "passed")
        failed = sum(1 for t in tests_list if t.get("outcome") == "failed")
    else:
        # Fallback: use summary fields (collected > total when errors occur)
        total_tests = summary.get("total", 0) or summary.get("collected", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)

    total_time = test_results.get("duration", 0.0)
    avg_time = total_time / total_tests if total_tests > 0 else 0.0

    # Métricas de recursos
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

    # Gerar PDF
    output_path = os.path.join(base_dir, f"relatorio_{today}.pdf")
    generate_pdf(report_data, output_path)
    print(f"Relatório PDF gerado com sucesso: {output_path}")


if __name__ == "__main__":
    main()
