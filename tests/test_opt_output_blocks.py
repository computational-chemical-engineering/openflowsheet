"""OPT WO-4 (design §4.4): the gray box's outputs as a sequence of output blocks.

E01's assessment is one block; WO-5's phase rows will be another, each from its own twin. One
block is passed through unchanged (gate G2 measures that bitwise); with several, the outputs, their
scales, admissibility rows and Jacobian are the blocks' in block order. The second block here is a
synthetic one over the first block's functions (its ids renamed), so the stacking is checked
against an expectation built independently of `FullSpaceNlp`'s concatenation.
"""

from __future__ import annotations

from types import MappingProxyType

import numpy as np
import pytest
import scipy.sparse as sp
from test_e01_b_nlp import binding, formulation, full_space, program, tac_objective

from openflowsheet.studies.nlp.formulation import FullSpaceNlp, OutputBlock


def _nlp() -> FullSpaceNlp:
    return full_space(formulation(tac_objective(), binding(("size.FAR.area", "tac"), program())))


def _shadow(first: OutputBlock, factor: float) -> OutputBlock:
    """`factor` times `first`, under `phase.<id>` names, one admissibility row."""
    ids = tuple(f"phase.{name}" for name in first.ids)
    return OutputBlock(
        name="phase",
        constraint="phase_admissibility",
        ids=ids,
        scales=MappingProxyType({name: 2.0 for name in ids}),
        admissibility=MappingProxyType({ids[-1]: 5.0}),
        values=lambda z: factor * first.values(z),
        jacobian=lambda z: sp.csc_matrix(factor * first.jacobian(z)),
    )


def test_an_assessment_is_one_block_and_the_concatenation_is_that_block() -> None:
    nlp = _nlp()
    assert [block.name for block in nlp.output_blocks] == ["assessment"]
    (block,) = nlp.output_blocks
    assert block.constraint == "assessment_admissibility"
    assert block.ids == nlp.output_ids
    assert dict(block.scales) == nlp.output_scales
    assert dict(block.admissibility) == nlp.admissibility_nominals
    z = nlp.initial_point()
    assert np.array_equal(nlp.output_values(z), block.values(z))
    assert (nlp.output_jacobian(z) != block.jacobian(z)).nnz == 0


def test_without_an_assessment_there_is_no_block() -> None:
    from m03_support import nlp_formulation

    nlp = full_space(nlp_formulation())
    assert nlp.output_blocks == () and nlp.output_ids == ()


def test_two_blocks_stack_in_block_order() -> None:
    nlp = _nlp()
    (first,) = nlp.output_blocks
    z = nlp.initial_point()
    single_values, single_jacobian = nlp.output_values(z), nlp.output_jacobian(z).toarray()
    calls = dict(nlp.counters)
    nlp._add_block(_shadow(first, 3.0))
    assert nlp.output_ids == (*first.ids, *(f"phase.{name}" for name in first.ids))
    assert nlp.admissibility_nominals == {
        **dict(first.admissibility),
        f"phase.{first.ids[-1]}": 5.0,
    }
    assert np.array_equal(
        nlp.output_scaling(),
        np.concatenate(
            [1.0 / np.array([first.scales[n] for n in first.ids]), [0.5] * len(first.ids)]
        ),
    )
    values = nlp.output_values(z)
    assert np.array_equal(values, np.concatenate([single_values, 3.0 * single_values]))
    jacobian = nlp.output_jacobian(z)
    assert jacobian.shape == (2 * len(first.ids), len(nlp.primal_ids))
    assert np.array_equal(jacobian.toarray(), np.vstack([single_jacobian, 3.0 * single_jacobian]))
    # One call of the gray box's outputs is one count, whatever the number of blocks.
    assert nlp.counters["output_calls"] == calls["output_calls"] + 1
    assert nlp.counters["output_jacobian_calls"] == calls["output_jacobian_calls"] + 1


def test_a_block_repeating_an_output_id_is_refused() -> None:
    nlp = _nlp()
    (first,) = nlp.output_blocks
    with pytest.raises(ValueError, match="repeat across blocks"):
        nlp._add_block(first)
