import networkx as nx


def build_graph(characters: list[dict], interactions: list[dict]):
    graph = nx.Graph()

    for character in characters:
        graph.add_node(
            character["character_id"],
            label=character["canonical_name"],
            names=character["canonical_name"]
        )

    for interaction in interactions:
        edge_attributes = {"weight": interaction["weight"]}
        for attribute in (
            "polarity",
            "sentiment",
            "polarity_width",
            "polarity_evidence",
        ):
            if attribute in interaction:
                edge_attributes[attribute] = interaction[attribute]

        graph.add_edge(
            interaction["source"],
            interaction["target"],
            **edge_attributes,
        )

    return graph
