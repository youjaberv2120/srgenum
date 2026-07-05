# Reads adjacency matrix of graph from ProcessFiles/graph.txt and returns matrix and matrix
# analysis functions such as inner degree/outer degree calculations and neighbor counter.

#Matrix Print
def printAdj(matrix):
    for row in matrix:
        print(''.join(map(str,row)))

#Read adjacency matrix
def get_graph(graphPath):
    
    with open(graphPath,'r') as path:
        
        #Read adjacency matric lines
        lines = [line.strip() for line in path.readlines() if line.strip()]
        n = len(lines)
        
        #Create empty adjacency matrix
        matrix = [[None for _ in range(n)] for _ in range(n)]
        
        #Populate adjacency matrix (read/write entries)
        for i in range(n):
            row = lines[i].split()
            
            #Check if valid row length and int type
            if len(row) != n:
                raise ValueError(f"Row {i+1} has {len(row)} entries, expected {n}")
            try:
                row = [int(x) for x in row]
            except ValueError:
                raise ValueError(f"Row {i+1} contains non-integer values")
            
            #Check binary
            if not all(x in (0,1) for x in row):
                raise ValueError(f"Row {i+1} contains values other than 0 or 1")
            
            #Ensure 0 along diagonals since no vertex
            #can be connected to itself (requirement).
            if row[i] != 0:
                raise ValueError(f"Row {i+1} contains a non-zero diagonal value, no vertex can be connected to itself")
            
            #Check symmetry -- adjacency matrix should be
            #symmetric, don't accept upper triangular.
            for j in range(n):
                if matrix[j][i] is not None and matrix[j][i] != row[j]:
                    raise ValueError(f"Matrix break symmetry for coordinates: ({i+1},{j+1}) and ({j+1},{i+1})")
                
            matrix[i] = row
        
        #Confirm succesful read and write
        print("Succesful wrote adjacency matrix from {graphPath}.")
        printAdj(matrix)
        
        #Define matrix specific helpers
        #Get matrix entry
        def entry(i,j):
            try:
                return matrix[i-1][j-1]
            except IndexError:
                raise IndexError(f"Indices ({i},{j}) out of bounds for matrix of size {n}")
            
        def isEdge(i,j):
            if entry(i,j) == 0:
                return False
            else:
                return True
        
        #Get interior degree (within subgraph)
        def inDegree(i):
            try:
                return sum(matrix[i-1])
            except IndexError:
                raise IndexError(f"Index {i} out of bounds for matrix of size {n}")
        
        #Check if vertex k is a neighbor of vertices i and j
        def isShared(i,j,k):
            return isEdge(i,k) and isEdge(j,k)
            
        #Get number of shared vertices
        def getShared(i,j):
            count = 0
            for k in range(n):
                if isShared(i,j,k):
                    count+=1
            return count
        
        return matrix, isEdge, inDegree, isShared, getShared