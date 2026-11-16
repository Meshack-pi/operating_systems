# operating_systems

OS Group Project, Topic 8: **Implementing a File System** (Silberschatz et al., *Operating System Concepts* 10e, Ch. 14).

| File | What it is |
|---|---|
| `Simulation_Script.md` | 10-minute "Records Office" role-play: cast, props, lines, timings, Q&A prep |
| `demo/fs_sim.py` | Python simulator (standard library only) of all 4 concepts + failure cases |
| `demo/wsl_demo.sh` | Live WSL Ubuntu demo on real ext4 structures |

## Simulator

```bash
python3 demo/fs_sim.py              # all scenes, Enter = next step
python3 demo/fs_sim.py scene 4      # 1 layers, 2 on-disk, 3 in-memory, 4 directory, 5 superblock failure
python3 demo/fs_sim.py bench        # linear list vs hash table benchmark
python3 demo/fs_sim.py --no-pause   # rehearsal, runs straight through
```

## WSL demo

```bash
sudo apt install -y e2fsprogs lsof strace   # once
cd ~ && cp /mnt/c/<path>/demo/wsl_demo.sh . # run from ext4, not /mnt/c
bash wsl_demo.sh            # all parts (Enter between steps); or: bash wsl_demo.sh 3
NO_PAUSE=1 bash wsl_demo.sh # rehearsal      NO_SUDO=1 skips optional sudo steps
bash wsl_demo.sh clean      # remove ~/fs_demo
```

Everything runs in `~/fs_demo`. The superblock is only ever corrupted inside a 256 MB image file.
