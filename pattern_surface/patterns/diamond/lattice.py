"""Diamond-specific lattice generation."""

import math



def translated_carrier(triangle, axis, offset):
    clone = dict(triangle)
    clone["v"] = []
    for vertex in triangle["v"]:
        item = dict(vertex)
        item["q"] = list(vertex["q"])
        item["q"][axis] += offset
        clone["v"].append(item)
    clone["periodic_copy"] = True
    return clone

def periodic_carriers(payload, carriers, periodic_records):
    result = list(carriers)
    for record in periodic_records:
        members = [triangle for triangle in carriers
                   if triangle.get("component", 0) == record["component"]]
        for offset in (-record["period"], record["period"]):
            result.extend(translated_carrier(triangle, record["axis"], offset)
                          for triangle in members)
    return result

def canonical_periodic_representative(payload, canonical, periodic_records):
    center = [sum(point[0] for point in canonical) / 3.0,
              sum(point[1] for point in canonical) / 3.0]
    for record in periodic_records:
        value = center[record["axis"]]
        if value < record["lower"] - 2.0e-4 or value >= record["upper"] - 2.0e-4:
            return False
    return True


def canonical_triangles(bounds, extra=True, diamond_height=12.0,
                        diamond_side=None, origin_x=0.0):
    """Yield one edge-connected equilateral triangle lattice.

    Consecutive rows are offset by half a side.  The previous implementation
    built an up/down pair inside every rectangular column; adjacent columns
    then met only at a vertex instead of sharing their sloping edge.
    """
    x0, x1, y0, y1 = bounds
    grid_height = float(diamond_height)
    grid_side = float(diamond_side if diamond_side is not None
                      else 2.0 * grid_height / math.sqrt(3.0))
    origin_x = float(origin_x)
    margin_x = grid_side if extra else 0.0
    margin_y = grid_height if extra else 0.0
    # The requested margin is exactly one canonical row/column.  A single
    # guard column covers the half-side offset without producing a second
    # ring of cells around curved boundaries.
    col0 = int(math.floor((x0 - margin_x - origin_x) / grid_side)) - 1
    col1 = int(math.ceil((x1 + margin_x - origin_x) / grid_side)) + 1
    row0 = int(math.floor((y0 - margin_y) / grid_height))
    row1 = int(math.ceil((y1 + margin_y) / grid_height))

    def point(row, col):
        shift = grid_side * 0.5 if row % 2 else 0.0
        return [origin_x + col * grid_side + shift, row * grid_height]

    for row in range(row0, row1):
        for col in range(col0, col1):
            lower_left = point(row, col)
            lower_right = point(row, col + 1)
            upper_left = point(row + 1, col)
            upper_right = point(row + 1, col + 1)
            if row % 2:
                up = [lower_left, lower_right, upper_right]
                down = [lower_left, upper_right, upper_left]
            else:
                up = [lower_left, lower_right, upper_left]
                down = [lower_right, upper_right, upper_left]
            yield "r{}_c{}_up".format(row, col), up
            yield "r{}_c{}_down".format(row, col), down
