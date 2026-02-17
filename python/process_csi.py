import numpy as np
import matplotlib.pyplot as plt

def load_csi(filename):
    data = []
    with open(filename) as f:
        for line in f:
            if "CSI_DATA:" in line:
                parts = line.replace("CSI_DATA:", "").strip().split()
                values = [int(x) for x in parts]
                data.append(values)

    min_len = min(len(row) for row in data)
    data = [row[:min_len] for row in data]

    return np.array(data)

empty = load_csi("../data/empty.txt")
occupied = load_csi("../data/occupied.txt")
walking = load_csi("../data/walking.txt")
wall = load_csi("../data/wall.txt")

empty_energy = np.mean(np.abs(empty), axis=1)
occupied_energy = np.mean(np.abs(occupied), axis=1)
walking_energy = np.mean(np.abs(walking), axis=1)
wall_energy = np.mean(np.abs(wall), axis=1)


plt.figure(figsize=(12,6))

plt.plot(empty_energy, label="Empty Room")
plt.plot(occupied_energy, label="Occupied (Still)")
plt.plot(walking_energy, label="Walking")
plt.plot(wall_energy, label="Behind Wall")

plt.title("CSI Energy Comparison")
plt.xlabel("Time")
plt.ylabel("CSI Energy")
plt.legend()
plt.grid()

plt.show()

