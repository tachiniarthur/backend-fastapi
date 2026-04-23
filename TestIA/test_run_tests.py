"""Testes para o script de execução integrada run_tests.py.

Inclui teste de propriedade (Property 26) para resiliência a falhas parciais.
"""

from unittest.mock import patch, MagicMock

from hypothesis import given, settings, strategies as st
import pytest

from TestIA.run_tests import (
    main,
    run_pytest_with_coverage,
    generate_coverage_json,
    collect_metrics,
    generate_report,
)


# ---------------------------------------------------------------------------
# Estratégia: qual(is) etapa(s) devem falhar
# ---------------------------------------------------------------------------
# Cada booleano indica se a etapa correspondente levanta exceção.
# Ordem: [run_pytest_with_coverage, generate_coverage_json, collect_metrics, generate_report]
failure_flags = st.lists(st.booleans(), min_size=4, max_size=4)


class TestRunTestsResilience:
    """
    # Feature: testia-suite, Property 26: Script de execução é resiliente a falhas parciais

    **Validates: Requirements 17.5**
    """

    @given(flags=failure_flags)
    @settings(max_examples=10, deadline=None)
    def test_property_26_resilient_to_partial_failures(self, flags: list[bool]):
        """Para qualquer combinação de falhas nas etapas, main() não levanta exceção."""

        def _maybe_fail(flag, name):
            """Retorna side_effect que falha se flag=True."""
            if flag:
                return RuntimeError(f"Simulated failure in {name}")
            return None  # sem side_effect → execução normal

        with (
            patch(
                "TestIA.run_tests.run_pytest_with_coverage",
                side_effect=_maybe_fail(flags[0], "run_pytest_with_coverage"),
            ) as mock_pytest,
            patch(
                "TestIA.run_tests.generate_coverage_json",
                side_effect=_maybe_fail(flags[1], "generate_coverage_json"),
            ) as mock_cov,
            patch(
                "TestIA.run_tests.collect_metrics",
                side_effect=_maybe_fail(flags[2], "collect_metrics"),
            ) as mock_metrics,
            patch(
                "TestIA.run_tests.generate_report",
                side_effect=_maybe_fail(flags[3], "generate_report"),
            ) as mock_report,
        ):
            # Se side_effect é None, precisamos de um return_value razoável
            if not flags[0]:
                mock_pytest.return_value = 0
            if not flags[1]:
                mock_cov.return_value = 0
            if not flags[2]:
                mock_metrics.return_value = {"cpu_time": 0.1, "memory_mb": 50.0}
            if not flags[3]:
                mock_report.return_value = None

            # main() NUNCA deve levantar exceção, independente das falhas
            main()

            # Todas as etapas devem ter sido chamadas (ou tentadas)
            mock_pytest.assert_called_once()
            mock_cov.assert_called_once()
            mock_metrics.assert_called_once()
            mock_report.assert_called_once()
