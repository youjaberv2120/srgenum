# path_generator.py
# Takes an integer n as input and writes the adjacency matrix for an
# n-vertex path graph (P_n) to 'processFiles/graph.txt'.

import os

def generate_path_adjacency_matrix(n):
    """
    Generates an n x n adjacency matrix for a path graph (P_n).

    In a path graph, vertex 'i' is connected to 'i-1' and 'i+1',
    except for the endpoints.
    - Vertex 0 is only connected to vertex 1.
    - Vertex n-1 is only connected to vertex n-2.

    Args:
        n (int): The number of vertices in the path graph.

    Returns:
        list[list[int]]: The n x n adjacency matrix, or an empty list if n is invalid.
    """
    if not isinstance(n, int) or n <= 0:
        print("Error: Please enter a positive integer for the number of vertices.")
        return []

    if n == 1:
        print("Note: A path with 1 vertex has no edges.")

    # Create an n x n matrix initialized with 0s.
    matrix = [[0 for _ in range(n)] for _ in range(n)]

    # For each vertex from 0 to n-2, connect it to the next one.
    # This creates the path structure.
    for i in range(n - 1):
        # Connect vertex i to vertex i+1
        matrix[i][i + 1] = 1
        # Since the graph is undirected, connect vertex i+1 back to i
        matrix[i + 1][i] = 1

    return matrix

def write_matrix_to_file(matrix, directory="ProcessFiles", filename="graph.txt"):
    """
    Writes a given matrix to a specified file.

    Args:
        matrix (list[list[int]]): The adjacency matrix to write.
        directory (str): The directory to save the file in.
        filename (str): The name of the output file.
    """
    # Ensure the target directory exists.
    if not os.path.exists(directory):
        print(f"Directory '{directory}' not found. Creating it.")
        os.makedirs(directory)
        
    filepath = os.path.join(directory, filename)

    try:
        with open(filepath, 'w') as f:
            for row in matrix:
                # Convert each integer in the row to a string and join with spaces
                f.write(' '.join(map(str, row)) + '\n')
        print(f"Successfully wrote the adjacency matrix to '{filepath}'")
    except IOError as e:
        print(f"Error: Could not write to file '{filepath}'.")
        print(f"Reason: {e}")

def main():
    """
    Main function to drive the user interaction, generation, and file writing.
    """
    print("Path Graph (P_n) Adjacency Matrix Generator")
    print("------------------------------------------")

    while True:
        try:
            # Get user input for the number of vertices 'n'
            n_input = input("Enter the number of vertices (n) for the path graph: ")
            n = int(n_input)
            
            # Generate the matrix
            adjacency_matrix = generate_path_adjacency_matrix(n)

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
