"""FreeCAD-side job packaging and Blender process orchestration."""

import json
import os
import shutil
import subprocess
import tempfile
import zlib
import base64
from pathlib import Path

from ..common.ownership import map_from_selection_object


JOB_SCHEMA = "auzyron.blender-job"
JOB_VERSION = 1


def job_root(root=None):
    return Path(root or (Path.home() / ".local" / "share" / "codex-cad" / "blender-jobs"))


def cleanup_jobs(root=None, keep=None):
    """Remove only bridge-owned transient packages, never user Blender files."""
    root = job_root(root)
    if not root.exists():
        return 0
    keep = Path(keep).resolve() if keep else None
    removed = 0
    for directory in root.glob("auzyron-*"):
        if not directory.is_dir() or (keep is not None and directory.resolve() == keep):
            continue
        shutil.rmtree(directory)
        removed += 1
    return removed


def _decode_chunks(obj, name):
    chunks = list(getattr(obj, name, []) or [])
    if not chunks:
        raise ValueError("Selected map does not contain {}.".format(name))
    return json.loads(zlib.decompress(base64.b64decode("".join(chunks))).decode("utf-8"))


def resolve_map(selected):
    return map_from_selection_object(selected)


def _payload(map_object):
    properties = getattr(map_object, "PropertiesList", [])
    for name in ("MapPayloadChunks", "WrapCarrierChunks"):
        if name in properties:
            return _decode_chunks(map_object, name)
    raise ValueError("Selected object is not a supported mapped surface.")


def _solid_owner(source):
    """Export the mapped solid, not a group containing its construction history."""
    # A selected PartDesign feature is a face provider, while its Body is the
    # finished CAD object the user sees. Prefer that Body even when the feature
    # itself exposes a solid Shape; otherwise a final fillet or pocket can be
    # exported as a fragment instead of the complete product.
    # App::Part remains deliberately excluded because it is an assembly and may
    # contain unrelated or overlapping construction history.
    for method_name in ("getParentGeoFeatureGroup", "getParentGroup"):
        method = getattr(source, method_name, None)
        if method is None:
            continue
        try:
            parent = method()
        except Exception:
            continue
        if parent is not None and getattr(parent, "TypeId", "") == "PartDesign::Body":
            shape = getattr(parent, "Shape", None)
            if shape is not None and not shape.isNull() and shape.Solids:
                return parent
    shape = getattr(source, "Shape", None)
    if shape is not None and not shape.isNull() and shape.Solids:
        return source
    return source


def _export_clean_shape(document, sources, path):
    """Export one cleaned shape so Blender receives a single CAD solid.

    Mesh.export(objects) can preserve seams between PartDesign features.  The
    bridge must not export those feature boundaries as disconnected STL
    shells, so make a temporary, non-document feature and remove it again.
    """
    import Mesh

    import Part

    shapes = []
    for source in sources:
        shape = getattr(source, "Shape", None)
        if shape is None or shape.isNull():
            tip = getattr(source, "Tip", None)
            shape = getattr(tip, "Shape", None)
        if shape is not None and not shape.isNull():
            try:
                shape = shape.removeSplitter()
            except Exception:
                shape = shape.copy()
            shapes.append(shape)
    if not shapes:
        raise ValueError("The map source has no exportable solid shape.")

    # Overlapping source solids must be united in CAD before tessellation.
    # A compound retains internal coincident walls and nonmanifold STL edges.
    shape = shapes[0] if len(shapes) == 1 else shapes[0].multiFuse(shapes[1:]).removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise ValueError("Mapped source solids do not form one valid connected CAD body.")
    temporary = document.addObject("Part::Feature", "_AuzyronBlenderExport")
    temporary.Shape = shape
    document.recompute()
    try:
        Mesh.export([temporary], str(path))
        return {"valid": True, "solids": len(shape.Solids),
                "shells": len(shape.Shells), "volume_mm3": float(shape.Volume)}
    finally:
        document.removeObject(temporary.Name)
        document.recompute()


def _export_pattern_mesh(document, pattern, path):
    """Tessellate the actual FreeCAD pattern without altering its geometry.

    Pattern results are often compounds of separately generated pyramids, so
    they must not be fused, refined, or otherwise rebuilt for Blender.  Those
    operations change clipped boundary cells and create the saw-tooth edges the
    bridge is meant to avoid.
    """
    import Mesh

    shape = getattr(pattern, "Shape", None)
    if shape is None or shape.isNull():
        raise ValueError("The selected Diamond Pattern has no exportable shape.")
    temporary = document.addObject("Part::Feature", "_AuzyronBlenderPatternExport")
    temporary.Shape = shape.copy()
    document.recompute()
    try:
        Mesh.export([temporary], str(path))
    finally:
        document.removeObject(temporary.Name)
        document.recompute()


