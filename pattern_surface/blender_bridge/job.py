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


def create_job(map_object, parameters, root=None, pattern_object=None,
               geometry_module=None, pattern_label="Diamond", boundary_solver="EXACT",
               include_boundary_curves=False):
    """Export the source body and map data into a transient Blender job."""

    map_object = resolve_map(map_object)
    if map_object is None:
        raise ValueError("Select a Mapped Surface or Mapping Grid first.")
    document = map_object.Document
    payload = _payload(map_object)
    from .reference import prepare_reference
    payload = prepare_reference(document, payload, include_boundary_curves=include_boundary_curves)
    records = payload.get("faces", [])
    objects = []
    seen = set()
    for record in records:
        object_name = record.get("object")
        source = document.getObject(object_name) if object_name else None
        if source is None:
            raise ValueError("Map source object is missing: {}. Recreate Map Faces from the current document.".format(object_name))
        if source is not None:
            source = _solid_owner(source)
            if source.Name not in seen:
                seen.add(source.Name)
                objects.append(source)
    if not objects:
        raise ValueError("The map does not reference a source CAD body.")

    root = job_root(root)
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="auzyron-", dir=str(root)))
    body_path = directory / "source_body.stl"
    body_topology = _export_clean_shape(document, objects, body_path)
    job = {
        "format": JOB_SCHEMA,
        "version": JOB_VERSION,
        "units": "mm",
        "source": {"document": document.Name, "map_object": map_object.Name,
                   "map_label": getattr(map_object, "Label", map_object.Name)},
        "map_payload": payload,
        "body_mesh": str(body_path),
        "body_topology": body_topology,
        "parameters": dict(parameters),
        "geometry_module": str(geometry_module or Path(__file__).with_name("geometry_closed.py")),
        "pattern_label": str(pattern_label),
        "boundary_solver": str(boundary_solver),
        "output_dir": str(directory),
    }
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
