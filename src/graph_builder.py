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
        graph.add_edge(
            interaction["source"],
            interaction["target"],
            weight=interaction["weight"]
        )

    return graph