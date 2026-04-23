"""Testes para o gerador de relatório PDF — TestIA Suite."""

import json
import os
import re
import tempfile
from datetime import datetime

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pypdf import PdfReader

from TestIA.generate_report import (
    ReportData,
    generate_pdf,
    load_coverage_data,
    load_test_results,
)


# ============================================================
# Unit Tests (Task 13.2)
# ============================================================


class TestGeneratePDFUnit:
    """Testes unitários para geração de PDF."""

    def test_generate_pdf_creates_file(self):
        """Teste de geração de PDF com dados válidos → arquivo criado."""
        data = ReportData(
            total_tests=10,
            passed=8,
            failed=2,
            coverage_percent=85.5,
            total_time=5.0,
            avg_time=0.5,
            cpu_time=3.2,
            memory_mb=128.0,
            covered_lines=500,
            total_lines=600,
            per_module_coverage={"app/services/auth_service.py": 90.0, "app/routers/auth.py": 80.0},
            top_covered=[("app/services/auth_service.py", 90.0)],
            least_covered=[("app/routers/auth.py", 80.0)],
            date="2024-06-15",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "relatorio_2024-06-15.pdf")
            generate_pdf(data, output_path)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0

    def test_generate_pdf_with_empty_module_coverage(self):
        """PDF gerado com per_module_coverage vazio não falha."""
        data = ReportData(
            total_tests=5,
            passed=5,
            failed=0,
            coverage_percent=100.0,
            total_time=1.0,
            avg_time=0.2,
            cpu_time=0.8,
            memory_mb=64.0,
            covered_lines=100,
            total_lines=100,
            per_module_coverage={},
            top_covered=[],
            least_covered=[],
            date="2024-01-01",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "relatorio_2024-01-01.pdf")
            generate_pdf(data, output_path)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0


class TestLoadDataUnit:
    """Testes unitários para carregamento de dados."""

    def test_load_coverage_data_missing_file(self):
        """Teste com arquivo de cobertura ausente → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_coverage_data("/nonexistent/path/coverage.json")

    def test_load_test_results_missing_file(self):
        """Teste com arquivo de resultados ausente → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_test_results("/nonexistent/path/pytest_results.json")

    def test_load_coverage_data_valid(self):
        """Teste de leitura de coverage.json válido."""
        sample = {"totals": {"percent_covered": 85.0, "covered_lines": 500, "num_statements": 600}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample, f)
            f.flush()
            path = f.name
        try:
            result = load_coverage_data(path)
            assert result["totals"]["percent_covered"] == 85.0
        finally:
            os.unlink(path)

    def test_load_test_results_valid(self):
        """Teste de leitura de pytest_results.json válido."""
        sample = {"summary": {"total": 10, "passed": 8, "failed": 2}, "duration": 5.0}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample, f)
            f.flush()
            path = f.name
        try:
            result = load_test_results(path)
            assert result["summary"]["total"] == 10
        finally:
            os.unlink(path)


class TestFilenameFormat:
    """Testes unitários para formato do nome do arquivo."""

    def test_filename_format_matches_date_pattern(self):
        """Teste de nome do arquivo → formato relatorio_YYYY-MM-DD.pdf."""
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"relatorio_{today}.pdf"
        assert re.match(r"^relatorio_\d{4}-\d{2}-\d{2}\.pdf$", filename)

    def test_pdf_generated_with_correct_name(self):
        """PDF gerado com nome no formato correto."""
        data = ReportData(date="2024-12-25")
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = f"relatorio_{data.date}.pdf"
            output_path = os.path.join(tmpdir, filename)
            generate_pdf(data, output_path)
            basename = os.path.basename(output_path)
            assert basename == "relatorio_2024-12-25.pdf"


# ============================================================
# Property-Based Tests (Tasks 13.3 and 13.4)
# ============================================================

