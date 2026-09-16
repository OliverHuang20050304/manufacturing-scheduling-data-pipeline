"""Build a binary machine-product compatibility matrix."""


def is_compatible(machine: dict, product: dict) -> bool:
    """Return whether a product fits one active machine's constraints."""
    if not machine["active"] or machine["process"] != product["process"]:
        return False

    dimensions_fit = (
        machine["diameter_min_mm"] <= product["diameter_mm"] <= machine["diameter_max_mm"]
        and machine["length_min_mm"] <= product["length_mm"] <= machine["length_max_mm"]
    )
    if not dimensions_fit:
        return False

    return (
        machine["process"] != "heading"
        or product["head_type"] in machine["supported_head_types"]
    )


def build_compatibility_matrix(machines: list[dict], products: list[dict]) -> dict:
    """Return {machine_id: {product_id: 0 or 1}} for active machines."""
    return {
        machine["machine_id"]: {
            product["product_id"]: int(is_compatible(machine, product))
            for product in products
        }
        for machine in machines
        if machine["active"]
    }
