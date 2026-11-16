# Scenario Simulation Script: "The Records Office"

**Project:** Operating Systems Group Project: File and I/O Management
**Topic 8:** Implementing a File System (Brief 4.5)
**Format:** Idea C (mixed): role-play with props, plus a live WSL Ubuntu demo and the `fs_sim.py` simulator
**Length:** 10 minutes (inside the 30-minute slot: 15 teaching, **10 simulation**, 5 questions)
**Reference:** Silberschatz, Galvin & Gagne, *Operating System Concepts*, 10th ed., Chapter 14
https://os.ecci.ucr.ac.cr/slides/Abraham-Silberschatz-Operating-System-Concepts-10th-2018.pdf

---

## 1. The scenario in one paragraph

The university **Records Office** is our disk volume. The **filing cabinet** is the disk. The **ledger on the door** is the superblock. The **folder cover sheets** are the FCBs/inodes. The **index the clerk searches** is the directory. A student's request for a record passes through four desks; those are the four **layers**. While records are being used, the office keeps a **whiteboard** of folders currently out (the **system-wide open-file table**). Each staff member keeps a **sticky note** of where they are in a folder (the **per-process open-file table**). We first act each idea out, then show the same structure **for real on Linux** and **measured in the simulator**.

## 2. Cast

| Member | Role in the simulation | Concept they link aloud |
|---|---|---|
| **Meshack Kiprono** | Narrator, and at the laptop (WSL + simulator) | Introduction and all live demos |
| **Gathingu Tatyana** | The *Request Runner* who walks the request through the four desks; also the timekeeper | Layered structure |
| **Mwangi Emmah** | The *Registrar* who owns the cabinet, the ledger and the folder cover sheets | On-disk structures |
| **MUSIMWA Caroline-Berly** | The *Front-Office Manager* who keeps the whiteboard (open files); runs the props | In-memory structures |
| **Naima** | The *Clerk* who finds names, first in a pile and then in a drawer cabinet | Directory: linear list vs hash table |
| **2 volunteers from the class** | *Process A (Registry staff)* and *Process B (Finance staff)* | Per-process tables |
| **1 volunteer from the class** | *Stopwatch* | Measuring the trade-off |

## 3. Props (Caroline prepares)

1. **4 desk signs (A4):** `LOGICAL FILE SYSTEM`, `FILE-ORGANISATION MODULE`, `BASIC FILE SYSTEM`, `I/O CONTROL`.
2. **Request slip:** `open("/records/wanjiru.rec")  then  read()`.
3. **Ledger card (superblock):** "Volume RECORDS · magic number OSFS · 4096 blocks of 1 KB · 1024 inodes · inode table starts at block 3 · free blocks 3922". Make **two copies**, and write **BACKUP** on the second.
4. **Boot card:** "Boot control block: no OS on this volume".
5. **One folder cover sheet (FCB)** for Wanjiru: inode 20, owner registrar, rw-r--r--, size 112 bytes, data block 172, dates. It has **no name** on it.
6. **20 name cards** (table below), each with a name and a registration number.
7. **10 envelopes labelled 0 to 9** (the "cabinet drawers"), plus **1 envelope labelled "2"** for the bad-hash round.
8. **Whiteboard or flipchart** with a grid: `index | file | inode | open count`.
9. **2 sticky notes** headed `fd | → whiteboard row | offset`.
10. A phone stopwatch.

**The 20 cards.** Keep the pile in this order. Wanjiru is **last** on purpose. Hash rule: **drawer = last digit of the registration number.**

