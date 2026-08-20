"""Selection primitives shared by mapping and pattern workflows."""

import FreeCADGui as Gui


def selected_faces():
    """Collect unique selected faces without any pattern-specific knowledge."""
    entries = []
    seen = set()
    for selection in Gui.Selection.getSelectionEx():
        obj = selection.Object
        names = list(selection.SubElementNames or [])
        shapes = list(selection.SubObjects or [])
        picked = None
        try:
            picked = selection.PickedPoints[0]
        except Exception:
            pass
        for pos, shape in enumerate(shapes):
            if getattr(shape, "ShapeType", "") != "Face":
                continue
            name = names[pos] if pos < len(names) else "Face{}".format(pos + 1)
            key = (obj.Name, name)
            if key in seen:
                continue
            seen.add(key)
            entries.append({"object": obj, "sub": name, "face": shape,
                            "picked": picked})
    if not entries:
        raise RuntimeError(
            "Selecione uma ou mais faces antes de executar Map Faces.")
    entries.sort(key=lambda item: (item["object"].Name, item["sub"]))
    for index, entry in enumerate(entries):
        entry["index"] = index
    return entries
