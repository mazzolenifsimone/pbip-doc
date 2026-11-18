"""
Unit tests for the indentation-aware TMDL Lexer & Block Parser (tmdl_lexer.py).
"""

import unittest
from pbip_doc.tmdl_lexer import (
    parse_tmdl,
    find_first_block,
    find_blocks,
    count_indent,
    unquote_tmdl_name,
    clean_multiline_code,
)


class TestTMDLLexer(unittest.TestCase):

    def test_count_indent_tabs_and_spaces(self):
        self.assertEqual(count_indent("table Sales"), (0, "table Sales"))
        self.assertEqual(count_indent("\tcolumn ID"), (1, "column ID"))
        self.assertEqual(count_indent("\t\tdataType: int64"), (2, "dataType: int64"))
        self.assertEqual(count_indent("    column ID"), (1, "column ID"))
        self.assertEqual(count_indent("        dataType: int64"), (2, "dataType: int64"))

    def test_unquote_tmdl_name(self):
        self.assertEqual(unquote_tmdl_name("Sales"), "Sales")
        self.assertEqual(unquote_tmdl_name("'Sales Territory'"), "Sales Territory")
        self.assertEqual(unquote_tmdl_name('"Sales Territory"'), "Sales Territory")

    def test_clean_multiline_code_backticks(self):
        dax = "```dax\nVAR x = 1\nRETURN x\n```"
        self.assertEqual(clean_multiline_code(dax), "VAR x = 1\nRETURN x")
        m_code = "```m\nlet\n  Source = 1\nin\n  Source\n```"
        self.assertEqual(clean_multiline_code(m_code), "let\n  Source = 1\nin\n  Source")

    def test_parse_table_with_columns_and_measures(self):
        content = """/// Table documentation comment
table Sales
\tlineageTag: 12345

\t/// Column doc
\tcolumn SalesKey
\t\tdataType: int64
\t\tisKey
\t\tisHidden
\t\tsourceColumn: SalesKey

\tcolumn Margin = [Price] - [Cost]
\t\tdataType: decimal
\t\tformatString: $#,##0.00

\t/// Measure doc
\tmeasure 'Total Sales' = SUM(Sales[Amount])
\t\tformatString: $#,##0.00
\t\tdisplayFolder: Financials

\tmeasure 'Profit YoY' =
\t\t\tVAR Cur = [Total Sales]
\t\t\tVAR Prev = CALCULATE([Total Sales], SAMEPERIODLASTYEAR('Date'[Date]))
\t\t\tRETURN DIVIDE(Cur - Prev, Prev)
\t\tformatString: 0.0%
\t\tdisplayFolder: Financials
\t\tlineageTag: meas-tag-1

\tpartition Sales-Partition = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t    Source = Sql.Database("srv", "db")
\t\t\t\tin
\t\t\t\t    Source

\tannotation PBI_NavigationStepName = Navigation
"""
        roots = parse_tmdl(content)
        self.assertEqual(len(roots), 1)
        tbl = roots[0]
        self.assertEqual(tbl.keyword, "table")
        self.assertEqual(tbl.name, "Sales")
        self.assertEqual(tbl.doc_comment, "Table documentation comment")
        self.assertEqual(tbl.properties.get("lineageTag"), "12345")
        self.assertEqual(tbl.annotations.get("PBI_NavigationStepName"), "Navigation")

        # Columns
        cols = [c for c in tbl.children if c.keyword == "column"]
        self.assertEqual(len(cols), 2)
        c1 = cols[0]
        self.assertEqual(c1.name, "SalesKey")
        self.assertEqual(c1.doc_comment, "Column doc")
        self.assertEqual(c1.properties.get("dataType"), "int64")
        self.assertEqual(c1.properties.get("sourceColumn"), "SalesKey")
        self.assertIn("isKey", c1.flags)
        self.assertIn("isHidden", c1.flags)
        self.assertIsNone(c1.expression)

        c2 = cols[1]
        self.assertEqual(c2.name, "Margin")
        self.assertEqual(c2.expression, "[Price] - [Cost]")
        self.assertEqual(c2.properties.get("dataType"), "decimal")
        self.assertEqual(c2.properties.get("formatString"), "$#,##0.00")

        # Measures
        meas = [c for c in tbl.children if c.keyword == "measure"]
        self.assertEqual(len(meas), 2)
        m1 = meas[0]
        self.assertEqual(m1.name, "Total Sales")
        self.assertEqual(m1.doc_comment, "Measure doc")
        self.assertEqual(m1.expression, "SUM(Sales[Amount])")
        self.assertEqual(m1.properties.get("formatString"), "$#,##0.00")
        self.assertEqual(m1.properties.get("displayFolder"), "Financials")

        m2 = meas[1]
        self.assertEqual(m2.name, "Profit YoY")
        self.assertIn("VAR Cur = [Total Sales]", m2.expression)
        self.assertIn("RETURN DIVIDE(Cur - Prev, Prev)", m2.expression)
        self.assertNotIn("formatString", m2.expression)
        self.assertEqual(m2.properties.get("formatString"), "0.0%")
        self.assertEqual(m2.properties.get("displayFolder"), "Financials")
        self.assertEqual(m2.properties.get("lineageTag"), "meas-tag-1")

        # Partition
        parts = [c for c in tbl.children if c.keyword == "partition"]
        self.assertEqual(len(parts), 1)
        p1 = parts[0]
        self.assertEqual(p1.name, "Sales-Partition")
        self.assertEqual(p1.properties.get("mode"), "import")
        self.assertIn('Sql.Database("srv", "db")', p1.properties.get("source", ""))

    def test_measure_with_is_hidden_flag(self):
        content = """table Test
\tmeasure HiddenMeasure = SELECTEDVALUE('Test'[Col], 0)
\t\tisHidden
\t\tlineageTag: 30a1a858-afcc-4343-802b-5b2229eccc0e
"""
        roots = parse_tmdl(content)
        tbl = roots[0]
        meas = tbl.children[0]
        self.assertEqual(meas.name, "HiddenMeasure")
        self.assertEqual(meas.expression, "SELECTEDVALUE('Test'[Col], 0)")
        self.assertNotIn("isHidden", meas.expression)
        self.assertIn("isHidden", meas.flags)
        self.assertEqual(meas.properties.get("lineageTag"), "30a1a858-afcc-4343-802b-5b2229eccc0e")

    def test_backtick_dax_expression(self):
        content = """table Test
\tmeasure 'Backtick Calc' = ```dax
\t\tVAR x = 1
\t\t// formatString: dummy comment that should not break parsing
\t\tRETURN x
\t\t```
\t\tformatString: #,##0
"""
        roots = parse_tmdl(content)
        meas = roots[0].children[0]
        self.assertEqual(meas.name, "Backtick Calc")
        self.assertIn("VAR x = 1", meas.expression)
        self.assertIn("formatString: dummy comment", meas.expression)
        self.assertIn("RETURN x", meas.expression)
        self.assertEqual(meas.properties.get("formatString"), "#,##0")

    def test_relationships_parsing(self):
        content = """relationship rel-1
\tfromColumn: Sales.CustomerKey
\ttoColumn: Customer.CustomerKey

relationship rel-2
\tcrossFilteringBehavior: bothDirections
\tfromCardinality: one
\tfromColumn: 'Sales Order'.LineKey
\ttoColumn: Sales.LineKey
\tisActive: false
"""
        roots = parse_tmdl(content)
        self.assertEqual(len(roots), 2)
        r1 = roots[0]
        self.assertEqual(r1.name, "rel-1")
        self.assertEqual(r1.properties.get("fromColumn"), "Sales.CustomerKey")
        self.assertEqual(r1.properties.get("toColumn"), "Customer.CustomerKey")

        r2 = roots[1]
        self.assertEqual(r2.name, "rel-2")
        self.assertEqual(r2.properties.get("crossFilteringBehavior"), "bothDirections")
        self.assertEqual(r2.properties.get("fromCardinality"), "one")
        self.assertEqual(r2.properties.get("isActive"), "false")


if __name__ == "__main__":
    unittest.main()