def _blender_binary():
    return (shutil.which("blender") or
            "/Applications/Blender.app/Contents/MacOS/Blender")


def worker_path():
    return Path(__file__).with_name("worker.py")


def _map_objects(selection):
    """Resolve a selection into unique Map Faces runs in selection order."""
    objects = selection if isinstance(selection, (list, tuple)) else [selection]
    result = []
    seen = set()
    for selected in objects:
        mapped = resolve_map(selected)
        if mapped is None:
            raise ValueError("Select only Mapped Surfaces or Mapping Grids.")
        key = getattr(mapped, "Name", id(mapped))
        if key not in seen:
            seen.add(key)
            result.append(mapped)
    if not result:
        raise ValueError("Select a Mapped Surface or Mapping Grid first.")
    return result


def _copy_payload_for_body(document, payload, owner_name):
    """Return one transient map payload containing one source Body only.

    Map Faces deliberately permits an arbitrary multi-Body selection. Blender
    must still preserve motion between Bodies, so this bridge-only split keeps
    their carriers and CAD exports separate without editing the saved map.
    """
    import copy

    records = list(payload.get("faces", []) or [])
    selected = []
    for position, record in enumerate(records):
        source = document.getObject(record.get("object", ""))
        if source is not None and _solid_owner(source).Name == owner_name:
            # Carrier records address the public face index, which need not
            # equal the position in a legacy payload's face list.
            selected.append((int(record.get("index", position)), record))
    if not selected:
        return None
    remap = {old: new for new, (old, _record) in enumerate(selected)}
    result = copy.deepcopy(payload)
    old_components = list(payload.get("components", []) or [])
    component_remap = {}
    components = []
    for old_component, component in enumerate(old_components):
        members = [remap[index] for index in component if index in remap]
        if members:
            component_remap[old_component] = len(components)
            components.append(members)
    if not components:
        components = [list(range(len(selected)))]
        component_remap = {0: 0}
    result["components"] = components
    result["faces"] = []
    for new_index, (_old_index, record) in enumerate(selected):
        clone = copy.deepcopy(record)
        clone["index"] = new_index
        # The bridge creates an independent carrier for each movable Body.
        # Its face records must use the same local component numbering as its
        # carrier triangles. Otherwise native boundary curves rebuilt from
        # these records are indexed under the original packed-map component
        # and cannot attenuate the matching relief samples.
        clone["component"] = component_remap.get(int(clone.get("component", 0)), 0)
        result["faces"].append(clone)

    def belongs(record):
        return int(record.get("face", -1)) in remap

    def remapped(records_to_copy):
        copied = []
        for record in records_to_copy or []:
            if not belongs(record):
                continue
            clone = copy.deepcopy(record)
            clone["face"] = remap[int(record["face"])]
            old_component = int(clone.get("component", 0))
            clone["component"] = component_remap.get(old_component, 0)
            copied.append(clone)
        return copied

    carrier = remapped(payload.get("carrier_triangles", payload.get("triangles", [])))
    result["carrier_triangles"] = carrier
    result["triangles"] = carrier
    result["external_segments"] = remapped(payload.get("external_segments", []))
    result["adjacency"] = [[remap[left], remap[right]]
                           for left, right in payload.get("adjacency", []) or []
                           if left in remap and right in remap]
    result["periodic_seams"] = [[remap[left], remap[right]]
                                for left, right in payload.get("periodic_seams", []) or []
                                if left in remap and right in remap]
    result["periodic_adjustments"] = []
    for record in payload.get("periodic_adjustments", []) or []:
        if int(record.get("component", 0)) not in component_remap:
            continue
        pairs = record.get("pairs") or ([record["pair"]] if record.get("pair") else [])
        retained = [[remap[a], remap[b]] for a, b in pairs if a in remap and b in remap]
        if pairs and not retained:
            continue
        clone = copy.deepcopy(record)
        clone["component"] = component_remap[int(record.get("component", 0))]
        if pairs:
            clone["pairs"] = retained
            clone["pair"] = retained[0]
        result["periodic_adjustments"].append(clone)
    qs = [vertex["q"] for triangle in carrier for vertex in triangle.get("v", [])]
    if qs:
        result["bounds"] = [min(q[0] for q in qs), max(q[0] for q in qs),
                            min(q[1] for q in qs), max(q[1] for q in qs)]
    return result

