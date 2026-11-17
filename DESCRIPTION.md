# What the demo programs do

Our simulation is set in a **University Records Office**. The office stands for a file system:

| In the office | In the file system |
|---|---|
| The filing cabinet | The disk (volume) |
| The four desks a request passes through | The four layers of the file system |
| The ledger on the cabinet | The superblock (volume control block) |
| A folder's cover sheet | The FCB / inode |
| The index the clerk searches | The directory |
| The whiteboard of folders currently out | The system-wide open-file table |
| Each staff member's sticky note | The per-process open-file table |
| The sign on the door ("cabinet attached at /records") | The mount table |

Two programs back up the role-play on screen:

- **`demo/fs_sim.py`** is a **model**. It is a small file system written from scratch in Python, so we can show what is inside each structure and count exactly how much work each design does. It needs only Python 3, so it runs on any laptop.
- **`demo/wsl_demo.sh`** is the **real thing**. It runs Linux commands on WSL Ubuntu, so the class sees the same structures inside a real ext4 file system and a real kernel.

Each idea is shown three ways: **acted out** with props, **modelled** in Python, and **proven** on Linux.

---

## 1. `fs_sim.py`: the Python simulator

### High level

The program builds a pretend 4 MB disk of 4,096 blocks of 1 KB each, formats it, and fills it with ten student records (`amina.rec` … `wanjiru.rec`). It then runs five scenes, one per concept plus the failure case, and pauses after each step so the narrator can explain. When **tracing** is switched on, every layer prints a coloured, indented line as it does its job, so the class can watch a single request travel down through the layers.

```bash
python3 demo/fs_sim.py              # all five scenes, Enter = next step
python3 demo/fs_sim.py scene 3      # just one scene
python3 demo/fs_sim.py bench        # just the linear vs hash benchmark
python3 demo/fs_sim.py --no-pause   # rehearsal: runs straight through
```

**How realistic it is:** the boot block, the superblock and the file contents are stored as **real bytes** inside the simulated blocks. That is why corrupting the superblock really breaks mounting. Inodes and directory entries are kept as Python objects, but each one has a **real block address**. Every lookup therefore performs the same block reads that a real disk would.

### How the code is organised

| Part of the code | Plays the role of | What it does |
|---|---|---|
| `Volume.driver_read` | **I/O control** (device driver) | Turns "read block 172" into "READ sectors 344–345" and counts actual disk reads |
| `Volume.bread` | **Basic file system** | Asks for blocks by number, keeps a **buffer cache**, and only calls the driver on a cache miss |
| `Volume.phys`, `Volume.alloc` | **File-organisation module** | Translates "block 0 of this file" into a physical block number, and hands out free blocks |
| `Volume.search`, `create`, `mount`, `superblock` | **Logical file system** | Owns the directory, the inodes (FCBs) and the superblock |
| `Linear`, `Hash` | **Directory implementations** | The two ways of storing names that we compare |
| `Kernel` | **In-memory structures** | The mount table, the system-wide open-file table and each process's open-file table |

### Scene by scene

**Scene 1: Layered structure ("the request walks past four desks")**
A program asks for `open("/records/wanjiru.rec")` and then reads 40 bytes. With tracing on, the screen shows:
1. **Application:** the program only knows a name.
2. **Logical file system:** checks the mount table, hashes the name, searches the directory, finds inode 20, and loads its FCB.
3. **File-organisation module:** "block 0 of inode 20 is physical block 172".
4. **Basic file system:** "block 172 is not in the cache, ask I/O control".
5. **I/O control and device:** "READ sectors 344–345", and the disk raises an interrupt.

The same read is then repeated. This time the basic file system finds block 172 **in its buffer cache**, the lower layers are never called, and the program reports *0 disk reads*. **What it demonstrates:** each layer has one job and passes the request down, and caching at the basic-FS layer saves real disk work.

**Scene 2: On-disk structures ("open the cabinet")**
This scene shows what is permanently stored on the disk:
- A **disk map**: `B` boot block, `S` superblock, `M` free-space bitmap, `I` inode table, `D` directory blocks, `#` used data blocks. The backup superblock is at the last block, 4095.
- **Block 0, the boot control block:** "no operating system on this volume".
- **Block 1, the superblock**, shown as raw hex and then decoded: magic number `OSFS`, block size, block count, inode count, free blocks and label.
- **The directory:** a table of file **name → inode number**.
- **The FCB of `wanjiru.rec`:** owner, permissions, size, link count and data-block pointers. **It has no name in it.**

