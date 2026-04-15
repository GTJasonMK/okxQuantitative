from __future__ import annotations

import random


MIN_BLOCK_LENGTH = 9
BOOTSTRAP_DEFINITION_VERSION = 'stationary_block_bootstrap_min9_v1'


def stationary_block_bootstrap_mean(
    *,
    values: list[float],
    avg_block_length: int,
    bootstrap_repeats: int,
) -> dict[str, object]:
    _validate_bootstrap_inputs(
        values=values,
        avg_block_length=avg_block_length,
        bootstrap_repeats=bootstrap_repeats,
    )
    draws = stationary_bootstrap(
        values=values,
        avg_block_length=avg_block_length,
        bootstrap_repeats=bootstrap_repeats,
    )
    means = [sum(draw) / len(draw) for draw in draws]
    ordered = sorted(means)
    lower_index = max(0, int(len(ordered) * 0.025) - 1)
    upper_index = min(len(ordered) - 1, int(len(ordered) * 0.975))
    return {
        'definition_version': BOOTSTRAP_DEFINITION_VERSION,
        'avg_block_length': int(avg_block_length),
        'bootstrap_repeats': int(bootstrap_repeats),
        'sample_count': len(values),
        'mean': sum(values) / len(values),
        'ci_95': [ordered[lower_index], ordered[upper_index]],
    }


def stationary_bootstrap(
    *,
    values: list[float],
    avg_block_length: int,
    bootstrap_repeats: int,
) -> list[list[float]]:
    rng = random.Random(7)
    block_restart_prob = min(1.0, 1.0 / max(int(avg_block_length), 1))
    draws = []
    for _ in range(int(bootstrap_repeats)):
        draws.append(_draw_stationary_sample(values, block_restart_prob, rng))
    return draws


def _validate_bootstrap_inputs(
    *,
    values: list[float],
    avg_block_length: int,
    bootstrap_repeats: int,
) -> None:
    if len(values) == 0:
        raise ValueError('bootstrap values must be non-empty')
    if int(avg_block_length) < MIN_BLOCK_LENGTH:
        raise ValueError('avg_block_length must be at least 9')
    if int(bootstrap_repeats) <= 0:
        raise ValueError('bootstrap_repeats must be positive')


def _draw_stationary_sample(
    values: list[float],
    block_restart_prob: float,
    rng: random.Random,
) -> list[float]:
    index = rng.randrange(len(values))
    draw = []
    for _ in range(len(values)):
        draw.append(values[index])
        if rng.random() < block_restart_prob:
            index = rng.randrange(len(values))
        else:
            index = (index + 1) % len(values)
    return draw
