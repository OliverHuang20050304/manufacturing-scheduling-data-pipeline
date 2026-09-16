"""Convert cleaned manufacturing records into scheduling parameters."""

SMALL_SETUP_MINUTES = 30.0
LARGE_SETUP_MINUTES = 75.0
SETUP_ATTRIBUTES = ("head_type", "diameter_mm", "length_mm")
CP_LAMBDA_BY_PROCESS = {"heading": 0.35, "threading": 0.50}


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


def build_blended_cp_parameters(
    machines: list[dict],
    products: list[dict],
    compatibility: dict,
    rates: dict,
    lambda_by_process: dict[str, float] = CP_LAMBDA_BY_PROCESS,
) -> dict[str, dict]:
    """Build optimistic, conservative, and lambda-blended C_P by product."""
    result = {}
    for product in products:
        process = product["process"]
        lambda_value = lambda_by_process.get(process)
        if lambda_value is None or not 0 <= lambda_value <= 1:
            raise ValueError(f"C_P lambda for '{process}' must be between 0 and 1")

        process_machines = [
            machine
            for machine in machines
            if machine["active"]
            and machine["process"] == process
            and rates.get(machine["machine_id"], {}).get(
                "machine_rate_units_per_minute"
            )
        ]
        machine_count = len(process_machines)
        total_rate = sum(
            rates[machine["machine_id"]]["machine_rate_units_per_minute"]
            for machine in process_machines
        )
        compatible_rate = sum(
            rates[machine["machine_id"]]["machine_rate_units_per_minute"]
            for machine in process_machines
            if compatibility[machine["machine_id"]][product["product_id"]]
        )

        optimistic_cp = machine_count / total_rate if total_rate else None
        conservative_cp = machine_count / compatible_rate if compatible_rate else None
        blended_cp = (
            (1 - lambda_value) * optimistic_cp + lambda_value * conservative_cp
            if optimistic_cp is not None and conservative_cp is not None
            else None
        )
        result[product["product_id"]] = {
            "optimistic_cp": optimistic_cp,
            "conservative_cp": conservative_cp,
            "lambda": lambda_value,
            "blended_cp": blended_cp,
        }
    return result


def build_processed_parameters(
    machines: list[dict],
    products: list[dict],
    compatibility: dict,
    rates: dict,
    weighted_setup: dict[str, float],
) -> list[dict]:
    """Return C_P and C_S rows for compatible active machine-product pairs."""
    rows = []
    cp_parameters = build_blended_cp_parameters(
        machines, products, compatibility, rates
    )
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
            cp = cp_parameters[product_id]
            rows.append(
                {
                    "machine_id": machine_id,
                    "product_id": product_id,
                    "process": product["process"],
                    "compatible": 1,
                    "machine_rate_units_per_minute": f"{rate:.4f}" if rate else "",
                    "machine_C_P_minutes_per_unit": f"{1 / rate:.4f}" if rate else "",
                    "optimistic_C_P_minutes_per_unit": (
                        f"{cp['optimistic_cp']:.4f}"
                        if cp["optimistic_cp"] is not None
                        else ""
                    ),
                    "conservative_C_P_minutes_per_unit": (
                        f"{cp['conservative_cp']:.4f}"
                        if cp["conservative_cp"] is not None
                        else ""
                    ),
                    "C_P_lambda": f"{cp['lambda']:.4f}",
                    "C_P_minutes_per_unit": (
                        f"{cp['blended_cp']:.4f}"
                        if cp["blended_cp"] is not None
                        else ""
                    ),
                    "weighted_C_S_minutes": f"{weighted_setup[product_id]:.4f}",
                    "rate_as_of_date": rate_record["as_of_date"] if rate_record else "",
                    "rate_version": rate_record["source_version"] if rate_record else "",
                    "data_quality_status": status,
                }
            )
    return rows
