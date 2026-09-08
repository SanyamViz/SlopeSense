"""Graph-based infrastructure risk analysis.

Builds a network of village zones and safe nodes (shelters / hospitals) from
hand-authored road segments, then simulates zone isolation when a high / severe
zone loses all traversable edges.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

HIGH_SEVERE = {"high", "severe"}


def build_graph(edges: list[dict[str, Any]]) -> nx.Graph:
    """Create an undirected road network from edge records.

    Each edge record must contain:
      - from: source node id
      - to: target node id
      - road_id: stable road segment identifier
      - passes_through_zone_id: the zone whose risk can sever this segment
    """
    g = nx.Graph()
    for e in edges:
        g.add_edge(
            e["from"],
            e["to"],
            road_id=e.get("road_id"),
            passes_through_zone_id=e.get("passes_through_zone_id"),
        )
    logger.info("Built graph with %d nodes and %d edges", g.number_of_nodes(), g.number_of_edges())
    return g


def _structural_analysis(graph: nx.Graph) -> dict[str, Any]:
    """Compute articulation points and bridges on the original graph."""
    bridges = list(nx.bridges(graph))
    return {
        "articulation_points": sorted(list(nx.articulation_points(graph))),
        "bridges": sorted(
            [
                (u, v, data.get("road_id"))
                for u, v, data in graph.edges(data=True)
                if (u, v) in bridges or (v, u) in bridges
            ],
            key=lambda x: x[2],
        ),
    }


def find_stranded_zones(
    graph: nx.Graph,
    scored_locations: list[dict[str, Any]],
    safe_node_ids: list[str],
    node_names: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Detect zones stranded from all safe infrastructure when blockers go high/severe.

    For each location with risk_level in {high, severe}:
      1. Copy the graph and remove every edge whose passes_through_zone_id matches
         the blocker.
      2. For every remaining non-safe node, check reachability to any safe node
         using nx.has_path.
      3. Zones that lose every path to every safe node are stranded.

    Returns a list of dicts:
      { zone_id, blocked_by_zone_id, isolated_from: [safe_node_ids...], reason }
    """
    scored_map = {loc["location_id"]: loc for loc in scored_locations}
    blockers = [lid for lid, loc in scored_map.items() if loc.get("risk_level") in HIGH_SEVERE]
    node_names = node_names or {}

    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for blocker_id in blockers:
        g = graph.copy()
        removed = [
            (u, v)
            for u, v, d in g.edges(data=True)
            if d.get("passes_through_zone_id") == blocker_id
        ]
        for u, v in removed:
            g.remove_edge(u, v)

        blocker_name = node_names.get(blocker_id) or scored_map.get(blocker_id, {}).get("name", blocker_id)

        for zone_id in list(g.nodes):
            if zone_id in safe_node_ids:
                continue
            reachable_safe = [sid for sid in safe_node_ids if nx.has_path(g, zone_id, sid)]
            if not reachable_safe:
                key = (zone_id, blocker_id)
                if key not in seen:
                    seen.add(key)
                    zone_name = node_names.get(zone_id) or scored_map.get(zone_id, {}).get("name", zone_id)
                    zone_risk = scored_map.get(zone_id, {}).get("risk_level", "unknown")
                    results.append({
                        "zone_id": zone_id,
                        "blocked_by_zone_id": blocker_id,
                        "isolated_from": reachable_safe,
                        "reason": (
                            f"{zone_name} itself is {zone_risk} risk, but is cut off from all "
                            f"shelters/hospitals if {blocker_name} slides."
                        ),
                    })

    return results


def analyze(
    edges: list[dict[str, Any]],
    scored_locations: list[dict[str, Any]],
    safe_node_ids: list[str],
    nodes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Full analysis: build graph, compute stranded zones, flag structural weak points."""
    graph = build_graph(edges)
    if nodes:
        for n in nodes:
            if n["id"] in graph.nodes:
                graph.nodes[n["id"]].update({k: v for k, v in n.items() if k != "id"})
            else:
                graph.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
    node_names = {n: graph.nodes[n].get("name", n) for n in graph.nodes}
    stranded = find_stranded_zones(graph, scored_locations, safe_node_ids, node_names=node_names)
    structure = _structural_analysis(graph)
    return {
        "nodes": [{"id": n, **graph.nodes[n]} for n in graph.nodes],
        "edges": [
            {
                "from": u,
                "to": v,
                "road_id": d.get("road_id"),
                "passes_through_zone_id": d.get("passes_through_zone_id"),
            }
            for u, v, d in graph.edges(data=True)
        ],
        "stranded_zones": stranded,
        "structural_analysis": structure,
    }
