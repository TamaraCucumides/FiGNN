

def score_attribute(graph, db, table: str, attribute: str, labels: dict, method: str) -> float:
    """
    Unified scoring interface. Dispatches to the appropriate scoring method.

    Args:
        graph: Current (possibly augmented) graph object
        db: RelationalDatabase instance
        table: Table where the attribute is defined
        attribute: Attribute name to score
        labels: Dictionary mapping node IDs to labels
        method: Scoring strategy ("mutual_info", "entropy_gain", "wl_gain", etc.)

    Returns:
        float: Score for the attribute
    """
    if method == "mutual_info":
        return mutual_info_score(graph, db, table, attribute, labels)
    elif method == "entropy_gain":
        return label_entropy_gain(graph, db, table, attribute, labels)
    elif method == "wl_gain":
        return wl_refinement_gain(graph, db, table, attribute, labels)
    elif method == "edge_disagreement":
        return edge_disagreement_rate(graph, db, table, attribute, labels)
    else:
        raise ValueError(f"Unknown scoring method: {method}")

def mutual_info_score(graph, db, table: str, attribute: str, labels: dict) -> float:
    """
    Compute mutual information between attribute values and target labels.
    Only uses the raw table data.
    """
    pass

def label_entropy_gain(graph, db, table: str, attribute: str, labels: dict) -> float:
    """
    Simulate promoting the attribute and compute average label entropy reduction
    in local neighborhoods.
    """
    pass

def wl_refinement_gain(graph, db, table: str, attribute: str, labels: dict) -> float:
    """
    Apply 1-WL color refinement before and after promotion.
    Score is the increase in color class count.
    """
    pass

def edge_disagreement_rate(graph, db, table: str, attribute: str, labels: dict) -> float:
    """
    Compute how often promoting the attribute creates edges between nodes
    with different labels.
    """
    pass

