from pathlib import Path

filename = Path("constant/porousMat/BoundaryConditions_0")

lines = filename.read_text().splitlines()

# Skip:
# 0 TITLE
# 1 VARIABLES
# 2 ZONE
# 3 Ordered
# 4 DATAPACKING
# 5 DT
data = []

for line in lines[6:]:
    line = line.strip()
    if line:
        data.extend(line.split())

N = 20252

print("Expected values:", 4*N)
print("Actual values:  ", len(data))
print("Difference:     ", len(data) - 4*N)

if len(data) == 4*N:
    print("PASS: Tecplot data count is correct.")
else:
    print("FAIL: Tecplot data count is incorrect.")

    if len(data) >= N:
        print("X block ends at:", N)

    if len(data) >= 2*N:
        print("Y block ends at:", 2*N)

    if len(data) >= 3*N:
        print("Z block ends at:", 3*N)

    if len(data) >= 4*N:
        print("q block ends at:", 4*N)