"""Safe document-tree ownership for map and pattern helper objects.

PartDesign::Body accepts only PartDesign features. Adding a map helper to a
Body makes it the Body Tip, which replaces the finished CAD shape. The
workbench therefore keeps helpers in a neutral group beside their source Body,
inside the nearest App::Part when one exists.
"""


def _add_link(obj, name, value, group="Pattern Surface"):
    if name not in getattr(obj, "PropertiesList", []):
        obj.addProperty("App::PropertyLink", name, group)
    setattr(obj, name, value)


def _add_link_list(obj, name, values, group="Pattern Surface"):
    if name not in getattr(obj, "PropertiesList", []):
        obj.addProperty("App::PropertyLinkList", name, group)
    setattr(obj, name, list(values))


def _add_string(obj, name, value, group="Pattern Surface"):
    if name not in getattr(obj, "PropertiesList", []):
        obj.addProperty("App::PropertyString", name, group)
    setattr(obj, name, str(value))


def _parent_geo(obj):
    method = getattr(obj, "getParentGeoFeatureGroup", None)
    if method is None:
        return None
    try:
        return method()
    except Exception:
        return None


def source_body(source):
    """Return the PartDesign Body containing a selected source feature."""
    current = source
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if getattr(current, "TypeId", "") == "PartDesign::Body":
            return current
        current = _parent_geo(current)
    return None


def _part_container(body):
    """Return the closest App::Part without treating a Body as a group."""
    current = body
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        current = _parent_geo(current)
        if getattr(current, "TypeId", "") == "App::Part":
            return current
    return None


def _next_group_name(document):
    base = "PatternSurfaceObjects"
    index = 1
    name = base
    while document.getObject(name) is not None:
        index += 1
        name = "{}{:03d}".format(base, index)
    return name


def organize_map(document, map_object, preview_object, source_objects):
    """Group a map with source body/bodies without changing any Body Tip."""
    bodies = []
    for source in source_objects:
        body = source_body(source)
        if body is not None and body not in bodies:
            bodies.append(body)

    group = document.addObject("App::DocumentObjectGroup", _next_group_name(document))
    if len(bodies) == 1:
        group.Label = "Pattern Surface ({})".format(getattr(bodies[0], "Label", bodies[0].Name))
        container = _part_container(bodies[0])
        if container is not None:
            container.addObject(group)
    else:
        group.Label = "Pattern Surface (multiple bodies)"

    group.addObject(map_object)
    group.addObject(preview_object)
    _add_link_list(group, "SourceBodies", bodies, "Pattern Surface")
    _add_link_list(map_object, "MapSourceBodies", bodies)
    _add_link_list(preview_object, "MapSourceBodies", bodies)
    if len(bodies) == 1:
        _add_link(map_object, "MapSourceBody", bodies[0])
        _add_link(preview_object, "MapSourceBody", bodies[0])
    # A PropertyLink back to the group would create a dependency cycle because
    # the group already owns the map objects. Store its stable object name.
    _add_string(map_object, "MapOwnerGroup", group.Name)
    _add_string(preview_object, "MapOwnerGroup", group.Name)
    return group


def organize_derived_object(result, map_object):
    """Place a pattern or trim result beside the map it consumes."""
    owner = getattr(map_object, "MapOwnerGroup", "")
    group = map_object.Document.getObject(owner) if isinstance(owner, str) and owner else owner
    if group is None:
        return None
    group.addObject(result)
    _add_string(result, "PatternOwnerGroup", group.Name)
    source_bodies = list(getattr(map_object, "MapSourceBodies", []) or [])
    _add_link_list(result, "PatternSourceBodies", source_bodies)
    if len(source_bodies) == 1:
        _add_link(result, "PatternSourceBody", source_bodies[0])
    return group


def map_from_selection_object(selected):
    """Resolve a map run from itself, its preview, or its ownership group."""
    if selected is None:
        return None
    properties = getattr(selected, "PropertiesList", [])
    if "MapPayloadChunks" in properties or "WrapCarrierChunks" in properties:
        return selected
    document = getattr(selected, "Document", None)
    for name in ("MapParentRun", "WrapParentRun"):
        parent_name = getattr(selected, name, "") or ""
        if document is not None and parent_name:
            parent = document.getObject(parent_name)
            if parent is not None:
                return parent
    owner_name = getattr(selected, "MapOwnerGroup", "") or ""
    if document is not None and owner_name:
        owner = document.getObject(owner_name)
        for child in list(getattr(owner, "Group", []) or []):
            child_properties = getattr(child, "PropertiesList", [])
            if "MapPayloadChunks" in child_properties or "WrapCarrierChunks" in child_properties:
                return child
        for child in list(getattr(owner, "Group", []) or []):
            parent_name = (getattr(child, "MapParentRun", "") or
                           getattr(child, "WrapParentRun", ""))
            if parent_name:
                parent = document.getObject(parent_name)
                if parent is not None:
                    return parent
        # The selected object is a map run from an incomplete legacy object.
        return selected
    # A neutral App::DocumentObjectGroup owns the map and preview. It is a
    # convenient tree selection and must mean the same map to every tool.
    for child in list(getattr(selected, "Group", []) or []):
        resolved = map_from_selection_object(child)
        if resolved is not None:
            return resolved
    return None
