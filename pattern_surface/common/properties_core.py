"""FreeCAD property helpers with no mapping or pattern dependencies."""

import FreeCAD as App


def add_string(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", name, group)
    setattr(obj, name, str(value))


def add_bool(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyBool", name, group)
    setattr(obj, name, bool(value))


def add_integer(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyInteger", name, group)
    setattr(obj, name, int(value))


def add_float(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyFloat", name, group)
    setattr(obj, name, float(value))


def add_string_list(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyStringList", name, group)
    setattr(obj, name, [str(item) for item in value])


def add_vector(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyVector", name, group)
    setattr(obj, name, App.Vector(float(value[0]), float(value[1]), 0.0))


def add_length(obj, name, value, group):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyLength", name, group)
    setattr(obj, name, float(value))


def length_value(value, default=1.0):
    try:
        return float(value.Value)
    except AttributeError:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)


def next_name(doc, prefix):
    index = 1
    while doc.getObject("{}_Run_{:03d}".format(prefix, index)) is not None:
        index += 1
    return "{}_Run_{:03d}".format(prefix, index)
