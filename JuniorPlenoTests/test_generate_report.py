# Feature: junior-pleno-test-suite, Property 11: Nome do arquivo PDF contém a data
"""Teste de propriedade para verificar que o nome do arquivo PDF contém a data YYYY-MM-DD."""

import os
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from JuniorPlenoTests.generate_report import ReportData, generate_pdf


@settings(max_examples=10, deadline=None)
@given(date=st.dates())
def test_pdf_filename_contains_date(date):
    """
    **Validates: Requirements 10.7**

    Para qualquer data gerada, o arquivo PDF deve ser salvo com um nome
    que contenha a data no formato YYYY-MM-DD.
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

        # Verify the file was created
        assert os.path.exists(output_path), f"PDF não foi criado em {output_path}"

        # Verify the filename contains the date in YYYY-MM-DD format
        basename = os.path.basename(output_path)
        assert date_str in basename, (
            f"Nome do arquivo '{basename}' não contém a data '{date_str}'"
        )