| # | Name | Reg. no. | Drawer |
|---|---|---|---|
| 1 | Amina | 2024-0311 | 1 |
| 2 | Brian | 2024-0127 | 7 |
| 3 | Chebet | 2024-0452 | 2 |
| 4 | David | 2024-0198 | 8 |
| 5 | Esther | 2024-0263 | 3 |
| 6 | Faith | 2024-0335 | 5 |
| 7 | George | 2024-0414 | 4 |
| 8 | Halima | 2024-0206 | 6 |
| 9 | Ian | 2024-0380 | 0 |
| 10 | Juma | 2024-0149 | 9 |
| 11 | Kamau | 2024-0221 | 1 |
| 12 | Lilian | 2024-0357 | 7 |
| 13 | Mercy | 2024-0092 | 2 |
| 14 | Njeri | 2024-0473 | 3 |
| 15 | Otieno | 2024-0165 | 5 |
| 16 | Purity | 2024-0284 | 4 |
| 17 | Rashid | 2024-0306 | 6 |
| 18 | Salma | 2024-0440 | 0 |
| 19 | Tom | 2024-0118 | 8 |
| 20 | Wanjiru | 2024-0459 | 9 |

Before the session, fill the cabinet so that each drawer holds 2 cards. Keep a second set of the 20 cards as the loose pile.

## 4. Laptop setup (Meshack, at least 10 minutes before)

```bash
cd ~                                   # Linux home folder, NOT /mnt/c
cp /mnt/c/Users/<you>/Desktop/OS_GROP/demo/* ~/   # or wherever the files are
NO_PAUSE=1 bash wsl_demo.sh 4 >/dev/null   # builds the 1,000- and 50,000-file folders in advance
sudo -v                                # cache the sudo password so no prompt appears mid-demo
```

Open **two terminal tabs**. Tab 1 is for `wsl_demo.sh`; Tab 2 is for `python3 fs_sim.py`. Make the font large (at least 18 pt). Each `bash wsl_demo.sh N` waits for Enter between steps, so the narrator controls the pace.

---

## 5. The script (timed)

> Stage directions are in *italics*. **[CONCEPT]** marks the moment the speaker must link the step aloud to the concept. This is required by the marking checklist.

### Opening (0:00 to 0:45) · Meshack

*All five stand at their "desks". The four desk signs are in a row and the cabinet is on a table.*

**Meshack:** "Welcome to the University Records Office. Thousands of student records live here, and people ask for them all day. For the next ten minutes this office **is a file system**. The cabinet is the disk, these four desks are the layers of the file system, and the whiteboard is the kernel's memory. Every time we act something out, we will show you the real thing on Linux. Let's start with a simple request."

### Scene 1: Layered structure (0:45 to 2:15) · Tatyana, Meshack

*Tatyana picks up the request slip `open("/records/wanjiru.rec") then read()`.*

**Tatyana:** "I'm a program, and I've asked for Wanjiru's record. I only know a **name**. I don't know where it is on the disk, and I don't care. Watch where my request goes."

*Tatyana walks to each desk and reads its sign aloud.*

**Tatyana (at LOGICAL FILE SYSTEM):** "Desk one turns the **name** into a **file**. It searches the directory, finds the folder's cover sheet, and checks that I'm allowed to read it. **[CONCEPT]** This is the **logical file system**. It manages metadata, never the data itself."

**Tatyana (at FILE-ORGANISATION MODULE):** "Desk two knows the file is stored in block 172. It translates *the first block of this file* into *physical block 172*. It also keeps track of free space. **[CONCEPT] File-organisation module.**"

**Tatyana (at BASIC FILE SYSTEM):** "Desk three just says 'fetch block 172'. It first checks its **buffer cache**, in case we already have a copy on the desk. **[CONCEPT] Basic file system.**"

**Tatyana (at I/O CONTROL):** "Desk four is the only one that speaks the hardware's language: 'controller, read sectors 344 to 345'. **[CONCEPT] I/O control**: the device driver and the interrupt handler."

**Meshack (Tab 2):** `python3 fs_sim.py scene 1`. *Press Enter twice.*
"This is the same request in our simulator. Each coloured line is one layer, indented one level deeper. Watch the **second read**: the basic file system finds the block in its cache, so I/O control is never called. That is why we have layers: each one does one job, and one disk driver serves every file system."

> *Optional if time allows:* Tab 1, `bash wsl_demo.sh 1`, the strace step. The real `cat` command only ever asks for a name, a file descriptor and bytes.

