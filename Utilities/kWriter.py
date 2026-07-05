# Takes argument n via command line from user and writes
# n-vertex complete graph to graph.txt.

import sys
import os

# K-n Graph Adjacency Matrix Generator
def generateKGraph(n):
    
    #Check parameters for n
    if (n <= 0) or not isinstance(n,int):
        raise ValueError("n should be a positive natural.")

    # Create n x n matrix initialized with 1s.
    matrix = [[1 for _ in range(n)] for _ in range(n)]

    # Set diagonal elements to 0 (no self-adjacency)
    for i in range(n):
        matrix[i][i] = 0

    return matrix

#Write matrix to file
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
    print("Complete Graph (K_n) Adjacency Matrix Generator")
    print("---------------------------------------------")

    unsuccessful = True
    while unsuccessful:
        try:
            # Get user input for the number of vertices 'n'
            n_input = input("Enter the number of vertices (n) for the complete graph: ")
            n = int(n_input)
            
            # Generate the matrix
            adjacency_matrix = generateKGraph(n)

            # If the matrix was generated successfully, write it to the file
            if adjacency_matrix:
                write_matrix_to_file(adjacency_matrix)
                unsuccessful = False
        except ValueError:
            # Handle cases where the input is not a valid integer
            print(f"Error: Invalid input. '{n_input}' is not an integer. Please try again.")
        except Exception as e:
            # Handle other potential errors
            print(f"An unexpected error occurred: {e}")
            break

if __name__ == "__main__":
    main()