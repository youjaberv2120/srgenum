# Constructs the Paley graph P(q) for a prime power q = 1 (mod 4).
# P(37) is a concrete SRG(37,18,8,9) (the unique one with a vertex-transitive
# automorphism group of order 666), used to validate the encoder/pipeline.

import os


def generate_paley_matrix(q):
    """Adjacency matrix of the Paley graph on GF(q), q prime, q = 1 (mod 4).

    Vertices 0..q-1; i ~ j iff (i - j) is a nonzero quadratic residue mod q.
    (Restricted to prime q so we can stay in pure-Python modular arithmetic.)
    """
    if q % 4 != 1:
        raise ValueError("Paley graph requires q = 1 (mod 4).")
    if not _is_prime(q):
        raise ValueError("This constructor only supports prime q.")

    residues = {(x * x) % q for x in range(1, q)}
    matrix = [[0] * q for _ in range(q)]
    for i in range(q):
        for j in range(q):
            if i != j and (i - j) % q in residues:
                matrix[i][j] = 1
    return matrix


def _is_prime(m):
    if m < 2:
        return False
    d = 2
    while d * d <= m:
        if m % d == 0:
            return False
        d += 1
    return True


def write_matrix_to_file(matrix, filename="ProcessFiles/graph.txt"):
    try:
        with open(filename, "w") as f:
            for row in matrix:
                f.write(" ".join(map(str, row)) + "\n")
        print(f"Successfully wrote the adjacency matrix to '{filename}'")
    except IOError as e:
        print(f"Error: Could not write to file '{filename}'.")
        print(f"Reason: {e}")


def main():
    print("Paley Graph P(q) Adjacency Matrix Generator")
    print("------------------------------------------")
    while True:
        try:
            q = int(input("Enter q (prime, q = 1 mod 4, e.g. 37): "))
            matrix = generate_paley_matrix(q)
            write_matrix_to_file(matrix)
            break
        except ValueError as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