### Scene 2: On-disk structures (2:15 to 3:30) · Emmah, Meshack

*Emmah opens the cabinet and holds up each prop in turn.*

**Emmah:** "Everything that must **survive a power cut** is kept in the cabinet, on the disk."
- *(boot card)* "In block zero we have the **boot control block**. If an OS were installed here, the code to start it would be in this block. Ours is empty."
- *(ledger card)* "In block one we have the **volume control block**, which Linux calls the **superblock**. It records how many blocks there are, how big they are, how many are free, and where the inode table starts. **[CONCEPT]** Without this ledger, nobody can make sense of the cabinet."
- *(cover sheet)* "This is the **file control block**, or **inode**. It holds the owner, permissions, size, dates and which blocks hold the data. Look carefully: **it does not contain the file name.**"
- *(name cards)* "The names live in the **directory**, which maps each name to an inode number. **[CONCEPT]** Directory plus FCB: the directory gives you the number, and the FCB gives you everything else."

**Meshack (Tab 1):** `bash wsl_demo.sh 2`. *Press Enter through these steps:* `xxd` (magic `53 ef`), `dumpe2fs`, then `debugfs stat /wanjiru.rec`.
"This is a real ext4 volume. At byte 1080 is the magic number EF53, and this is the superblock decoded. Here is the real inode: size, times and EXTENTS, which are the block pointers. Again, no name."

### Scene 3: In-memory structures (3:30 to 5:15) · Caroline, volunteers, Meshack

*Caroline invites two volunteers: **Process A (Registry)** and **Process B (Finance)**. Each gets a sticky note.*

**Caroline:** "The cabinet is slow, so when the office is open we keep **working copies in memory**. First, the sign on the door says 'Cabinet RECORDS is attached at /records'. **[CONCEPT]** That's the **mount table**."

