"""Cost providers of an assessment: forms, correlation sets, quotes and the cost basis.

E01 design §4.5–§4.6 as amended by §9.2 (ADR 0052; register R-864, R-865). `forms` holds the
arithmetic (the generic forms and one form per IDAES SSLW method a day-one family uses), `sets`
loads and checks the data that parameterises them, `index` escalates, converts and locates a cost
basis. The cost contributor that wires sizing, forms and the basis into the program is WO-A4's.
"""
