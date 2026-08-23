from ...common.runtime import maybe_reload


def run():
    from . import parameters, solids

    maybe_reload(parameters)
    values = parameters.get_parameters()
    if values is None:
        return None
    maybe_reload(solids)
    return solids.create_pattern(values)