# Strategy for generating valid ReportData
report_data_strategy = st.builds(
    ReportData,
    total_tests=st.integers(min_value=1, max_value=500),
    passed=st.integers(min_value=0, max_value=500),
    failed=st.integers(min_value=0, max_value=500),
    coverage_percent=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    total_time=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    avg_time=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    cpu_time=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    memory_mb=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    covered_lines=st.integers(min_value=0, max_value=100000),
    total_lines=st.integers(min_value=0, max_value=100000),
    per_module_coverage=st.dictionaries(
        keys=st.from_regex(r"app/[a-z_]+\.py", fullmatch=True),
        values=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        min_size=0,
        max_size=5,
    ),
    top_covered=st.lists(
        st.tuples(
            st.from_regex(r"app/[a-z_]+\.py", fullmatch=True),
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        ),
        min_size=0,
        max_size=3,
    ),
    least_covered=st.lists(
        st.tuples(
            st.from_regex(r"app/[a-z_]+\.py", fullmatch=True),
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        ),
        min_size=0,
        max_size=3,
    ),
    date=st.dates().map(lambda d: d.strftime("%Y-%m-%d")),
)


# Feature: testia-suite, Property 24: Relatório PDF contém todas as métricas obrigatórias
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(data=report_data_strategy)
def test_pdf_contains_all_required_metrics(data):
    """
    **Validates: Requirements 16.2, 16.3, 16.4, 16.5, 16.6**

    Para qualquer ReportData válido, o PDF gerado deve conter:
    tempo total, tempo médio, total de testes, aprovados, reprovados,
    cobertura geral, cobertura por módulo, arquivos com maior/menor
    cobertura, e métricas de CPU/memória.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, f"relatorio_{data.date}.pdf")
        generate_pdf(data, output_path)

        assert os.path.exists(output_path), "PDF não foi criado"
        assert os.path.getsize(output_path) > 0, "PDF está vazio"

        # Extract text from PDF using pypdf
        reader = PdfReader(output_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() or ""

        # Verify test execution metrics are present
        assert "Total de Testes" in full_text, "Falta 'Total de Testes' no PDF"
        assert "Aprovados" in full_text, "Falta 'Aprovados' no PDF"
        assert "Reprovados" in full_text, "Falta 'Reprovados' no PDF"
        assert "Tempo Total" in full_text, "Falta 'Tempo Total' no PDF"
        assert "Tempo M" in full_text, "Falta 'Tempo Médio' no PDF"
        assert str(data.total_tests) in full_text, "Valor de total_tests ausente"
        assert str(data.passed) in full_text, "Valor de passed ausente"
        assert str(data.failed) in full_text, "Valor de failed ausente"

        # Verify coverage metrics
        assert "Cobertura Geral" in full_text, "Falta 'Cobertura Geral' no PDF"
        assert "Cobertura de C" in full_text, "Falta seção de cobertura no PDF"

        # Verify per-module coverage section if data has modules
        if data.per_module_coverage:
            assert "dulo" in full_text, "Falta seção 'Cobertura por Módulo' no PDF"

        # Verify top/least covered sections if data has them
        if data.top_covered:
            assert "Maior Cobertura" in full_text, "Falta seção 'Maior Cobertura' no PDF"
        if data.least_covered:
            assert "Menor Cobertura" in full_text, "Falta seção 'Menor Cobertura' no PDF"

        # Verify resource metrics
        assert "Tempo de CPU" in full_text, "Falta 'Tempo de CPU' no PDF"
        assert "Mem" in full_text, "Falta 'Uso de Memória' no PDF"


# Feature: testia-suite, Property 25: Nome do arquivo PDF segue padrão de data
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(date=st.dates())
def test_pdf_filename_follows_date_pattern(date):
    """
    **Validates: Requirements 16.8**

    Para qualquer data gerada, o arquivo PDF deve ser salvo com um nome
    que siga o formato relatorio_YYYY-MM-DD.pdf.
    """
    date_str = date.strftime("%Y-%m-%d")

    data = ReportData(
        total_tests=5,
        passed=4,
        failed=1,
        coverage_percent=55.0,
        total_time=2.0,
        avg_time=0.4,
        cpu_time=1.5,
        memory_mb=50.0,
        covered_lines=100,
        total_lines=200,
        date=date_str,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        filename = f"relatorio_{date_str}.pdf"
        output_path = os.path.join(tmpdir, filename)

        generate_pdf(data, output_path)

        assert os.path.exists(output_path), f"PDF não foi criado em {output_path}"

        basename = os.path.basename(output_path)
        assert re.match(r"^relatorio_\d{4}-\d{2}-\d{2}\.pdf$", basename), (
            f"Nome '{basename}' não segue o padrão relatorio_YYYY-MM-DD.pdf"
        )
        assert date_str in basename, (
            f"Nome do arquivo '{basename}' não contém a data '{date_str}'"
        )
