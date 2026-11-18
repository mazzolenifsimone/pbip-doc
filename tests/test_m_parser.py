"""
Unit tests for the Power Query M Lexer and Recursive-Descent AST Parser (m_parser.py).
100% Python Standard Library implementation.
"""

import unittest
from pbip_doc.m_parser import (
    MLexer, MParser, parse_m,
    TOKEN_IDENTIFIER, TOKEN_STRING, TOKEN_NUMBER, TOKEN_KEYWORD, TOKEN_OPERATOR,
    MLetExpr, MStep, MFunctionExpr, MEachExpr, MIfExpr, MTryExpr,
    MInvocationExpr, MItemAccessExpr, MFieldAccessExpr, MRecordExpr,
    MListExpr, MBinaryExpr, MUnaryExpr, MMetadataExpr, MTypeExpr,
    MIdentifier, MLiteral, MUnresolvedExpr, MSectionDocument, MSectionMember
)


class TestMLexer(unittest.TestCase):
    def test_identifiers_and_quoted_identifiers(self):
        code = 'Source #"Promoted Headers" #"Step with ""quotes""" Table.AddColumn'
        lexer = MLexer(code)
        tokens = lexer.tokenize()

        self.assertEqual(tokens[0].type, TOKEN_IDENTIFIER)
        self.assertEqual(tokens[0].value, "Source")

        self.assertEqual(tokens[1].type, TOKEN_IDENTIFIER)
        self.assertEqual(tokens[1].value, "Promoted Headers")

        self.assertEqual(tokens[2].type, TOKEN_IDENTIFIER)
        self.assertEqual(tokens[2].value, 'Step with "quotes"')

        self.assertEqual(tokens[3].type, TOKEN_IDENTIFIER)
        self.assertEqual(tokens[3].value, "Table.AddColumn")

    def test_strings_with_quotes(self):
        code = '"Simple String" "String with ""escaped"" quotes" ""'
        lexer = MLexer(code)
        tokens = lexer.tokenize()

        self.assertEqual(tokens[0].type, TOKEN_STRING)
        self.assertEqual(tokens[0].value, "Simple String")

        self.assertEqual(tokens[1].type, TOKEN_STRING)
        self.assertEqual(tokens[1].value, 'String with "escaped" quotes')

        self.assertEqual(tokens[2].type, TOKEN_STRING)
        self.assertEqual(tokens[2].value, "")

    def test_numbers(self):
        code = "123 45.67 1e-4 0xFF"
        lexer = MLexer(code)
        tokens = lexer.tokenize()

        self.assertEqual(tokens[0].value, 123)
        self.assertEqual(tokens[1].value, 45.67)
        self.assertEqual(tokens[2].value, 1e-4)
        self.assertEqual(tokens[3].value, 255)

    def test_comments_skipping_and_preservation(self):
        code = """// Line comment
Source = 1, /* Block comment */
Next = 2"""
        lexer_no_comments = MLexer(code, include_comments=False)
        tokens = lexer_no_comments.tokenize()
        token_values = [t.value for t in tokens if t.type != "EOF"]
        self.assertNotIn("Line comment", token_values)
        self.assertNotIn("Block comment", token_values)

        lexer_comments = MLexer(code, include_comments=True)
        tokens_with = lexer_comments.tokenize()
        comment_tokens = [t for t in tokens_with if t.type == "COMMENT"]
        self.assertEqual(len(comment_tokens), 2)
        self.assertEqual(comment_tokens[0].value, "Line comment")
        self.assertEqual(comment_tokens[1].value, "Block comment")


