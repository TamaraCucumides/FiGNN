from data_loader import load_relational_data
from utils import add_reverse_edges
from torch_geometric.data import HeteroData
import torch
import pandas as pd
import copy

def build_fk_graph(db):
    """
    Build a heterogeneous graph from the relational database.

    Args:
        db (RelationalDatabase): The relational schema and data.

    Returns:
        data (HeteroData): A typed heterogeneous graph
        node_id_maps (dict): Maps table -> {pk_value: node_index}
    """
    data = HeteroData()
    node_id_maps = {}  # Maps: table_name → {pk_value: node_index}

    # --- Step 1: Add node types ---
    for table_name, df in db.tables.items():
        pk = db.primary_keys[table_name]
        pk_values = df[pk].tolist()

        # Build map from primary key value to node index
        id_map = {pkv: idx for idx, pkv in enumerate(pk_values)}
        node_id_maps[table_name] = id_map

        num_nodes = len(df)
        data[table_name].node_ids = torch.tensor(pk_values)

        # Heuristic: bridge tables usually appear only as FK sources
        is_bridge = all(
            fk[0] == table_name and fk[2] != table_name
            for fk in db.foreign_keys
        )

        if not is_bridge:
            # Assign one-hot features to entity tables
            # TODO: change after with some nice encoding
            data[table_name].x = torch.eye(num_nodes)
        else:
            # Assign small dummy features to bridge tables
            data[table_name].x = torch.ones((num_nodes, 1))
            print(f"[build_fk_graph] Added dummy features to bridge table '{table_name}'")

    # --- Step 2: Add foreign key edges ---
    for src_table, src_col, dst_table, dst_col in db.foreign_keys:
        src_df = db.get_table(src_table)
        dst_map = node_id_maps[dst_table]
        src_map = node_id_maps[src_table]
        src_pk = db.primary_keys[src_table]

        src_nodes = []
        dst_nodes = []

        for _, row in src_df.iterrows():
            if pd.isna(row[src_col]) or pd.isna(row[src_pk]):
                continue
            src_id = row[src_pk]
            dst_id = row[src_col]

            if dst_id in dst_map and src_id in src_map:
                src_nodes.append(src_map[src_id])
                dst_nodes.append(dst_map[dst_id])

        edge_index = torch.tensor([src_nodes, dst_nodes], dtype=torch.long)
        edge_type = (src_table, f"{src_col}_to_{dst_col}", dst_table)
        data[edge_type].edge_index = edge_index

    # --- Step 3: Ensure all node types have x ---
    for node_type in data.node_types:
        x = data[node_type].x
        if x is None or not isinstance(x, torch.Tensor):
            num_nodes = data[node_type].num_nodes
            data[node_type].x = torch.ones((num_nodes, 1))
            print(f"[build_fk_graph] Fallback: added dummy features to '{node_type}'")

    # --- Step 4: Add reverse edges ---
    data = add_reverse_edges(data)

    return data, node_id_maps


def promote_attribute(
    graph,
    db,
    table: str,
    attribute: str,
    node_id_map: dict,
    modify_db: bool = False,
    inplace: bool = False
):
    """
    Promote a categorical attribute into a node type and connect entities to their attribute values.
    Ensures new attribute node type has valid `.x` features.
    """
    if not inplace:
        graph = copy.deepcopy(graph)

    df = db.get_table(table)
    pk = db.primary_keys[table]

    # Get all unique non-null values
    values = df[attribute].dropna().unique().tolist()
    value_to_index = {val: idx for idx, val in enumerate(values)}

    attr_node_type = attribute
    num_values = len(values)

    # Create one-hot or dummy feature for attribute nodes
    if num_values > 0:
        graph[attr_node_type].x = torch.eye(num_values)
        graph[attr_node_type].value_strings = values
    else:
        graph[attr_node_type].x = torch.ones((1, 1))  # fallback for edge cases
        graph[attr_node_type].value_strings = []

    # Create edges from entity to attribute value node
    src_nodes, dst_nodes = [], []

    for _, row in df.iterrows():
        if pd.isna(row[attribute]) or pd.isna(row[pk]):
            continue
        attr_val = row[attribute]
        entity_id = row[pk]
        if attr_val in value_to_index and entity_id in node_id_map[table]:
            src_idx = node_id_map[table][entity_id]
            dst_idx = value_to_index[attr_val]
            src_nodes.append(src_idx)
            dst_nodes.append(dst_idx)

    if len(src_nodes) > 0:
        edge_index = torch.tensor([src_nodes, dst_nodes], dtype=torch.long)
        edge_type = (table, f"has_{attribute}", attribute)
        graph[edge_type].edge_index = edge_index
    else:
        print(f"[promote_attribute] WARNING: No valid edges for attribute '{attribute}'")

    if modify_db:
        attr_df = pd.DataFrame({f"{attribute}_id": values})
        db.tables[attribute] = attr_df
        db.primary_keys[attribute] = f"{attribute}_id"
        db.foreign_keys.append((table, attribute, attribute, f"{attribute}_id"))

    # --- Step 4: Add reverse edges ---
    graph = add_reverse_edges(graph)

    return graph

if __name__ == "__main__":
    print("=== Graph Builder Test ===")

    # 1. Load the database and build the initial graph
    db = load_relational_data("data/synthetic")
    graph, id_maps = build_fk_graph(db)

    print("\n[Original Graph]")
    print(graph)
    db.print_schema()

    # 2. Promote with inplace=False (should NOT change the original graph)
    print("\n[Test 1] Promote attribute with inplace=False")
    graph_copy = promote_attribute(
        graph,
        db,
        table="users",
        attribute="region",
        node_id_map=id_maps,
        modify_db=False,
        inplace=False
    )

    print("→ Modified graph (copy):", graph_copy)
    print("→ Original graph still unchanged:")
    print(graph)

    # 3. Promote with inplace=True (should modify the original graph)
    print("\n[Test 2] Promote attribute with inplace=True")
    graph = promote_attribute(
        graph,
        db,
        table="users",
        attribute="region",
        node_id_map=id_maps,
        modify_db=False,
        inplace=True
    )

    print("→ Graph after inplace promotion:")
    print(graph)

    # 4. Inspect schema (should be unchanged unless modify_db=True was used)
    print("\n[Current Schema]")
    db.print_schema()

