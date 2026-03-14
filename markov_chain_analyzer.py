# !/usr/bin/env python3
"""Markov chain transition matrix analyzer.

Supports three mathematical input modes:
1. sequence: estimate transition probabilities from an observed state sequence
2. counts: normalize transition counts/weights into a probability matrix
3. matrix: validate an existing transition matrix
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


EPSILON = 1e-9


class InputError(ValueError):
    """Raised when the input payload cannot be analyzed."""


@dataclass
class AnalysisResult:
    states: List[str]
    matrix: List[List[float]]
    mode: str
    row_sums: List[float]
    absorbing_states: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "mode": self.mode,
            "states": self.states,
            "transition_probability_matrix": self.matrix,
            "row_sums": self.row_sums,
            "absorbing_states": self.absorbing_states,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a Markov chain and output its transition probability matrix."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        help="Path to a JSON input file. If omitted, JSON is read from stdin.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "table"),
        default="table",
        help="Output format for the analysis result.",
    )
    parser.add_argument(
        "--precision",
        type=int,
        default=4,
        help="Decimal precision used when printing table output.",
    )
    return parser.parse_args()


def load_payload(path: Path | None) -> Dict[str, object]:
    if path is None:
        raw = input_json_from_stdin()
    else:
        raw = path.read_text(encoding="utf-8")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InputError(f"Input is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise InputError("Top-level JSON value must be an object.")
    return payload


def input_json_from_stdin() -> str:
    print("请输入 JSON 数据，然后按 Ctrl+Z 回车结束输入：")
    lines: List[str] = []
    while True:
        try:
            lines.append(input())
        except EOFError:
            break
    return "\n".join(lines).strip()


def analyze_markov_chain(payload: Dict[str, object]) -> AnalysisResult:
    mode = str(payload.get("mode", "")).strip().lower()
    if mode not in {"sequence", "counts", "matrix"}:
        raise InputError("mode must be one of: sequence, counts, matrix.")

    if mode == "sequence":
        states, matrix = matrix_from_sequence(payload)
    elif mode == "counts":
        states, matrix = matrix_from_counts(payload)
    else:
        states, matrix = matrix_from_existing_matrix(payload)

    row_sums = [round(sum(row), 10) for row in matrix]
    absorbing_states = find_absorbing_states(states, matrix)
    return AnalysisResult(
        states=states,
        matrix=matrix,
        mode=mode,
        row_sums=row_sums,
        absorbing_states=absorbing_states,
    )


def matrix_from_sequence(payload: Dict[str, object]) -> tuple[List[str], List[List[float]]]:
    sequence = payload.get("sequence")
    if not isinstance(sequence, list) or len(sequence) < 2:
        raise InputError("sequence mode requires a list with at least two states.")

    normalized_sequence = [normalize_state_name(item) for item in sequence]
    states = get_states(payload.get("states"), normalized_sequence)
    index = {state: idx for idx, state in enumerate(states)}
    counts = [[0.0 for _ in states] for _ in states]

    for current_state, next_state in zip(normalized_sequence, normalized_sequence[1:]):
        counts[index[current_state]][index[next_state]] += 1.0

    matrix = normalize_rows(counts)
    return states, matrix


def matrix_from_counts(payload: Dict[str, object]) -> tuple[List[str], List[List[float]]]:
    transitions = payload.get("transitions")
    if not isinstance(transitions, list) or not transitions:
        raise InputError("counts mode requires a non-empty transitions list.")

    discovered_states: List[str] = []
    normalized_transitions = []
    for item in transitions:
        if not isinstance(item, dict):
            raise InputError("Each transition must be an object.")

        from_state = normalize_state_name(item.get("from"))
        to_state = normalize_state_name(item.get("to"))
        value = item.get("value", 1)
        if not isinstance(value, (int, float)) or value < 0:
            raise InputError("Transition value must be a non-negative number.")

        if from_state not in discovered_states:
            discovered_states.append(from_state)
        if to_state not in discovered_states:
            discovered_states.append(to_state)
        normalized_transitions.append((from_state, to_state, float(value)))

    states = get_states(payload.get("states"), discovered_states)
    index = {state: idx for idx, state in enumerate(states)}
    counts = [[0.0 for _ in states] for _ in states]

    for from_state, to_state, value in normalized_transitions:
        counts[index[from_state]][index[to_state]] += value

    matrix = normalize_rows(counts)
    return states, matrix


def matrix_from_existing_matrix(
    payload: Dict[str, object]
) -> tuple[List[str], List[List[float]]]:
    raw_matrix = payload.get("matrix")
    if not isinstance(raw_matrix, list) or not raw_matrix:
        raise InputError("matrix mode requires a non-empty matrix field.")
    if not all(isinstance(row, list) for row in raw_matrix):
        raise InputError("matrix must be a two-dimensional array.")

    size = len(raw_matrix)
    raw_states = payload.get("states")
    if raw_states is None:
        states = [f"S{i + 1}" for i in range(size)]
    else:
        if not isinstance(raw_states, list) or not raw_states:
            raise InputError("states must be a non-empty list when provided.")
        states = [normalize_state_name(item) for item in raw_states]
        if len(states) != size:
            raise InputError("Number of states must match matrix dimensions.")

    matrix: List[List[float]] = []
    for row in raw_matrix:
        if len(row) != size:
            raise InputError("matrix must be square.")
        normalized_row: List[float] = []
        for value in row:
            if not isinstance(value, (int, float)) or value < 0:
                raise InputError("matrix values must be non-negative numbers.")
            normalized_row.append(float(value))
        matrix.append(normalized_row)

    normalize = bool(payload.get("normalize", False))
    if normalize:
        matrix = normalize_rows(matrix)
    else:
        validate_probability_matrix(matrix)
    return states, matrix


def get_states(raw_states: object, discovered_states: Sequence[str]) -> List[str]:
    if raw_states is None:
        return list(dict.fromkeys(discovered_states))
    if not isinstance(raw_states, list) or not raw_states:
        raise InputError("states must be a non-empty list when provided.")

    states = [normalize_state_name(item) for item in raw_states]
    missing = [state for state in discovered_states if state not in states]
    if missing:
        raise InputError(
            "states is missing the following states referenced by the input: "
            + ", ".join(missing)
        )
    return states


def normalize_state_name(value: object) -> str:
    if value is None:
        raise InputError("State names cannot be null.")
    text = str(value).strip()
    if not text:
        raise InputError("State names cannot be empty.")
    return text


def normalize_rows(matrix: Sequence[Sequence[float]]) -> List[List[float]]:
    normalized: List[List[float]] = []
    for row in matrix:
        row_sum = float(sum(row))
        if row_sum <= EPSILON:
            normalized.append([0.0 for _ in row])
        else:
            normalized.append([value / row_sum for value in row])
    return normalized


def validate_probability_matrix(matrix: Sequence[Sequence[float]]) -> None:
    for idx, row in enumerate(matrix):
        row_sum = float(sum(row))
        if abs(row_sum - 1.0) > EPSILON:
            raise InputError(
                f"Row {idx} sums to {row_sum:.10f}, not 1.0. "
                "Pass normalize=true to auto-normalize."
            )


def find_absorbing_states(states: Sequence[str], matrix: Sequence[Sequence[float]]) -> List[str]:
    absorbing: List[str] = []
    for idx, row in enumerate(matrix):
        diagonal = row[idx]
        off_diagonal_sum = sum(value for col, value in enumerate(row) if col != idx)
        if abs(diagonal - 1.0) <= EPSILON and off_diagonal_sum <= EPSILON:
            absorbing.append(states[idx])
    return absorbing


def render_table(result: AnalysisResult, precision: int) -> str:
    states = result.states
    formatted_rows: List[List[str]] = []
    for state, row, row_sum in zip(states, result.matrix, result.row_sums):
        formatted = [f"{value:.{precision}f}" for value in row]
        formatted_rows.append([state, *formatted, f"{row_sum:.{precision}f}"])

    headers = ["state", *states, "row_sum"]
    widths = [len(header) for header in headers]
    for row in formatted_rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    lines = []
    title = f"Mode: {result.mode}"
    lines.append(title)
    lines.append(format_row(headers, widths))
    lines.append(format_row(["-" * width for width in widths], widths))
    for row in formatted_rows:
        lines.append(format_row(row, widths))

    if result.absorbing_states:
        lines.append("Absorbing states: " + ", ".join(result.absorbing_states))
    else:
        lines.append("Absorbing states: none")
    return "\n".join(lines)


def format_row(values: Iterable[str], widths: Sequence[int]) -> str:
    return " | ".join(str(value).ljust(width) for value, width in zip(values, widths))


def main() -> int:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    args = parse_args()
    try:
        payload = load_payload(args.input)
        result = analyze_markov_chain(payload)
    except InputError as exc:
        print(f"[ERROR] {exc}")
        return 1
    except FileNotFoundError as exc:
        print(f"[ERROR] Input file not found: {exc.filename}")
        return 1

    if args.format == "json":
        print(
            json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(render_table(result, args.precision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