def _payloads_by_source_body(document, payload):
    """Partition a map only when it really spans separate movable Bodies."""
    owners = []
    for record in payload.get("faces", []) or []:
        source = document.getObject(record.get("object", ""))
        if source is None:
            raise ValueError("Map source object is missing: {}. Recreate Map Faces from the current document.".format(
                record.get("object", "")))
        owner = _solid_owner(source)
        if owner.Name not in owners:
            owners.append(owner.Name)
    if len(owners) <= 1:
        return [(owners[0] if owners else None, payload)]
    return [(owner, _copy_payload_for_body(document, payload, owner))
            for owner in owners]


def _attach_shared_map_phase(payloads):
    """Attach the pattern-neutral assembly phase to transient map payloads.

    Registration already puts all compatible maps in one logical coordinate
    system.  This record makes the reference origin and any complete assembly
    loop available to every Blender pattern without selecting a lattice size.
    """
    if not payloads:
        return {}
    grid = payloads[0].get("grid", {}) or {}
    phase = {"origin": [float(value) for value in grid.get("origin", [0.0, 0.0])[:2]]}
    from .shared_phase import assembly_cycle_period
    period = assembly_cycle_period(payloads)
    if period is None:
        # A joint atlas can retain its closure seam inside one partition.
        # Its native period still governs all registered portions of that atlas.
        periods = [float(r["period"]) for p in payloads
                   for r in p.get("periodic_adjustments", []) if "period" in r]
        if periods and max(periods) - min(periods) < 1e-6:
            period = periods[0]
    if period is not None:
        phase["assembly_period"] = float(period)
    for payload in payloads:
        payload["shared_map_phase"] = dict(phase)
    return phase


def _apply_shared_diamond_phase(payloads, parameters):
    """Attach one transient Diamond lattice to every shared job payload.

    The Map Faces grid remains untouched and map-local. Only the Blender job
    receives the reference pattern dimensions, preventing each periodic
    component from independently changing the requested Diamond side.
    """
    if not payloads:
        return
    from .geometry_closed import dimensions
    reference = dimensions(payloads[0], parameters)
    phase = {"side": float(reference["side"]),
             "row_height": float(reference["row_height"]),
             "origin": [float(value) for value in reference["origin"][:2]],
             "modules": reference.get("modules")}
    common = payloads[0].get("shared_map_phase", {}) or {}
    if not common:
        common = _attach_shared_map_phase(payloads)
    period = common.get("assembly_period")
    if period is not None:
        import math
        requested = float(parameters.get('diamond_side') or
                          2.0 * float(parameters.get('diamond_height', 12.32)) / math.sqrt(3.0))
        modules = max(1, round(period / requested))
        side = period / modules
        if abs(side - requested) > float(parameters.get('closure_fit_tolerance', 0.2)) + 1.0e-8:
            raise ValueError('Assembly Diamond closure exceeds the configured tolerance.')
        phase.update(side=side, modules=None, assembly_period=period,
                     assembly_modules=modules)
    for index, payload in enumerate(payloads):
        payload["shared_pattern_phase"] = dict(phase, reference=(index == 0))


def _sources_for_map(document, payload):
    records = payload.get("faces", [])
    objects = []
    seen = set()
    for record in records:
        object_name = record.get("object")
        source = document.getObject(object_name) if object_name else None
        if source is None:
            raise ValueError("Map source object is missing: {}. Recreate Map Faces from the current document.".format(object_name))
        source = _solid_owner(source)
        if source.Name not in seen:
            seen.add(source.Name)
            objects.append(source)
    if not objects:
        raise ValueError("The map does not reference a source CAD body.")
    return objects


