"""Convert cleaned manufacturing records into scheduling parameters."""

SMALL_SETUP_MINUTES = 30.0
LARGE_SETUP_MINUTES = 75.0
SETUP_ATTRIBUTES = ("head_type", "diameter_mm", "length_mm")


def setup_time(source: dict, target: dict) -> tuple[float, list[str]]:
    """Return illustrative C_S and the product attributes that changed."""
    changed = [name for name in SETUP_ATTRIBUTES if source[name] != target[name]]
    if not changed:
        return 0.0, changed
    if len(changed) == 1:
        return SMALL_SETUP_MINUTES, changed
    return LARGE_SETUP_MINUTES, changed


def build_setup_parameters(products: list[dict]) -> tuple[list[dict], dict[str, float]]:
    """Build pairwise C_S rows and a batch-weighted C_S for each target product."""
    pairwise_rows = []
    weighted_setup = {}

    for target in products:
        same_process = [p for p in products if p["process"] == target["process"]]
        total_weight = sum(p["batch_weight"] for p in same_process)
        weighted_minutes = 0.0

        for source in same_process:
            minutes, changed = setup_time(source, target)
            weighted_minutes += source["batch_weight"] * minutes
            pairwise_rows.append(
                {
                    "process": target["process"],
                    "from_product_id": source["product_id"],
                    "to_product_id": target["product_id"],
                    "changed_attributes": "|".join(changed) or "none",
                    "C_S_minutes": f"{minutes:.2f}",
                }
            )

        weighted_setup[target["product_id"]] = round(weighted_minutes / total_weight, 4)

    return pairwise_rows, weighted_setup


def build_processed_parameters(
    machines: list[dict],
    products: list[dict],
    compatibility: dict,
    rates: dict,
    weighted_setup: dict[str, float],
) -> list[dict]:
    """Return C_P and C_S rows for compatible active machine-product pairs."""
    rows = []
    for machine in machines:
        machine_id = machine["machine_id"]
        if machine_id not in compatibility:
            continue

        rate_record = rates.get(machine_id)
        rate = rate_record["machine_rate_units_per_minute"] if rate_record else None
        status = "ok" if rate else "missing_machine_rate"

        for product in products:
            product_id = product["product_id"]
            if not compatibility[machine_id][product_id]:
                continue
            rows.append(
                {
                    "machine_id": machine_id,
                    "product_id": product_id,
                    "process": product["process"],
                    "compatible": 1,
                    "machine_rate_units_per_minute": f"{rate:.4f}" if rate else "",
                    "C_P_minutes_per_unit": f"{1 / rate:.4f}" if rate else "",
                    "weighted_C_S_minutes": f"{weighted_setup[product_id]:.4f}",
                    "rate_as_of_date": rate_record["as_of_date"] if rate_record else "",
                    "rate_version": rate_record["source_version"] if rate_record else "",
                    "data_quality_status": status,
                }
            )
    return rows
