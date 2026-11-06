"""Visual-DAG model for a project plan (B3-04.02). The engine decides validity; this only explains and lays out.

`valid` is exactly "planner._dag accepted the spec". When it rejects, the plan is still drawn (as far as it can be read)
with structured findings that point at the offending nodes/edges, and the engine's own message is always included, so the
picture can neither approve what the engine refused nor stay silent about why. No worker, command or file is touched.
"""
from __future__ import annotations

from . import planner

MAX_NODES = 96  # engine limit: 12 phases x 8 workstreams


def _norm(path):
    text = str(path).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def _read(spec):
    """Tolerant read of nodes and edges from a possibly invalid spec."""
    nodes, edges, findings, seen = {}, [], [], {}
    phases = spec.get("phases") if isinstance(spec, dict) else None
    phases = [p for p in phases if isinstance(p, dict)] if isinstance(phases, list) else []
    lanes_of = {}
    for phase in phases:
        name = phase.get("name")
        if not isinstance(name, str):
            continue
        lanes = [w for w in (phase.get("workstreams") or []) if isinstance(w, dict) and isinstance(w.get("name"), str)] \
            if isinstance(phase.get("workstreams"), list) else []
        lanes_of.setdefault(name, []).extend(lanes)
        for lane in lanes:
            node_id = f"{name}/{lane['name']}"
            if node_id in seen:
                findings.append({"kind": "duplicate_name", "nodes": [node_id], "edges": [], "message": f"{node_id} is defined twice."})
                continue
            seen[node_id] = True
            request = lane.get("request") if isinstance(lane.get("request"), dict) else {}
            own = request.get("ownership")
            forb = request.get("forbidden")
            nodes[node_id] = {
                "id": node_id, "phase": name, "name": lane["name"],
                "ownership": sorted({_norm(x) for x in own if isinstance(x, str)}) if isinstance(own, list) else [],
                "forbidden": sorted({_norm(x) for x in forb if isinstance(x, str)}) if isinstance(forb, list) else [],
                "budget": {"timeout_seconds": request.get("timeout_seconds"),
                           "max_weighted_tokens": (request.get("workflow") or {}).get("max_weighted_tokens")
                           if isinstance(request.get("workflow"), dict) else None},
                "issues": [],
            }
    for phase in phases:
        name = phase.get("name")
        if not isinstance(name, str):
            continue
        after = phase.get("after") if isinstance(phase.get("after"), list) else []
        for lane in lanes_of.get(name, []):
            target = f"{name}/{lane['name']}"
            if target not in nodes:
                continue
            for dep in after:
                if not isinstance(dep, str):
                    continue
                if dep not in lanes_of:
                    findings.append({"kind": "unknown_dependency", "nodes": [target], "edges": [[f"{dep}/?", target]],
                                     "message": f"{target} waits for unknown phase '{dep}'."})
                    continue
                for other in lanes_of[dep]:
                    source = f"{dep}/{other['name']}"
                    if source in nodes:
                        edges.append([source, target])
            lane_after = lane.get("after") if isinstance(lane.get("after"), list) else []
            for dep in lane_after:
                if not isinstance(dep, str):
                    continue
                source = f"{name}/{dep}"
                if source in nodes:
                    edges.append([source, target])
                else:
                    findings.append({"kind": "unknown_dependency", "nodes": [target], "edges": [[source, target]],
                                     "message": f"{target} waits for unknown workstream '{dep}'."})
    return nodes, sorted({tuple(e) for e in edges}), findings


def _cycles(nodes, edges):
    graph = {n: [] for n in nodes}
    for source, target in edges:
        graph[target].append(source)  # target depends on source
    state, stack, found = {}, [], []

    def visit(node):
        mark = state.get(node, 0)
        if mark == 1:
            found.append(stack[stack.index(node):] + [node])
            return
        if mark == 2:
            return
        state[node] = 1
        stack.append(node)
        for dep in sorted(graph[node]):
            visit(dep)
        stack.pop()
        state[node] = 2

    for node in sorted(graph):
        visit(node)
    return found


def _ancestors(nodes, edges):
    deps = {n: set() for n in nodes}
    for source, target in edges:
        deps[target].add(source)
    result = {}
    for node in nodes:
        seen, todo = set(), list(deps[node])
        while todo:
            current = todo.pop()
            if current not in seen:
                seen.add(current)
                todo.extend(deps[current])
        result[node] = seen
    return result


def _layers(nodes, edges):
    """Longest-path depth; nodes inside a cycle fall back to depth 0 so the picture still renders."""
    deps = {n: [] for n in nodes}
    for source, target in edges:
        deps[target].append(source)
    depth = {}

    def of(node, trail=()):
        if node in depth:
            return depth[node]
        if node in trail:
            return 0
        depth[node] = 1 + max((of(d, trail + (node,)) for d in deps[node]), default=-1)
        return depth[node]
    return {n: of(n) for n in sorted(nodes)}


def dag_view(spec, project_root):
    verdict, message, engine_dag = False, None, None
    try:
        engine_dag = planner._dag(spec, project_root)
        verdict = bool(engine_dag.get("valid"))
    except (TypeError, ValueError, AttributeError, KeyError) as error:
        message = str(error)
    nodes, edges, findings = _read(spec)
    if len(nodes) > MAX_NODES:
        findings.append({"kind": "too_large", "nodes": [], "edges": [], "message": f"More than {MAX_NODES} workstreams."})
    for cycle in _cycles(nodes, edges):
        findings.append({"kind": "cycle", "nodes": sorted(set(cycle)), "edges": [[cycle[i + 1], cycle[i]] for i in range(len(cycle) - 1)],
                         "message": "Cycle: " + " -> ".join(reversed(cycle))})
    ancestry = _ancestors(nodes, edges)
    ids = sorted(nodes)
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            if left in ancestry[right] or right in ancestry[left]:
                continue
            shared = sorted({a if len(a) <= len(b) else b for a in nodes[left]["ownership"] for b in nodes[right]["ownership"]
                             if planner._inside(a, b)})
            if shared:
                findings.append({"kind": "ownership_collision", "nodes": [left, right], "edges": [],
                                 "message": f"{left} and {right} run in parallel but both own {', '.join(shared)}."})
    if not verdict and message and not findings:
        findings.append({"kind": "engine", "nodes": [], "edges": [], "message": message})  # the engine said no; never silent
    layer = _layers(nodes, edges)
    rows = {}
    out_nodes = []
    for node_id in sorted(nodes, key=lambda n: (layer[n], n)):
        row = rows.get(layer[node_id], 0)
        rows[layer[node_id]] = row + 1
        issues = [f["kind"] for f in findings if node_id in f["nodes"]]
        out_nodes.append({**nodes[node_id], "layer": layer[node_id], "row": row, "issues": sorted(set(issues))})
    flagged = {tuple(e) for f in findings for e in f["edges"]}
    out_edges = [{"from": s, "to": t, "issue": (s, t) in flagged} for s, t in edges]
    return {"valid": verdict, "engine_message": message, "nodes": out_nodes, "edges": out_edges, "findings": findings,
            "counts": {"nodes": len(out_nodes), "edges": len(out_edges)},
            "authority": {"workers": False, "start": "explicit human action only"}}
