"""Graph-based infrastructure risk analysis.

Builds a network of village zones and safe nodes (shelters / hospitals) from
hand-authored road segments, then simulates zone isolation when a high / severe
zone loses all traversable edges.

Extended: computes hospital/safe-node capacity, nearby facility counts, and
alternative evacuation routes when primary roads are severed.
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

HIGH_SEVERE = {"high", "severe"}
EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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


def _nearby_safe_nodes(
    zone_id: str,
    graph: nx.Graph,
    radius_km: float = 20.0,
) -> list[dict[str, Any]]:
    """Find safe nodes within ``radius_km`` of the given zone by haversine."""
    zdata = graph.nodes.get(zone_id, {})
    zlat, zlon = zdata.get("lat"), zdata.get("lon")
    if zlat is None or zlon is None:
        return []
    results: list[dict[str, Any]] = []
    for nid, ndata in graph.nodes(data=True):
        if ndata.get("type") != "safe":
            continue
        nlat, nlon = ndata.get("lat"), ndata.get("lon")
        if nlat is None or nlon is None:
            continue
        dist = _haversine_km(zlat, zlon, nlat, nlon)
        if dist <= radius_km:
            cap_total = ndata.get("capacity_total") or 0
            cap_filled = ndata.get("capacity_filled") or 0
            results.append({
                "id": nid,
                "name": ndata.get("name", nid),
                "subtype": ndata.get("subtype", "safe"),
                "distance_km": round(dist, 2),
                "capacity_total": cap_total,
                "capacity_filled": cap_filled,
                "capacity_available": max(cap_total - cap_filled, 0),
            })
    results.sort(key=lambda x: x["distance_km"])
    return results


def _alternative_routes(
    graph: nx.Graph,
    zone_id: str,
    safe_node_ids: list[str],
    blocked_edges: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Compute shortest alternative routes from ``zone_id`` to each safe node
    after removing ``blocked_edges``. Returns only routes that differ from the
    original shortest path."""
    if zone_id not in graph.nodes:
        return []
    g = graph.copy()
    for u, v in blocked_edges:
        if g.has_edge(u, v):
            g.remove_edge(u, v)

    routes: list[dict[str, Any]] = []
    for sid in safe_node_ids:
        try:
            path = nx.shortest_path(g, zone_id, sid)
            length = nx.shortest_path_length(g, zone_id, sid)
            blocked_road_ids = [
                graph.edges[u, v].get("road_id")
                for u, v in zip(path[:-1], path[1:])
                if graph.has_edge(u, v)
                and graph.edges[u, v].get("passes_through_zone_id")
            ]
            routes.append({
                "safe_node_id": sid,
                "safe_node_name": graph.nodes[sid].get("name", sid),
                "path": path,
                "hops": len(path) - 1,
                "estimated_distance_km": round(length * 5.5, 1),
                "blocked_road_ids_on_route": blocked_road_ids,
            })
        except nx.NetworkXNoPath:
            routes.append({
                "safe_node_id": sid,
                "safe_node_name": graph.nodes[sid].get("name", sid),
                "path": None,
                "hops": None,
                "estimated_distance_km": None,
                "blocked_road_ids_on_route": [],
                "unreachable": True,
            })
    return routes


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


def compute_impact_assessment(
    edges: list[dict[str, Any]],
    scored_locations: list[dict[str, Any]],
    nodes: list[dict[str, Any]] | None = None,
    hospital_radius_km: float = 20.0,
) -> dict[str, Any]:
    """Compute per-zone impact assessment for landscape authorities.

    For every zone, returns:
      - nearby_safe_nodes: safe facilities within ``hospital_radius_km`` with
        capacity (total, filled, available) and distance.
      - nearby_hospital_count: number of hospitals within ``hospital_radius_km``.
      - For high/severe zones: alternative evacuation routes after primary
        routes are severed by the blocker.

    Returns:
      {
        zones: [
          {
            zone_id,
            zone_name,
            district,
            risk_level,
            coordinates: {lat, lon},
            nearby_safe_nodes: [...],
            nearby_hospital_count: int,
            alternative_routes: [...] | null,
            total_available_capacity_nearby: int,
          },
          ...
        ],
        summary: {
          total_zones_at_risk: int,
          zones_with_hospitals_nearby: int,
          zones_with_no_hospitals_nearby: int,
          total_available_capacity_nearby: int,
        }
      }
    """
    graph = build_graph(edges)
    if nodes:
        for n in nodes:
            if n["id"] in graph.nodes:
                graph.nodes[n["id"]].update({k: v for k, v in n.items() if k != "id"})
            else:
                graph.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})

    scored_map = {loc["location_id"]: loc for loc in scored_locations}
    safe_node_ids = [n["id"] for n in (nodes or []) if n.get("type") == "safe"]
    blockers = [lid for lid, loc in scored_map.items() if loc.get("risk_level") in HIGH_SEVERE]

    zones_out: list[dict[str, Any]] = []
    total_available_capacity = 0
    zones_with_hospitals = 0
    zones_without_hospitals = 0

    for zone_id, loc in scored_map.items():
        if graph.nodes.get(zone_id, {}).get("type") == "safe":
            continue
        if zone_id not in graph.nodes:
            continue

        nearby = _nearby_safe_nodes(zone_id, graph, radius_km=hospital_radius_km)
        hospital_count = sum(1 for n in nearby if n.get("subtype") == "hospital")
        available_cap = sum(n["capacity_available"] for n in nearby)
        total_available_capacity += available_cap
        if hospital_count > 0:
            zones_with_hospitals += 1
        else:
            zones_without_hospitals += 1

        alt_routes = None
        if zone_id in blockers:
            removed = [
                (u, v)
                for u, v, d in graph.edges(data=True)
                if d.get("passes_through_zone_id") == zone_id
            ]
            alt_routes = _alternative_routes(graph, zone_id, safe_node_ids, removed)

        zones_out.append({
            "zone_id": zone_id,
            "zone_name": loc.get("name", zone_id),
            "district": loc.get("district", "unknown"),
            "risk_level": loc.get("risk_level", "unknown"),
            "coordinates": loc.get("coordinates", {}),
            "nearby_safe_nodes": nearby,
            "nearby_hospital_count": hospital_count,
            "alternative_routes": alt_routes,
            "total_available_capacity_nearby": available_cap,
        })

    total_zones_at_risk = sum(1 for z in zones_out if z["risk_level"] in HIGH_SEVERE)

    return {
        "zones": zones_out,
        "summary": {
            "total_zones": len(zones_out),
            "total_zones_at_risk": total_zones_at_risk,
            "zones_with_hospitals_nearby": zones_with_hospitals,
            "zones_with_no_hospitals_nearby": zones_without_hospitals,
            "total_available_capacity_nearby": total_available_capacity,
            "search_radius_km": hospital_radius_km,
        },
    }


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
