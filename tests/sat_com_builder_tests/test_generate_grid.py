from collections import defaultdict

import pytest

from sat_com_builder.links.inter_satellite_link_generator import (
    generate_sun_synchronous_constellation_grid,
    generate_checkerboard_walker_star_constellation_grid,
    generate_checkerboard_walker_delta_constellation_grid,
)


def compute_degrees(links):
    degree = defaultdict(int)
    for u, v, _ in links:
        degree[u] += 1
        degree[v] += 1
    return degree


def assert_basic_graph_sanity(links, total_nodes):
    seen = set()

    for u, v, _ in links:
        assert u != v
        assert 0 <= u < total_nodes
        assert 0 <= v < total_nodes

        edge = (min(u, v), max(u, v))
        assert edge not in seen
        seen.add(edge)


VALID_CHECKERBOARD_DELTA = [
    (4, 4),
    (6, 10),
    (10, 20),
    (10, 120),
]

INVALID_CHECKERBOARD_DELTA = [
    (3, 3),
    (5, 5),
    (4, 5),
    (5, 4),
    (7, 10),
    (10, 7),
]


@pytest.mark.parametrize("n_orbits,n_sats", VALID_CHECKERBOARD_DELTA)
def test_checkerboard_delta_valid(n_orbits, n_sats):
    links = generate_checkerboard_walker_delta_constellation_grid(
        n_orbits, n_sats, isl_shift=0
    )

    total_nodes = n_orbits * n_sats

    assert_basic_graph_sanity(links, total_nodes)

    degree = compute_degrees(links)

    for node in range(total_nodes):
        assert degree[node] == 3


@pytest.mark.parametrize("n_orbits,n_sats", INVALID_CHECKERBOARD_DELTA)
def test_checkerboard_delta_invalid(n_orbits, n_sats):
    with pytest.raises(ValueError):
        generate_checkerboard_walker_delta_constellation_grid(
            n_orbits, n_sats, isl_shift=0
        )


VALID_CHECKERBOARD_STAR = [
    (3, 4),
    (5, 6),
    (10, 20),
    (10, 120),
]

INVALID_CHECKERBOARD_STAR = [
    (3, 3),
    (5, 5),
    (10, 7),
]


@pytest.mark.parametrize("n_orbits,n_sats", VALID_CHECKERBOARD_STAR)
def test_checkerboard_star_valid(n_orbits, n_sats):
    links = generate_checkerboard_walker_star_constellation_grid(
        n_orbits, n_sats, isl_shift=0
    )
    print(links)

    total_nodes = n_orbits * n_sats

    assert_basic_graph_sanity(links, total_nodes)

    degree = compute_degrees(links)

    for node in range(total_nodes):
        assert degree[node] <= 3

    for i in range(n_orbits):
        for j in range(n_sats):
            node = i * n_sats + j

            outgoing = i % 2 == j % 2
            incoming = (i > 0) and ((i - 1) % 2 == j % 2)

            expected_degree = 2 + int(outgoing) + int(incoming)

            if i == n_orbits - 1:
                expected_degree = 2 + int(incoming)

            assert degree[node] == expected_degree


@pytest.mark.parametrize("n_orbits,n_sats", INVALID_CHECKERBOARD_STAR)
def test_checkerboard_star_invalid(n_orbits, n_sats):
    with pytest.raises(ValueError):
        generate_checkerboard_walker_star_constellation_grid(
            n_orbits, n_sats, isl_shift=0
        )


def test_sun_synchronous():
    n = 50
    links = generate_sun_synchronous_constellation_grid(n)

    degree = compute_degrees(links)

    for node in range(n):
        assert degree[node] == 2