**Caroline:** "Process A, please open Amina's record." *(Naima finds Amina's card; Caroline writes on the whiteboard: `0 | amina.rec | inode 11 | open count 1`. A writes on their sticky note: `fd 3 → row 0 | offset 0`.)*
"This whiteboard is the **system-wide open-file table**: one row per open file, holding a copy of the FCB. The sticky note is the **per-process open-file table**. **[CONCEPT]**"

**Caroline:** "Process B, open the same record." *(Caroline changes the count to 2 and does **not** call the clerk.)*
"Notice that we didn't search the directory again. The file was already on the whiteboard, so we just raised the open count to 2."

**Caroline:** "A, read 15 characters." *(A changes their offset to 15.)* "B, read 15 characters. Where does B start?"
*(Ask the class.)* "**At zero!** Each process keeps its own offset on its own sticky note."

**Meshack (Tab 1):** `bash wsl_demo.sh 3`. *Press Enter to the fdinfo step, then lsof.*
"These are two real Linux processes holding the same file. In `/proc/<pid>/fdinfo`, A's position is 10 and B's is 0. `lsof` shows both pointing to **the same inode**." *(If sudo is ready, show the step:)* "And I can't unmount a volume while a process still has a file open on it: `target is busy`."

**What goes wrong.** **Caroline:** "Now suppose we were lazy and stored the offset **on the whiteboard**, shared by everyone."
**Meshack (Tab 2):** `python3 fs_sim.py scene 3`. *Skip ahead to Scene 3b.*
"Finance asked for the start of the record and got `' Amina\nProgramm'`, the middle of it. The two processes are fighting over one offset. **[CONCEPT]** Shared information goes in the system-wide table; private information goes in the per-process table."

### Scene 4: Directory implementation, linear list vs hash table (5:15 to 8:15) · Naima, Stopwatch volunteer, Meshack

*Naima stands at the table with the loose pile and the cabinet of envelopes. A volunteer holds the stopwatch.*

**Naima:** "I'm the clerk. My whole job is to turn a name into an inode number. There are two ways I can store the names."

**Round 1: Linear list (the pile).**
**Naima:** "Class, which student should I find?" *(Steer them towards **Wanjiru**, or just announce: "let's try Wanjiru".)* "Stopwatch, go."
*Naima turns cards one by one, counting aloud: "Amina, no. Brian, no. ..." up to "Wanjiru, yes, twenty."*
**Naima:** "Twenty comparisons. **[CONCEPT]** That's a **linear list**: simple, but every lookup scans the entries, so it is **O(n)**. Even worse, to **create** a new file I have to scan the **whole** pile first to make sure the name isn't already taken."

**Round 2: Hash table (the cabinet).**
**Naima:** "Same student. The registration number ends in 9, so I go to drawer 9." *(Opens drawer 9: "Juma, no. Wanjiru, yes.")* "Two comparisons. Stopwatch?" *(The volunteer reads out both times.)*
"**[CONCEPT]** That's a **hash table**. The hash function sends me straight to the right drawer, so a lookup takes about the same time however many files there are: **O(1) on average**."

**Round 3: What goes wrong with a bad hash.**
**Naima:** "Suppose I had chosen a bad hash function: the **first digit of the year**." *(Pours all 20 cards into the single envelope labelled 2.)* "Every student registered in 2024, so every card lands in drawer 2. That's a **collision** for every name, and we're back to a linear search." *(Hold up an empty envelope.)* "If the table is **too small**, say only two drawers, each chain gets long. A good hash table needs a good hash function **and** must be resized as it grows."

**Meshack (Tab 2):** `python3 fs_sim.py bench` (or press Enter through `scene 4`).
"Twenty cards doesn't seem like much, so here are 50,000. The linear list needs about **25,000 comparisons per lookup**. A good hash table needs fewer than **2**. The too-small table needs about 1,600, and the bad hash function is exactly as bad as the linear list."

**Meshack (Tab 1):** `bash wsl_demo.sh 4`, from the `lsattr` step.
"Real Linux uses the hash idea. The **`I` flag** means ext4 has indexed this directory with a hashed tree called the **htree**. Looking up the last of 50,000 files takes the same few microseconds as with 1,000 files. Scanning the directory entry by entry, the linear way, takes thousands of times longer, and gets slower as the directory grows." *(If sudo is ready and time allows, show the optional step: the same files on ext4 with `dir_index` turned off, about 9× slower.)*

**Naima (trade-off, 20 seconds):** "So is the hash table always better? Not quite. A linear list is simpler, uses less space, and can easily be kept in sorted order for `ls`. A hash table needs a good hash function and resizing, and it has no natural order. Small directories are fine with a list. Large ones need a hash, which is why ext4 only switches on the index once a directory grows beyond one block."

### Scene 5: Failure case, a lost superblock (8:15 to 9:30) · Emmah, Meshack

**Emmah:** *(tears up or scribbles over the ledger card)* "Power cut! The ledger was being updated when the power failed, and now it's garbage."
"Every folder is still in the cabinet, but nobody knows how big the blocks are or where the inode table starts. **[CONCEPT]** Without the volume control block, the volume **cannot be mounted**."

**Meshack (Tab 1):** `bash wsl_demo.sh 5`.
"I overwrite the real superblock with random bytes, and the magic number is gone. `dumpe2fs` says *Bad magic number*, and `mount` says *bad superblock*. Yet `grep` still finds all 10 student records in the raw disk. **The data is there but unreachable.**"

**Emmah:** *(holds up the BACKUP ledger)* "Which is why the file system keeps **backup copies** of the superblock in other block groups."
**Meshack:** "`e2fsck -b 32768` rebuilds the superblock from the backup. It even fixes the free-block counts, because the backup was slightly out of date. The volume mounts, and Esther's record is back."

### Wrap-up (9:30 to 10:00) · Tatyana

**Tatyana:** "In ten minutes you've seen the four ideas of file-system implementation:"

| What you saw | Concept |
|---|---|
| The request walking past four desks | **Layered structure** |
| The ledger, boot card, cover sheet and name index in the cabinet | **On-disk structures** |
| The door sign, the whiteboard and the sticky notes | **In-memory structures** |
| The pile vs the cabinet, and the overflowing drawer | **Directory implementation: linear list vs hash table** |

"And you've seen what breaks when an idea is missing or chosen badly: a shared offset, a slow linear directory, a bad hash function, and a lost superblock. Thank you. We'll take your questions now."

---

## 6. Timing summary and cuts if we run late

| Segment | Start | Length | Lead | If behind schedule, cut |
|---|---|---|---|---|
| Opening | 0:00 | 0:45 | Meshack | |
| 1 Layers | 0:45 | 1:30 | Tatyana | the optional strace step |
| 2 On-disk | 2:15 | 1:15 | Emmah | the `xxd` step; show only `debugfs stat` |
| 3 In-memory | 3:30 | 1:45 | Caroline | the unmount-busy step |
| 4 Directory | 5:15 | 3:00 | Naima | Round 3 props (keep the screen); the optional dir_index step |
| 5 Superblock | 8:15 | 1:15 | Emmah | the `grep` step |
| Wrap-up | 9:30 | 0:30 | Tatyana | never cut |

Tatyana gives a hand signal at **5:15** (Scene 4 must be starting) and at **8:15** (Scene 5 must be starting).

## 7. Backup plan

- **WSL fails or the projector cannot show it:** every scene has a simulator version. Run `python3 fs_sim.py` (full guided demo, Enter = next step) or `python3 fs_sim.py scene N`. It needs only Python 3 and runs on Windows, macOS or Linux.
- **Sudo password problem:** run `NO_SUDO=1 bash wsl_demo.sh N`. Every required step works without sudo; only the optional extras are skipped.
- **Running out of time:** go straight to the wrap-up table. It covers all four concepts in 30 seconds.

## 8. Requirement checklist (from the brief)

- [x] **Original and realistic:** a records-office scenario, a real ext4 volume, and real `/proc` open-file tables.
- [x] **Compares at least two approaches:** linear list vs hash table, shown with props, the simulator and Linux ext4 (indexed vs scanned, and optionally `dir_index` on vs off).
- [x] **Shows what goes wrong:** slow linear search at scale, a bad hash function and an undersized table, a shared offset (no per-process table), unmounting while busy, and a corrupted superblock.
- [x] **All four concepts appear as clear steps**, each with a spoken **[CONCEPT]** link.
- [x] **The class takes part:** two volunteer processes, a volunteer with the stopwatch, and the class picks the name and predicts B's offset.
- [x] **Everyone has a speaking part.**
- [x] **Fits in 10 minutes:** timed plan with cut list.

## 9. Likely questions (everyone should be ready)

1. **Why doesn't the inode store the file name?** So that one file can have several names (hard links: `ln`, as shown in WSL part 2), and so that renaming a file only changes the directory.
2. **Why not always use a hash table?** It costs more memory and complexity, needs resizing, and has no sorted order. For small directories a list is just as fast. ext4 indexes a directory only after it outgrows one block.
3. **What happens on a hash collision?** The colliding entries are chained in the same bucket. Lookup checks the chain, so many collisions turn the table back into a linear list. That is Round 3.
4. **Why have both a system-wide and a per-process open-file table?** Shared state (the FCB copy and the open count) is kept once; private state (the offset and the access mode) is kept per process. Scene 3b shows what happens otherwise.
5. **Why can't you unmount a busy volume?** Open-file table entries point into it. Unmounting would leave dangling references, and data still in the cache could be lost.
6. **How does Linux survive a corrupted superblock?** It keeps backup superblocks in other block groups (`dumpe2fs` lists them). `e2fsck -b <backup>` rebuilds the primary, and journaling reduces the chance of a half-written update in the first place.
7. **Where is each layer in Linux?** The VFS and ext4 code form the logical FS and the file-organisation module. The block layer and page cache form the basic FS. The SCSI/virtio/NVMe drivers are I/O control.
