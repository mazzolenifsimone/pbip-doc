"""
Unit tests for the Power Query M Step Graph and Intra-Query Analyzer (m_step_graph.py).
100% Python Standard Library implementation.
"""

import unittest
from pbip_doc.m_parser import parse_m
from pbip_doc.m_step_graph import MStepGraph


class TestMStepGraph(unittest.TestCase):
    def test_backward_slicing_isolates_dead_steps(self):
        code = """let
    Source = Sql.Database("myserver", "mydb"),
    DeadStep1 = Table.SelectRows(Source, each [Amount] < 0),
    DeadStep2 = Table.AddColumn(DeadStep1, "Negative", each true),
    ActiveStep = Table.SelectRows(Source, each [Amount] >= 0),
    Final = Table.TransformColumnTypes(ActiveStep, {{"Amount", type number}})
in
    Final"""
        ast = parse_m(code)
        graph = MStepGraph(ast, raw_code=code)

        active_names = [s.name for s in graph.active_steps]
        unused_names = [s.name for s in graph.unused_steps]

        self.assertEqual(active_names, ["Source", "ActiveStep", "Final"])
        self.assertEqual(unused_names, ["DeadStep1", "DeadStep2"])

        unused_lineage = graph.get_unused_steps()
        self.assertEqual(len(unused_lineage), 2)
        self.assertIn("Unused", unused_lineage[0].operation)

    def test_cross_join_via_add_column(self):
        code = """let
    Source = Customers,
    #"Cross Joined Products" = Table.AddColumn(Source, "ProductsData", each Products),
    #"Expanded Products" = Table.ExpandTableColumn(#"Cross Joined Products", "ProductsData", {"ProductID", "Price"}, {"Product ID", "Unit Price"})
in
    #"Expanded Products" """
        ast = parse_m(code)
        graph = MStepGraph(ast, raw_code=code, known_query_names={"Customers", "Products"})

        # Check merge detection
        self.assertEqual(len(graph.merges), 1)
        merge = graph.merges[0]
        self.assertEqual(merge.joined_query, "Products")
        self.assertEqual(merge.join_kind, "CrossJoin")
        self.assertTrue(merge.is_cross_join)
        self.assertEqual(merge.expanded_columns, ["Product ID", "Unit Price"])

        # Check column transformations
        self.assertIn("Product ID", graph.column_transformations)
        self.assertIn("Cross Joined from Products", graph.column_transformations["Product ID"].operation)
        self.assertEqual(graph.column_transformations["Product ID"].source_table, "Products")

    def test_add_column_with_parameter_is_not_cross_join(self):
        code = """let
    Source = Customers,
    #"Added Flag" = Table.AddColumn(Source, "ErrorFlag", each ForceError)
in
    #"Added Flag" """
        ast = parse_m(code)
        graph = MStepGraph(ast, raw_code=code, known_query_names={"Customers", "ForceError"}, known_parameter_names={"ForceError"})

        # Must NOT be detected as a merge/cross join
        self.assertEqual(len(graph.merges), 0)
        self.assertIn("ErrorFlag", graph.column_transformations)
        self.assertEqual(graph.column_transformations["ErrorFlag"].operation, "Calculated Column")

    def test_aggregate_table_column_support(self):
        code = """let
    Source = Orders,
    #"Merged Details" = Table.NestedJoin(Source, {"OrderID"}, OrderDetails, {"OrderID"}, "Details", JoinKind.LeftOuter),
    #"Aggregated Details" = Table.AggregateTableColumn(#"Merged Details", "Details", {{"Quantity", List.Sum, "Total Quantity"}, {"Amount", List.Average, "Avg Amount"}})
in
    #"Aggregated Details" """
        ast = parse_m(code)
        graph = MStepGraph(ast, raw_code=code, known_query_names={"Orders", "OrderDetails"})

        self.assertEqual(len(graph.merges), 1)
        self.assertEqual(graph.merges[0].joined_query, "OrderDetails")
        self.assertEqual(graph.merges[0].expanded_columns, ["Total Quantity", "Avg Amount"])

        self.assertIn("Total Quantity", graph.column_transformations)
        self.assertIn("Aggregated from OrderDetails", graph.column_transformations["Total Quantity"].operation)
        self.assertEqual(graph.column_transformations["Total Quantity"].source_column, "Quantity")

        self.assertIn("Avg Amount", graph.column_transformations)
        self.assertEqual(graph.column_transformations["Avg Amount"].source_column, "Amount")

    def test_rename_column_chain_resolution(self):
        code = """let
    Source = Sql.Database("server", "db"),
    #"Added Col" = Table.AddColumn(Source, "GrossAmount", each [Qty] * [Price]),
    #"Renamed Col" = Table.RenameColumns(#"Added Col", {{"GrossAmount", "Total Sales"}})
in
    #"Renamed Col" """
        ast = parse_m(code)
        graph = MStepGraph(ast, raw_code=code)

        # "GrossAmount" should be resolved forward to "Total Sales"
        self.assertNotIn("GrossAmount", graph.column_transformations)
        self.assertIn("Total Sales", graph.column_transformations)
        tf = graph.column_transformations["Total Sales"]
        self.assertEqual(tf.source_column, "GrossAmount")
        self.assertIn("[Qty] * [Price]", tf.m_expression)
        self.assertIn("Renamed from [GrossAmount]", tf.m_expression)

    def test_physical_navigation_extraction(self):
        code = """let
    Source = Sql.Database("prod-server.database.windows.net", "SalesDWH"),
    Navigation = Source{[Schema="sales", Item="FactOrders"]}[Data]
in
    Navigation"""
        ast = parse_m(code)
        graph = MStepGraph(ast, raw_code=code)

        self.assertEqual(len(graph.root_sources), 1)
        src = graph.root_sources[0]
        self.assertEqual(src.source_type, "SQL_SERVER")
        self.assertEqual(src.server, "prod-server.database.windows.net")
        self.assertEqual(src.database, "SalesDWH")
        self.assertEqual(src.endpoint_or_path, "sales.FactOrders")
        self.assertIn("[sales.FactOrders]", src.connection_string)

    def test_native_query_extraction(self):
        code = """let
    Source = Sql.Database("srv", "db"),
    Query = Value.NativeQuery(Source, "SELECT OrderID, Amount FROM dbo.Orders WHERE Status = 'A'")
in
    Query"""
        ast = parse_m(code)
        graph = MStepGraph(ast, raw_code=code)

        native_src = [s for s in graph.root_sources if s.source_type == "SQL_NATIVE_QUERY"]
        self.assertEqual(len(native_src), 1)
        self.assertIn("SELECT OrderID, Amount FROM dbo.Orders", native_src[0].raw_snippet)

    def test_custom_function_metadata(self):
        code = '(x as number, optional y as text) as number => x + 1'
        ast = parse_m(code)
        graph = MStepGraph(ast, raw_code=code)

        self.assertTrue(graph.is_custom_function)
        self.assertEqual(graph.function_return_type, "number")
        self.assertEqual(len(graph.function_parameters), 2)
        self.assertEqual(graph.function_parameters[0].name, "x")
        self.assertFalse(graph.function_parameters[0].is_optional)
        self.assertEqual(graph.function_parameters[1].name, "y")
        self.assertTrue(graph.function_parameters[1].is_optional)

    def test_lineage_steps_with_scope_and_details(self):
        code = """let
    Source = Sql.Database("server", "db"),
    #"Filtered Rows" = Table.SelectRows(Source, each [Amount] > 0),
    #"Added Flag" = Table.AddColumn(#"Filtered Rows", "ErrorFlag", each ForceError),
    #"Selected Cols" = Table.SelectColumns(#"Added Flag", {"OrderID", "ErrorFlag"})
in
    #"Selected Cols" """
        ast = parse_m(code)
        graph = MStepGraph(ast, raw_code=code, known_query_names={"ForceError"}, known_parameter_names={"ForceError"})

        steps = graph.get_lineage_steps()
        self.assertEqual(len(steps), 4)

        # Step 3: Added Flag
        step3 = steps[2]
        self.assertEqual(step3.step_name, "Added Flag")
        self.assertEqual(step3.operation, "Calculated Column")
        self.assertEqual(step3.transformed_column, "ErrorFlag")
        self.assertEqual(step3.referenced_queries, ["ForceError"])
        self.assertIn("ForceError", step3.details)

        # Step 4: Selected Cols
        step4 = steps[3]
        self.assertEqual(step4.step_name, "Selected Cols")
        self.assertIn("OrderID, ErrorFlag", step4.transformed_column)

    def test_parentheses_preservation_in_m_formulas(self):
        from pbip_doc.m_step_graph import _ast_to_raw_snippet

        # 1. Arithmetic operator precedence: (A + B) / C
        code_arith = "(A + B) / C"
        ast_arith = parse_m(code_arith)
        self.assertEqual(_ast_to_raw_snippet(ast_arith), "(A + B) / C")

        # 2. Nested boolean condition in if expression
        code_if = 'if ((TableToFail = "Products" and RandomError = "TRUE") or ForceError = "TRUE") then error "Forced Error" else Products_table'
        ast_if = parse_m(code_if)
        snippet = _ast_to_raw_snippet(ast_if)
        self.assertIn('((TableToFail = "Products" and RandomError = "TRUE") or ForceError = "TRUE")', snippet)


if __name__ == "__main__":
    unittest.main()

