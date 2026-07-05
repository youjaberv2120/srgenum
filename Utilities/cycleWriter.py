# Takes argument n via command line from user and writes
# n-vertex cycle graph to graph.txt.

def generate_cycle_adjacency_matrix(n):
    if not isinstance(n, int) or n <= 0:
        print("Error: Please enter a positive integer for the number of vertices.")
        return []

    if n < 3:
        print("Note: A true cycle graph is typically defined for n >= 3.")
        print("      Generating a graph for this degenerate case.")

    # Create an n x n matrix initialized with 0s.
    matrix = [[0 for _ in range(n)] for _ in range(n)]

    # For each vertex, connect it to its two neighbors.
    for i in range(n):
        # The modulo operator (%) handles the "wraparound" for the cycle.
        # For vertex 0, its previous neighbor is (0-1)%n = n-1.
        # For vertex n-1, its next neighbor is (n-1+1)%n = 0.
        previous_neighbor = (i - 1) % n
        next_neighbor = (i + 1) % n

        matrix[i][previous_neighbor] = 1
        matrix[i][next_neighbor] = 1

    return matrix

def write_matrix_to_file(matrix, filename="ProcessFiles/graph.txt"):
    try:
        with open(filename, 'w') as f:
            for row in matrix:
                # Convert each integer in the row to a string and join with spaces
                f.write(' '.join(map(str, row)) + '\n')
        print(f"Successfully wrote the adjacency matrix to '{filename}'")
    except IOError as e:
        print(f"Error: Could not write to file '{filename}'.")
        print(f"Reason: {e}")

def main():
    print("Cycle Graph (C_n) Adjacency Matrix Generator")
    print("------------------------------------------")

    while True:
        try:
            # Get user input for the number of vertices 'n'
            n_input = input("Enter the number of vertices (n) for the cycle graph: ")
            n = int(n_input)
            
            # Generate the matrix
            adjacency_matrix = generate_cycle_adjacency_matrix(n)

            # If the matrix was generated successfully, write it to the file
            if adjacency_matrix:
                write_matrix_to_file(adjacency_matrix)
                break  # Exit the loop on successful execution
        except ValueError:
            # Handle cases where the input is not a valid integer
            print(f"Error: Invalid input. '{n_input}' is not an integer. Please try again.")
        except Exception as e:
            # Handle other potential errors
            print(f"An unexpected error occurred: {e}")
            break

if __name__ == "__main__":
    main()