**What it demonstrates:** names live in the directory and everything else lives in the FCB. The superblock describes the whole volume, and its magic number is what lets the OS recognise the volume.

**Scene 3: In-memory structures ("the whiteboard and the sticky notes")**
- It mounts two volumes, `/records` (directory stored as a hash table) and `/archive` (linear list), and prints the **mount table**.
- Two processes, *registrar* and *finance*, open **the same file**. The trace shows that the first open searches the directory and copies the FCB into the **system-wide table**. The second open **skips the directory search** and only raises the open count to 2.
- Both processes read 15 bytes, and **both get the start of the file**, because each keeps its own offset in its **per-process table**. The program prints both tables to prove it.
- It then tries to **unmount** `/records` while finance still has the file open. This is refused with *target is busy*, and succeeds after the last close.

**Scene 3b: Wrong design.** The same test is run with the offset stored in the **shared** system-wide table instead. Finance asks for the start of the record but gets `' Amina\nProgramm'`, the middle of it, because the two processes are fighting over one offset. **What it demonstrates:** shared information (the FCB copy and the open count) belongs in the system-wide table; private information (the offset) belongs in the per-process table.

**Scene 4: Directory implementation ("the pile vs the cabinet")**
- **Small office, 10 files:** to find `wanjiru.rec`, the linear list prints every name it checks (*amina ✗ brian ✗ … wanjiru ✓*) and needs 10 comparisons. The hash table jumps to one drawer and needs 1.
- **A missing name** (`zawadi.rec`): the linear list must check all 10 entries to prove the name is absent. That is what every `create()` must do to rule out duplicates.
- **Benchmark:** 300 random lookups in directories of 100, 1,000, 10,000 and 50,000 files, comparing four designs:

| Design | Average comparisons at 50,000 files | Meaning |
|---|---|---|
| Linear list | about 25,000 | O(n): grows with the directory |
| Hash table, good function, grows when full | under 2 | O(1) on average |
| Hash table fixed at 16 buckets | about 1,600 | **Failure:** the table is too small, so chains get long |
| Hash table, bad function (first letter only) | about 25,000 | **Failure:** every name starts with "s", so everything collides in one bucket and it acts like a linear list |

- It finishes with a **trade-off table**. The linear list is simple and easy to keep sorted, but slow for big directories. The hash table is fast, but needs a good hash function and resizing, and keeps no order.

**Scene 5: Failure case, a destroyed superblock ("the ledger is torn up")**
1. It reads `esther.rec` successfully, then unmounts.
2. A "power cut" overwrites block 1 with random bytes.
3. Mount fails with *bad superblock: bad magic number*. Yet the program shows that Esther's data is **still sitting in its data block**. The data is there, but unreachable.
4. It mounts using the **backup superblock** in block 4095, rewrites the primary copy, and reads Esther's record again.
5. It destroys **both** copies, and the volume can no longer be mounted at all.

**What it demonstrates:** without the volume control block nothing on the disk can be found, which is why file systems keep backup copies.

---

## 2. `wsl_demo.sh`: the live Linux demo

### High level

The Bash script runs real Linux commands on WSL Ubuntu, to show that everything in the simulator exists in a real operating system. It works inside its own folder, `~/fs_demo`. Wherever it would be risky, it uses a **256 MB disk-image file** formatted as ext4 instead of the real disk, so nothing on the computer can be damaged. It is split into the same five parts as the scenes, pauses between steps, and prints each command before running it so the class can read it.

```bash
bash wsl_demo.sh          # all five parts
bash wsl_demo.sh 4        # one part
NO_PAUSE=1 bash wsl_demo.sh   # rehearsal       NO_SUDO=1  skip the steps that need sudo
bash wsl_demo.sh clean    # delete ~/fs_demo
```

**Setup:** it checks that the tools are installed (`e2fsprogs`, `lsof`, `xxd`). It warns if it is not running on ext4; `/mnt/c` is a Windows drive, so it must be run from `~`. It then writes the same ten student records as the simulator into `~/fs_demo/records`.

