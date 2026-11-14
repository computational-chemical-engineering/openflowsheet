"""The V-tolerances of candidate verification (M03 spec §8.5, §8.3): one registered table.

`studies.nlp.verification` applies them (V2, V3, V5) and re-exports them; the assessment program
reads `TAU_FEAS` here for its admissibility rows. A leaf: it imports nothing from the package,
so code below `studies` may import it.
"""

from __future__ import annotations

from typing import Final

#: Spec §8.5's thresholds.
TAU_GROSS: Final = 1e-6
TAU_FEAS: Final = 1e-8
TAU_ACTIVE: Final = 1e-6
TAU_KKT: Final = 1e-6
TAU_SIGN: Final = 1e-8
TAU_LICQ: Final = 1e-8
#: Spec §8.3: at a vertex every multiplier must exceed this for the critical cone to be {0}.
TAU_VERTEX_MULTIPLIER: Final = 1e-8
