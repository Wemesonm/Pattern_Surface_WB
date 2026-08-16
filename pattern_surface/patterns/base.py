REQUIRED_FIELDS = ("pattern_id", "label", "command_id", "icon")


def validate_descriptor(descriptor):
    missing = [field for field in REQUIRED_FIELDS if not descriptor.get(field)]
    if missing:
        raise ValueError("Pattern descriptor missing: {}".format(", ".join(missing)))
    return descriptor