### Part by part

**Part 1: Layered structure**
- `/proc/filesystems` lists the logical file systems the kernel supports (ext4, vfat, and others).
- `findmnt` and `lsblk` show which file system (ext4) and which block device hold our folder. This is the chain from logical FS to device.
- `strace cat wanjiru.rec` shows the only things a real program asks for: `openat` with a **name**, then `read` and `close` with a **file descriptor** and **bytes**. It never mentions blocks or sectors, because the lower layers handle those.
- `stat -f` shows the block size the basic file system uses (4096 bytes).

**Part 2: On-disk structures**
- It creates a fresh ext4 volume inside `records.img` and copies the ten records into it with `debugfs`, without even mounting it.
- `xxd` shows the **boot control block** (zeros, so not bootable) and the **superblock magic number** `53 ef` (0xEF53) at byte 1080.
- `dumpe2fs` decodes the **superblock**: label, block size, block and inode counts, free blocks and features (including `dir_index`). It also lists the **backup superblock at block 32768**.
- `debugfs ls` shows the **directory**: names with their inode numbers.
- `debugfs stat` shows the **inode (FCB)** of `wanjiru.rec`: size, owner, link count, times and `EXTENTS`, the real block pointers. There is no name in it.
- A **hard link** (`ln`) gives one file two names: `ls -li` shows the **same inode number** with a link count of 2. This proves the name lives in the directory, not in the inode.

**Part 3: In-memory structures**
- `findmnt` prints the kernel's real **mount table**.
- Two background processes open `amina.rec`. Process A reads 10 bytes and process B reads nothing.
- `/proc/<pid>/fdinfo` shows A's offset is **10** and B's is **0**: real **per-process** state.
- `lsof` shows both processes pointing to **the same inode**, the shared system-wide information.
- *(with sudo)* It mounts the image, holds a file open on it, and tries to unmount. Linux refuses with **"target is busy"**, and allows it once the file is closed.

**Part 4: Directory implementation**
- It creates two directories of **1,000** and **50,000** empty files.
- `lsattr -d` shows the **`I` flag**: ext4 has turned these directories into an **htree**, its hashed directory index.
- **Timing:** it looks up the last file in each directory in two ways:
  - The **kernel's hashed lookup** takes about the **same few microseconds** for 1,000 or 50,000 files.
  - A **linear scan** (`ls -f | grep`, which reads every entry the way a linear-list directory would) **grows with the size**. It took about 0.9 ms at 1,000 files and about 14 ms at 50,000 in our test.
- *(with sudo, optional)* It builds two ext4 volumes holding the same 20,000 files, one **with** and one **without** `dir_index`. With a cold cache, looking up missing names was about **9× slower without the index**. This is the real-world version of "linear list vs hash table".

**Part 5: Failure case, a destroyed superblock**
- It builds a fresh volume, reads `esther.rec`, and notes where the backup superblock is (block 32768).
- `dd` writes random bytes over the superblock (the "power cut"), and `xxd` shows the magic number is gone.
- `dumpe2fs` reports *"Bad magic number in super-block"*. *(With sudo)* `mount` fails with *"bad superblock"*.
- `grep` still finds all ten student records in the raw image. **The data is there but unreachable.**
- `e2fsck -b 32768` rebuilds the superblock **from the backup copy**. It even corrects the free-block counts, which were out of date in the backup. Esther's record can be read again.

---

## How the two programs fit the script

| Scene in the role-play | Simulator | Linux demo | Concept |
|---|---|---|---|
| Request walks past four desks | `scene 1` | `wsl_demo.sh 1` | Layered structure |
| Registrar opens the cabinet | `scene 2` | `wsl_demo.sh 2` | On-disk structures |
| Whiteboard and sticky notes, with two class volunteers | `scene 3` (+ 3b wrong design) | `wsl_demo.sh 3` | In-memory structures |
| Clerk: pile vs drawers, stopwatch volunteer | `scene 4` / `bench` | `wsl_demo.sh 4` | Directory: linear list vs hash table |
| The ledger is torn up | `scene 5` | `wsl_demo.sh 5` | Failure: lost superblock |