def create_job(map_object, parameters, root=None, pattern_object=None,
               geometry_module=None, pattern_label="Diamond", boundary_solver="EXACT",
               include_boundary_curves=False):
    """Export the source body and map data into a transient Blender job."""

    map_objects = _map_objects(map_object)
    document = map_objects[0].Document
    if any(item.Document is not document for item in map_objects):
        raise ValueError("All selected maps must belong to the active FreeCAD document.")
    from .reference import prepare_reference
    # A single Map Faces run can contain faces of several movable Bodies.
    # Split that saved contract only in this transient job before refreshing
    # curved carriers, so every result remains physically independent.
    payloads = []
    payload_sources = []
    for item in map_objects:
        partitions = _payloads_by_source_body(document, _payload(item))
        for owner_name, payload in partitions:
            payloads.append(prepare_reference(
                document, payload, include_boundary_curves=include_boundary_curves,
                rebuild_boundary=len(partitions) > 1))
            payload_sources.append((item, owner_name))

    root = job_root(root)
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="auzyron-", dir=str(root)))
    maps = []
    for (mapped, owner_name), payload in zip(payload_sources, payloads):
        sources = _sources_for_map(document, payload)
        label = getattr(mapped, "Label", mapped.Name)
        if owner_name is not None and len(payload_sources) > len(map_objects):
            label = "{} — {}".format(label, owner_name)
        maps.append({
            "map_object": mapped.Name,
            "map_label": label,
            "map_payload": payload,
            "sources": sources,
        })
    phase_records = []
    if len(maps) > 1:
        from .shared_phase import align
        aligned, phase_records = align([item["map_payload"] for item in maps])
        shared_map_phase = _attach_shared_map_phase(aligned)
        if str(pattern_label).strip().lower() == "diamond":
            _apply_shared_diamond_phase(aligned, parameters)
        for mapped, payload in zip(maps, aligned):
            mapped["map_payload"] = payload
    # Several maps can refer to separate exterior regions of one Body. Export
    # that Body once; only a different source-body set creates another Blender
    # CAD object.  Pattern patches remain independently clipped to their maps.
    components_by_sources = {}
    for mapped in maps:
        key = tuple(source.Name for source in mapped["sources"])
        components_by_sources.setdefault(key, []).append(mapped)
    components = []
    for index, (key, component_maps) in enumerate(components_by_sources.items(), 1):
        sources = component_maps[0]["sources"]
        body_path = directory / "source_body_{:03d}.stl".format(index)
        components.append({
            "body_label": getattr(sources[0], "Label", sources[0].Name),
            "body_mesh": str(body_path),
            "body_topology": _export_clean_shape(document, sources, body_path),
            "source_bodies": list(key),
            "maps": [{key: value for key, value in mapped.items() if key != "sources"}
                     for mapped in component_maps],
        })
    first_map = maps[0]
    first_component = components[0]
    job = {
        "format": JOB_SCHEMA,
        "version": JOB_VERSION,
        "units": "mm",
        "source": {"document": document.Name, "map_object": first_map["map_object"],
                   "map_label": first_map["map_label"]},
        "map_payload": first_map["map_payload"],
        "body_mesh": first_component["body_mesh"],
        "body_topology": first_component["body_topology"],
        "parameters": dict(parameters),
        "geometry_module": str(geometry_module or Path(__file__).with_name("geometry_closed.py")),
        "pattern_label": str(pattern_label),
        "boundary_solver": str(boundary_solver),
        "output_dir": str(directory),
    }
    if len(maps) > 1:
        job["components"] = components
        job["shared_phase"] = {"reference_map": first_map["map_object"],
                               "alignments": phase_records,
                               "map_phase": shared_map_phase}
    # An optional final pattern is supported for future export-only workflows,
    # but Blender Diamond intentionally generates its relief from the map.
    if pattern_object is not None:
        pattern_path = directory / "diamond_pattern.stl"
        _export_pattern_mesh(document, pattern_object, pattern_path)
        job["pattern_mesh"] = str(pattern_path)
        job["pattern_source"] = {"object": pattern_object.Name,
                                 "label": getattr(pattern_object, "Label", pattern_object.Name)}
    job_path = directory / "job.json"
    job_path.write_text(json.dumps(job, indent=2, sort_keys=True), encoding="utf-8")
    return job_path


def run_job(job_path, timeout=900):
    blender = _blender_binary()
    if not os.path.isfile(blender) or not os.access(blender, os.X_OK):
        raise RuntimeError("Blender executable was not found: {}".format(blender))
    worker = worker_path()
    completed = subprocess.run([blender, "--background", "--python", str(worker), "--",
                                str(job_path)], capture_output=True, text=True,
                               timeout=timeout)
    if completed.returncode != 0:
        raise RuntimeError("Blender failed ({}):\n{}".format(
            completed.returncode, (completed.stderr or completed.stdout)[-4000:]))
    report_path = Path(job_path).with_name("validation.json")
    if not report_path.exists():
        raise RuntimeError("Blender finished without a validation report.")
    return json.loads(report_path.read_text(encoding="utf-8"))
