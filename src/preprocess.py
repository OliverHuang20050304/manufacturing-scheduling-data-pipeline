"""Run the sanitized manufacturing-data preprocessing demonstration."""

import csv
from datetime import date
from pathlib import Path

from compatibility_matrix import build_compatibility_matrix
from parameter_conversion import build_processed_parameters, build_setup_parameters

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "sample_data"
OUTPUT_DIR = ROOT / "output"


def read_csv(name: str) -> list[dict]:
    """Read a sample CSV into a list of dictionaries."""
    with (DATA_DIR / name).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def required_text(row: dict, field: str, row_name: str) -> str:
    """Return stripped required text or raise a useful validation error."""
    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"{row_name}: missing required field '{field}'")
    return value


def required_float(row: dict, field: str, row_name: str) -> float:
    """Parse a required positive numeric field."""
    value = required_text(row, field, row_name)
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{row_name}: '{field}' must be numeric") from error
    if number <= 0:
        raise ValueError(f"{row_name}: '{field}' must be positive")
    return number


def parse_active(value: str, row_name: str) -> bool:
    """Normalize common boolean spellings used by source systems."""
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"{row_name}: invalid active flag '{value}'")


def load_machines() -> list[dict]:
    """Normalize and validate synthetic machine capability records."""
    machines = []
    for index, row in enumerate(read_csv("machines.csv"), start=2):
        row_name = f"machines.csv row {index}"
        machine = {
            "machine_id": required_text(row, "machine_id", row_name).upper(),
            "process": required_text(row, "process", row_name).lower(),
            "diameter_min_mm": required_float(row, "diameter_min_mm", row_name),
            "diameter_max_mm": required_float(row, "diameter_max_mm", row_name),
            "length_min_mm": required_float(row, "length_min_mm", row_name),
            "length_max_mm": required_float(row, "length_max_mm", row_name),
            "supported_head_types": {
                value.strip().lower()
                for value in (row.get("supported_head_types") or "").split("|")
                if value.strip()
            },
            "active": parse_active(required_text(row, "active", row_name), row_name),
        }
        if machine["diameter_min_mm"] > machine["diameter_max_mm"]:
            raise ValueError(f"{row_name}: diameter minimum exceeds maximum")
        if machine["length_min_mm"] > machine["length_max_mm"]:
            raise ValueError(f"{row_name}: length minimum exceeds maximum")
        if machine["process"] == "heading" and not machine["supported_head_types"]:
            raise ValueError(f"{row_name}: heading machine requires supported head types")
        machines.append(machine)
    return machines


def load_products() -> list[dict]:
    """Normalize and validate synthetic product specifications."""
    products = []
    for index, row in enumerate(read_csv("products.csv"), start=2):
        row_name = f"products.csv row {index}"
        product = {
            "product_id": required_text(row, "product_id", row_name).upper(),
            "process": required_text(row, "process", row_name).lower(),
            "head_type": (row.get("head_type") or "").strip().lower(),
            "diameter_mm": required_float(row, "diameter_mm", row_name),
            "length_mm": required_float(row, "length_mm", row_name),
            "batch_weight": required_float(row, "batch_weight", row_name),
        }
        if product["process"] == "heading" and not product["head_type"]:
            raise ValueError(f"{row_name}: heading product requires a head type")
        products.append(product)
    return products


def load_latest_machine_rates() -> dict:
    """Normalize rates and keep the newest dated record for each machine."""
    candidates = {}
    for index, row in enumerate(read_csv("machine_rates.csv"), start=2):
        row_name = f"machine_rates.csv row {index}"
        machine_id = required_text(row, "machine_id", row_name).upper()
        date_text = required_text(row, "as_of_date", row_name)
        try:
            parsed_date = date.fromisoformat(date_text)
        except ValueError as error:
            raise ValueError(f"{row_name}: as_of_date must use YYYY-MM-DD") from error

        raw_rate = (row.get("machine_rate_units_per_minute") or "").strip()
        rate = None if not raw_rate else required_float(
            row, "machine_rate_units_per_minute", row_name
        )
        record = {
            "machine_rate_units_per_minute": rate,
            "as_of_date": date_text,
            "source_version": required_text(row, "source_version", row_name),
            "_parsed_date": parsed_date,
        }

        current = candidates.get(machine_id)
        if current and current["_parsed_date"] == parsed_date and current != record:
            raise ValueError(f"{row_name}: conflicting rates share the latest date")
        if current is None or parsed_date > current["_parsed_date"]:
            candidates[machine_id] = record

    for record in candidates.values():
        del record["_parsed_date"]
    return candidates


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write deterministic UTF-8 CSV output."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Run normalization, compatibility checks, and parameter conversion."""
    machines = load_machines()
    products = load_products()
    rates = load_latest_machine_rates()
    compatibility = build_compatibility_matrix(machines, products)
    setup_rows, weighted_setup = build_setup_parameters(products)
    parameter_rows = build_processed_parameters(
        machines, products, compatibility, rates, weighted_setup
    )

    OUTPUT_DIR.mkdir(exist_ok=True)
    product_ids = [product["product_id"] for product in products]
    matrix_rows = [
        {"machine_id": machine_id, **product_flags}
        for machine_id, product_flags in compatibility.items()
    ]
    write_csv(
        OUTPUT_DIR / "compatibility_matrix.csv",
        ["machine_id", *product_ids],
        matrix_rows,
    )
    write_csv(
        OUTPUT_DIR / "processed_parameters.csv",
        [
            "machine_id",
            "product_id",
            "process",
            "compatible",
            "machine_rate_units_per_minute",
            "C_P_minutes_per_unit",
            "weighted_C_S_minutes",
            "rate_as_of_date",
            "rate_version",
            "data_quality_status",
        ],
        parameter_rows,
    )
    write_csv(
        OUTPUT_DIR / "setup_times.csv",
        [
            "process",
            "from_product_id",
            "to_product_id",
            "changed_attributes",
            "C_S_minutes",
        ],
        setup_rows,
    )

    missing_rates = sum(row["data_quality_status"] != "ok" for row in parameter_rows)
    print(f"Wrote {len(matrix_rows)} machine rows to compatibility_matrix.csv")
    print(f"Wrote {len(parameter_rows)} compatible pairs to processed_parameters.csv")
    print(f"Wrote {len(setup_rows)} product transitions to setup_times.csv")
    print(f"Flagged {missing_rates} compatible pair(s) with missing machine rates")


if __name__ == "__main__":
    main()
