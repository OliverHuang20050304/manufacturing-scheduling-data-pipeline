# Manufacturing Scheduling Data Pipeline — Sanitized Demo

This repository is a small, sanitized demonstration of my data-processing work in a seven-person university manufacturing-scheduling project. My main responsibility in the original project was preparing manufacturing data and converting it into parameters that the scheduling model could consume.

The original team repository is private because it may contain data provided by an industry partner. This public repository is not the full scheduling system: it contains newly written demonstration code and entirely synthetic data. It does not contain or attempt to reconstruct any company records.

## What this demo shows

- cleaning and standardizing machine, product, and machine-rate records;
- building a binary machine–product compatibility matrix;
- deriving sequence-dependent setup time (`C_S`) from product attributes;
- reducing pairwise setup times to a weighted per-product parameter;
- selecting the latest machine-rate record and converting it to processing time (`C_P`);
- blending optimistic and conservative `C_P` estimates with a configurable synthetic lambda;
- handling inactive machines, missing rates, inconsistent text formatting, and source-version tracking.

## Repository structure

```text
.
├── README.md
├── sample_data/
│   ├── machines.csv
│   ├── products.csv
│   └── machine_rates.csv
├── src/
│   ├── preprocess.py
│   ├── compatibility_matrix.py
│   └── parameter_conversion.py
└── output/
    ├── compatibility_matrix.csv
    ├── processed_parameters.csv
    └── setup_times.csv
```

| File | Purpose |
| --- | --- |
| `src/preprocess.py` | Loads and normalizes CSV files, validates required fields, selects current rate versions, and runs the pipeline. |
| `src/compatibility_matrix.py` | Applies process, diameter, length, and head-type constraints to produce a 0/1 compatibility matrix. |
| `src/parameter_conversion.py` | Converts machine rate to `C_P`, applies lambda blending, and derives pairwise and weighted `C_S` values. |
| `sample_data/*.csv` | Small synthetic examples, including harmless formatting and missing-rate cases. |
| `output/compatibility_matrix.csv` | Machine × product 0/1 matrix for active machines. |
| `output/processed_parameters.csv` | Compatible machine–product combinations with `C_P`, weighted `C_S`, version metadata, and quality status. |
| `output/setup_times.csv` | Auditable pairwise `C_S` calculations. |

## Parameter logic

A machine and product are compatible when they use the same process and the product's diameter and length are within the machine's supported ranges. Head type is checked only for the heading process.

For a usable machine rate in units per minute, the machine-level processing time is:

```text
machine C_P (minutes per unit) = 1 / machine rate
```

The demo also derives process-level estimates. The optimistic estimate uses all active machines with valid rates in the process, while the conservative estimate uses only machines compatible with the product:

```text
optimistic C_P   = valid machine count / sum of all valid process rates
conservative C_P = valid machine count / sum of compatible valid rates
final C_P        = (1 - lambda) × optimistic C_P + lambda × conservative C_P
```

The synthetic configuration uses `lambda = 0.35` for heading and `lambda = 0.50` for threading. Lambda must remain between 0 and 1. These values are illustrative and are not derived from company data or the private project.

Pairwise `C_S` compares head type, diameter, and length. In this demonstration, no changed attribute gives 0 minutes, one changed attribute gives 30 minutes, and two or more changed attributes give 75 minutes. These are illustrative constants, not company values. The pipeline then calculates a batch-weighted average for each target product because the simplified scheduling input expects one setup value per product.

Missing machine rates are not guessed or imputed. The affected row remains in `processed_parameters.csv`, unavailable `C_P` values are blank, and its status is `missing_machine_rate`. When several rate records exist, the most recent `as_of_date` is selected and its `source_version` is retained.

## Run

Python 3.10 or later is sufficient; no third-party packages are required.

```bash
python3 src/preprocess.py
```

The command recreates all files under `output/` and prints a short summary.

## Scope and limitations

This repository demonstrates only the data-processing portion that I primarily worked on. The scheduling model, optimization algorithms, application integration, and other team members' work are intentionally excluded. The data model and rule values are simplified for public explanation and should not be treated as production manufacturing assumptions.