class TestMParser(unittest.TestCase):
    def test_simple_let_expression(self):
        code = """let
    Source = Sql.Database("myserver", "mydb"),
    #"Filtered Rows" = Table.SelectRows(Source, each [Amount] > 100)
in
    #"Filtered Rows" """
        ast = parse_m(code)
        self.assertIsInstance(ast, MLetExpr)
        self.assertEqual(len(ast.steps), 2)
        self.assertEqual(ast.steps[0].name, "Source")
        self.assertEqual(ast.steps[1].name, "Filtered Rows")

        self.assertIsInstance(ast.in_expr, MIdentifier)
        self.assertEqual(ast.in_expr.name, "Filtered Rows")

        # Step 1: Sql.Database invocation
        step1_val = ast.steps[0].value
        self.assertIsInstance(step1_val, MInvocationExpr)
        self.assertEqual(step1_val.function.name, "Sql.Database")
        self.assertEqual(len(step1_val.arguments), 2)
        self.assertEqual(step1_val.arguments[0].value, "myserver")
        self.assertEqual(step1_val.arguments[1].value, "mydb")

    def test_nested_let_expression(self):
        code = """let
    Outer = let Inner = 42 in Inner
in
    Outer"""
        ast = parse_m(code)
        self.assertIsInstance(ast, MLetExpr)
        self.assertEqual(len(ast.steps), 1)
        self.assertIsInstance(ast.steps[0].value, MLetExpr)
        inner_let = ast.steps[0].value
        self.assertEqual(inner_let.steps[0].name, "Inner")
        self.assertEqual(inner_let.steps[0].value.value, 42)

    def test_item_access_and_physical_navigation(self):
        code = 'Source{[Schema="dbo", Item="FactSales"]}[Data]'
        ast = parse_m(code)
        # Target: FieldAccess on Data
        self.assertIsInstance(ast, MFieldAccessExpr)
        self.assertEqual(ast.field_name, "Data")

        # Target: ItemAccess {[Schema="dbo", Item="FactSales"]}
        item_access = ast.target
        self.assertIsInstance(item_access, MItemAccessExpr)
        self.assertIsInstance(item_access.target, MIdentifier)
        self.assertEqual(item_access.target.name, "Source")

        # Record inside item lookup
        record = item_access.item
        self.assertIsInstance(record, MRecordExpr)
        field_dict = {k: v.value for k, v in record.fields}
        self.assertEqual(field_dict, {"Schema": "dbo", "Item": "FactSales"})

    def test_custom_function_definition(self):
        code = '(x as number, optional y as text) as number => x + 1'
        ast = parse_m(code)
        self.assertIsInstance(ast, MFunctionExpr)
        self.assertEqual(len(ast.parameters), 2)
        self.assertEqual(ast.parameters[0].name, "x")
        self.assertEqual(ast.parameters[0].type_name, "number")
        self.assertFalse(ast.parameters[0].is_optional)

        self.assertEqual(ast.parameters[1].name, "y")
        self.assertEqual(ast.parameters[1].type_name, "text")
        self.assertTrue(ast.parameters[1].is_optional)

        self.assertEqual(ast.return_type, "number")
        self.assertIsInstance(ast.body, MBinaryExpr)
        self.assertEqual(ast.body.operator, "+")

    def test_each_and_standalone_field_access(self):
        code = 'each [UnitPrice] * [Quantity]'
        ast = parse_m(code)
        self.assertIsInstance(ast, MEachExpr)
        self.assertIsInstance(ast.body, MBinaryExpr)
        self.assertEqual(ast.body.operator, "*")
        self.assertIsInstance(ast.body.left, MFieldAccessExpr)
        self.assertEqual(ast.body.left.field_name, "UnitPrice")
        self.assertIsInstance(ast.body.right, MFieldAccessExpr)
        self.assertEqual(ast.body.right.field_name, "Quantity")

    def test_if_then_else(self):
        code = 'if [Status] = "Active" then 1 else 0'
        ast = parse_m(code)
        self.assertIsInstance(ast, MIfExpr)
        self.assertIsInstance(ast.condition, MBinaryExpr)
        self.assertEqual(ast.condition.operator, "=")
        self.assertEqual(ast.then_branch.value, 1)
        self.assertEqual(ast.else_branch.value, 0)

    def test_try_otherwise(self):
        code = 'try [Amount] / [Total] otherwise null'
        ast = parse_m(code)
        self.assertIsInstance(ast, MTryExpr)
        self.assertIsInstance(ast.try_branch, MBinaryExpr)
        self.assertIsInstance(ast.otherwise_branch, MLiteral)
        self.assertIsNone(ast.otherwise_branch.value)

    def test_metadata_expression_and_parameters(self):
        code = '"http://api.contoso.com" meta [IsParameterQuery=true, Type="Any", IsParameterQueryRequired=true]'
        ast = parse_m(code)
        self.assertIsInstance(ast, MMetadataExpr)
        self.assertEqual(ast.expr.value, "http://api.contoso.com")
        self.assertIsInstance(ast.metadata, MRecordExpr)
        meta_dict = {k: v.value for k, v in ast.metadata.fields}
        self.assertTrue(meta_dict["IsParameterQuery"])
        self.assertEqual(meta_dict["Type"], "Any")
        self.assertTrue(meta_dict["IsParameterQueryRequired"])

    def test_lists_and_type_expressions(self):
        code = 'Table.AddColumn(Source, "Tax", each [Amount] * 0.2, type number)'
        ast = parse_m(code)
        self.assertIsInstance(ast, MInvocationExpr)
        self.assertEqual(len(ast.arguments), 4)
        self.assertIsInstance(ast.arguments[3], MTypeExpr)
        self.assertEqual(ast.arguments[3].type_name, "number")

    def test_cross_join_pattern_ast(self):
        code = '''let
    Source = Customers,
    #"Added Products" = Table.AddColumn(Source, "Products", each Products),
    #"Expanded Products" = Table.ExpandTableColumn(#"Added Products", "Products", {"ProductID", "ProductName"}, {"ProductID", "ProductName"})
in
    #"Expanded Products"'''
        ast = parse_m(code)
        self.assertIsInstance(ast, MLetExpr)
        self.assertEqual(len(ast.steps), 3)
        add_col = ast.steps[1].value
        self.assertIsInstance(add_col, MInvocationExpr)
        self.assertEqual(add_col.function.name, "Table.AddColumn")
        self.assertIsInstance(add_col.arguments[2], MEachExpr)
        self.assertIsInstance(add_col.arguments[2].body, MIdentifier)
        self.assertEqual(add_col.arguments[2].body.name, "Products")

    def test_graceful_degradation_on_malformed_syntax(self):
        malformed = 'let Source = @@INVALID SINTAX@@'
        ast = parse_m(malformed)
        # Doesn't crash, returns valid AST or MUnresolvedExpr
        self.assertIsNotNone(ast)

    def test_section_document_parsing(self):
        """Verifies M Section Document parsing according to official grammar."""
        code = '''section DataConnectors;

shared SourceQuery = let
    Source = 1
in
    Source;

shared StaticText = "Hello Enterprise";

PrivateHelper = 42;
'''
        ast = parse_m(code)
        self.assertIsInstance(ast, MSectionDocument)
        self.assertEqual(ast.section_name, "DataConnectors")
        self.assertEqual(len(ast.members), 3)

        # Member 1: SourceQuery (shared let)
        m1 = ast.members[0]
        self.assertEqual(m1.name, "SourceQuery")
        self.assertTrue(m1.is_shared)
        self.assertIsInstance(m1.expression, MLetExpr)

        # Member 2: StaticText (shared string)
        m2 = ast.members[1]
        self.assertEqual(m2.name, "StaticText")
        self.assertTrue(m2.is_shared)
        self.assertIsInstance(m2.expression, MLiteral)
        self.assertEqual(m2.expression.value, "Hello Enterprise")

        # Member 3: PrivateHelper (private number)
        m3 = ast.members[2]
        self.assertEqual(m3.name, "PrivateHelper")
        self.assertFalse(m3.is_shared)

        # Helpers
        shared_map = ast.get_shared_members()
        self.assertEqual(set(shared_map.keys()), {"SourceQuery", "StaticText"})
        all_map = ast.get_all_members()
        self.assertEqual(set(all_map.keys()), {"SourceQuery", "StaticText", "PrivateHelper"})


if __name__ == "__main__":
    unittest.main()
