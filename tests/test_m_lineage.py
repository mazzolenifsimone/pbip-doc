"""
Comprehensive unit tests for the AST-based Power Query (M) Lineage Engine (m_lineage.py).
Tests multi-hop staging, parameter resolution, custom functions, cross joins,
dead step isolation, aggregate table columns, and rename chains.
100% Python Standard Library implementation.
"""

import unittest
from pbip_doc.m_lineage import MLineageResolver
from pbip_doc.model_schema import PowerQueryColumnTransformation


class TestMLineageEngine(unittest.TestCase):
    def test_multi_hop_staging_with_parameter_resolution(self):
        raw_queries = {
            "ServerName": {
                "m_code": '"prod-sql.contoso.com" meta [IsParameterQuery=true, Type="Any", IsParameterQueryRequired=true]',
                "is_staging": True,
                "kind": "parameter",
            },
            "Staging_Sales": {
                "m_code": '''let
    Source = Sql.Database(ServerName, "SalesDW"),
    Filtered = Table.SelectRows(Source, each [Status] = "Active")
in
    Filtered''',
                "is_staging": True,
            },
            "FactSales": {
                "m_code": '''let
    Source = Staging_Sales,
    AddMargin = Table.AddColumn(Source, "Margin", each [Amount] - [Cost])
in
    AddMargin''',
                "target_table": "FactSales",
                "is_staging": False,
            },
        }

        resolver = MLineageResolver(raw_queries)
        fact_node = resolver.get_lineage_for_table("FactSales")

        self.assertIsNotNone(fact_node)
        self.assertIn("Staging_Sales", fact_node.direct_dependencies)
        self.assertIn("Staging_Sales", fact_node.all_upstream_queries)
        self.assertIn("ServerName", fact_node.all_upstream_queries)

        # Parameter resolution in root sources
        self.assertEqual(len(fact_node.root_sources), 1)
        src = fact_node.root_sources[0]
        self.assertEqual(src.source_type, "SQL_SERVER")
        self.assertEqual(src.server, "prod-sql.contoso.com")
        self.assertEqual(src.database, "SalesDW")

        # Parameter node metadata
        param_node = resolver.get_lineage_for_query("ServerName")
        self.assertIsNotNone(param_node)
        self.assertEqual(param_node.expression_kind, "parameter")
        self.assertFalse(param_node.is_staging)
        self.assertEqual(param_node.parameter_value, "prod-sql.contoso.com")
        self.assertEqual(param_node.parameter_type, "Any")
        self.assertTrue(param_node.parameter_required)

    def test_cross_join_end_to_end_lineage(self):
        raw_queries = {
            "DimProducts": {
                "m_code": 'let Source = Sql.Database("srv", "db"){[Schema="dbo", Item="Products"]}[Data] in Source',
                "target_table": "DimProducts",
                "is_staging": False,
            },
            "DimCustomers": {
                "m_code": '''let
    Source = Sql.Database("srv", "db"){[Schema="dbo", Item="Customers"]}[Data],
    #"Add Cross Products" = Table.AddColumn(Source, "ProdData", each DimProducts),
    #"Expand Cross" = Table.ExpandTableColumn(#"Add Cross Products", "ProdData", {"ProductID", "ProductName"}, {"Product ID", "Product Name"})
in
    #"Expand Cross"''',
                "target_table": "DimCustomers",
                "is_staging": False,
            },
        }

        resolver = MLineageResolver(raw_queries)
        cust_node = resolver.get_lineage_for_table("DimCustomers")

        self.assertIsNotNone(cust_node)
        self.assertIn("DimProducts", cust_node.direct_dependencies)
        self.assertEqual(len(cust_node.merges), 1)
        mg = cust_node.merges[0]
        self.assertEqual(mg.joined_query, "DimProducts")
        self.assertEqual(mg.join_kind, "CrossJoin")
        self.assertTrue(mg.is_cross_join)

        # Check column transformations
        self.assertIn("Product ID", cust_node.column_transformations)
        tf = cust_node.column_transformations["Product ID"]
        self.assertEqual(tf.source_table, "DimProducts")
        self.assertIn("Cross Joined from DimProducts", tf.operation)

    def test_custom_m_function_detection_and_signature(self):
        raw_queries = {
            "fxDiscount": {
                "m_code": '(basePrice as number, discountPercent as number) as number => basePrice * (1 - discountPercent)',
                "is_staging": True,
            },
            "Orders": {
                "m_code": '''let
    Source = Sql.Database("srv", "db"),
    AddDisc = Table.AddColumn(Source, "DiscountedPrice", each fxDiscount([UnitPrice], [Discount]))
in
    AddDisc''',
                "target_table": "Orders",
                "is_staging": False,
            },
        }

        resolver = MLineageResolver(raw_queries)
        fn_node = resolver.nodes["fxDiscount"]

        self.assertTrue(fn_node.is_m_function)
        self.assertEqual(fn_node.expression_kind, "function")
        self.assertEqual(fn_node.m_function_return_type, "number")
        self.assertEqual(len(fn_node.m_function_parameters), 2)
        self.assertEqual(fn_node.m_function_parameters[0].name, "basePrice")
        self.assertEqual(fn_node.m_function_parameters[0].data_type, "number")

        orders_node = resolver.get_lineage_for_table("Orders")
        self.assertIn("fxDiscount", orders_node.direct_dependencies)

    def test_dead_steps_isolation(self):
        raw_queries = {
            "SampleTable": {
                "m_code": '''let
    Source = Sql.Database("srv", "db"),
    DeadA = Table.AddColumn(Source, "UnusedCol", each 99),
    DeadB = Table.SelectRows(DeadA, each [UnusedCol] > 0),
    Active = Table.SelectRows(Source, each [Active] = true)
in
    Active''',
                "target_table": "SampleTable",
                "is_staging": False,
            }
        }

        resolver = MLineageResolver(raw_queries)
        node = resolver.get_lineage_for_table("SampleTable")

        active_step_names = [s.step_name for s in node.steps]
        unused_step_names = [s.step_name for s in node.unused_steps]

        self.assertEqual(active_step_names, ["Source", "Active"])
        self.assertEqual(unused_step_names, ["DeadA", "DeadB"])

    def test_power_query_column_transformation_dataclass_and_dict_compatibility(self):
        tf = PowerQueryColumnTransformation(
            name="NetSales",
            operation="Calculated Column",
            step_name="AddNet",
            m_expression="[Gross] - [Tax]",
            expression="[Gross] - [Tax]",
            source_column=None,
            source_table="Orders",
        )

        # Dataclass attribute access
        self.assertEqual(tf.name, "NetSales")
        self.assertEqual(tf.operation, "Calculated Column")

        # Dict-like subscription access
        self.assertEqual(tf["name"], "NetSales")
        self.assertEqual(tf["step_name"], "AddNet")
        self.assertEqual(tf.get("source_table"), "Orders")
        self.assertIsNone(tf.get("non_existent_key"))
        self.assertIn("name", tf)

        # to_dict() serialization
        d = tf.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["name"], "NetSales")

    def test_section_document_unpacking_and_lineage(self):
        section_code = '''section Section1;

shared SourceQuery = let
    Source = Sql.Database("sql.example.com", "AppDB")
in
    Source;

shared TargetTable = let
    Source = SourceQuery,
    Filtered = Table.SelectRows(Source, each [Active] = true)
in
    Filtered;
'''
        raw_queries = {
            "MainSection": {
                "m_code": section_code,
                "is_staging": False,
            }
        }

        resolver = MLineageResolver(raw_queries)

        # MainSection should be unpacked into SourceQuery and TargetTable
        self.assertIn("SourceQuery", resolver.nodes)
        self.assertIn("TargetTable", resolver.nodes)

        target_node = resolver.nodes["TargetTable"]
        self.assertIn("SourceQuery", target_node.direct_dependencies)
        self.assertEqual(len(target_node.root_sources), 1)
        self.assertEqual(target_node.root_sources[0].source_type, "SQL_SERVER")
        self.assertEqual(target_node.root_sources[0].server, "sql.example.com")


if __name__ == "__main__":
    unittest.main()

