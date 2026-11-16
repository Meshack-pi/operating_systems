#!/usr/bin/env python3
"""fs_sim.py - teaching simulator for "Implementing a File System" (OSC 10e, Ch. 14).

  python3 fs_sim.py              all scenes (Enter = next step)
  python3 fs_sim.py scene N      1 layers, 2 on-disk, 3 in-memory, 4 directory, 5 superblock failure
  python3 fs_sim.py bench        linear list vs hash table benchmark
  add --no-pause to run straight through

Superblock, boot block and file data are real bytes in simulated blocks; inodes and
directory entries are Python objects stored at real block locations, so every lookup
performs the block reads a real disk would.
"""
import math, random, struct, sys, time, zlib

BS, NBLK = 1024, 4096                         # 1 KB blocks, 4 MB volume
SB, BACKUP, ITABLE, DIRBLK, DATA = 1, NBLK - 1, 3, 131, 163
SBFMT = struct.Struct("<4sIIII16s")           # magic, block size, blocks, inodes, free blocks, label
MAGIC = b"OSFS"
PAUSE = "--no-pause" not in sys.argv
COLOR = sys.stdout.isatty()
TRACE = False


# ---------------------------------------------------------------- output helpers
def col(code, t): return f"\033[{code}m{t}\033[0m" if COLOR else str(t)
def step(t): print("\n" + col(33, ">> ") + col(1, t))
def ok(t): print(col(32, "   OK  ") + t)
def bad(t): print(col(31, "   !!  ") + t)
def note(t): print(col(2, "   " + t))


def banner(title, concept):
    line = col(36, "=" * 72)
    print(f"\n{line}\n {col(1, title)}\n {col(2, 'Concept: ' + concept)}\n{line}")


def pause():
    if PAUSE:
        try: input(col(2, "   [Enter] "))
        except EOFError: print()


def table(hdr, rows):
    rows = [[str(x) for x in r] for r in rows]
    w = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(hdr)]
    fmt = "   " + " | ".join(f"{{:<{x}}}" for x in w)
    print(col(1, fmt.format(*hdr)) + "\n   " + "-+-".join("-" * x for x in w))
    for r in rows: print(fmt.format(*r))


LAYERS = {"app": (0, 35, "APPLICATION"), "lfs": (1, 34, "LOGICAL FILE SYSTEM"),
          "fom": (2, 36, "FILE-ORGANISATION MODULE"), "bfs": (3, 32, "BASIC FILE SYSTEM"),
          "ioc": (4, 33, "I/O CONTROL"), "dev": (5, 31, "DEVICE")}


def log(layer, msg):
    if TRACE:
        depth, c, name = LAYERS[layer]
        print("   " + "  " * depth + col(c, f"[{name}]") + " " + msg)


# ---------------------------------------------------------------- directories
class Linear:
    label = "Linear list"
    def __init__(s): s.e = []
    def insert(s, name, ino): s.e.append((name, ino))
    def names(s): return [n for n, _ in s.e]

    def lookup(s, name, walk=None):              # -> (inode, comparisons, bucket)
        for i, (n, ino) in enumerate(s.e):
            if walk is not None: walk.append(n)
            if n == name: return ino, i + 1, None
        return None, len(s.e), None


def fnv(name):                                     # good hash: FNV-1a
    h = 0x811C9DC5
    for b in name.encode(): h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def first_letter(name): return ord(name[0])        # BAD hash: first character only


class Hash:
    def __init__(s, size=16, fn=fnv, grow=True):
        s.b, s.fn, s.grow, s.n = [[] for _ in range(size)], fn, grow, 0
        s.label = f"Hash table ({fn.__name__}, " + ("auto-resize)" if grow else f"fixed {size})")

    def insert(s, name, ino):
        s.b[s.fn(name) % len(s.b)].append((name, ino))
        s.n += 1
        if s.grow and s.n > 2 * len(s.b):          # keep load factor <= 2
            old, s.b, s.n = [e for c in s.b for e in c], [[] for _ in range(2 * len(s.b))], 0
            for e in old: s.insert(*e)

    def names(s): return [n for c in s.b for n, _ in c]

    def lookup(s, name, walk=None):
        k = s.fn(name) % len(s.b)
        for i, (n, ino) in enumerate(s.b[k]):
            if walk is not None: walk.append(n)
            if n == name: return ino, i + 1, k
        return None, len(s.b[k]), k


# ---------------------------------------------------------------- one volume, four layers
class Volume:
    def __init__(s, dev, directory, label="RECORDS"):
        s.dev, s.dir, s.label = dev, directory, label
        s.blocks = [bytearray(BS) for _ in range(NBLK)]
        s.used, s.inodes, s.cache, s.reads, s.mounted = set(range(DATA)) | {BACKUP}, {}, {}, 0, False
        s.blocks[0][:48] = b"BOOT: no operating system on this volume".ljust(48, b"\0")
        s.blocks[SB][:SBFMT.size + 4] = s.blocks[BACKUP][:SBFMT.size + 4] = s.superblock()

    # I/O control: device driver
    def driver_read(s, n):
        log("ioc", f"driver {s.dev}: READ sectors {2 * n}-{2 * n + 1} -> controller")
        log("dev", f"disk transfers block {n}, raises interrupt")
        s.reads += 1
        return bytes(s.blocks[n])

    # basic file system: generic block I/O + buffer cache
    def bread(s, n, why):
        if n in s.cache:
            log("bfs", f"block {n} ({why}): found in buffer cache - no disk I/O")
        else:
            log("bfs", f"block {n} ({why}): not cached -> ask I/O control")
            s.cache[n] = s.driver_read(n)
        return s.cache[n]

    # file-organisation module: logical -> physical blocks, free space
    def phys(s, ino, lblock):
        p = s.inodes[ino]["blocks"][lblock]
        log("fom", f"file block {lblock} of inode {ino} -> physical block {p}")
        return p

    def alloc(s):
        b = next(b for b in range(DATA, NBLK) if b not in s.used)
        s.used.add(b)
        return b

    # logical file system: superblock, directory, FCBs
    def superblock(s):
        body = SBFMT.pack(MAGIC, BS, NBLK, 1024, NBLK - len(s.used), s.label.encode())
        return body + struct.pack("<I", zlib.crc32(body))

    def mount(s, block=SB):
        s.cache.clear()
        raw = s.bread(block, "superblock")
        if raw[:4] != MAGIC: raise OSError(f"bad magic number {raw[:4]!r} (expected {MAGIC!r})")
        if zlib.crc32(raw[:SBFMT.size]) != struct.unpack_from("<I", raw, SBFMT.size)[0]:
            raise OSError("superblock checksum mismatch")
        if block != SB:                                     # repair primary from backup
            s.blocks[SB][:SBFMT.size + 4] = s.superblock()
        s.mounted = True
        return dict(zip(["magic", "block size", "total blocks", "inodes", "free blocks", "label"],
                        [v.rstrip(b"\0").decode() if isinstance(v, bytes) else v
                         for v in SBFMT.unpack(raw[:SBFMT.size])]))

    def search(s, name):
        log("lfs", f'search directory ({s.dir.label}) for "{name}"')
        ino, comps, k = s.dir.lookup(name)
        if k is not None: log("lfs", f'hash("{name}") mod {len(s.dir.b)} = bucket {k}')
        for i in range(max(1, math.ceil(comps / 32))):      # 32 entries per directory block
            s.bread(DIRBLK + ((k or 0) + i) % 32, "directory")
        log("lfs", f"{comps} comparison(s) -> " + (f"found, inode {ino}" if ino else "not found"))
        return ino

    def create(s, name, data):
        ino = 11 + len(s.inodes)
        blk = s.alloc()
        s.blocks[blk][:len(data)] = data
        s.inodes[ino] = dict(size=len(data), blocks=[blk], owner="registrar",
                             perms="rw-r--r--", links=1, mtime=time.time())
        s.dir.insert(name, ino)

    def read(s, ino, off, n):
        end, out = min(off + n, s.inodes[ino]["size"]), b""
        while off < end:
            data = s.bread(s.phys(ino, off // BS), "file data")
            take = min(end - off, BS - off % BS)
            out, off = out + data[off % BS: off % BS + take], off + take
        return out


# ---------------------------------------------------------------- in-memory structures
class Kernel:
    def __init__(k, shared_offset=False):
        k.mounts, k.sys, k.procs, k.names, k.shared = {}, [], {}, {}, shared_offset

    def mount(k, vol, mp, backup=False):
        vol.mount(BACKUP if backup else SB)
        k.mounts[mp] = vol

    def umount(k, mp):
        if any(e and e["vol"] is k.mounts[mp] for e in k.sys):
            raise OSError(f"umount {mp}: target is busy (files still open)")
        k.mounts.pop(mp).mounted = False

    def open(k, pid, path):
        mp, name = path.rsplit("/", 1)
        vol = k.mounts[mp]
        log("app", f'{k.names[pid]} (pid {pid}) calls open("{path}")')
        log("lfs", f"mount table: {mp} is {vol.dev}")
        idx = next((i for i, e in enumerate(k.sys) if e and e["vol"] is vol and e["name"] == name), None)
        if idx is None:
            ino = vol.search(name)
            if not ino: raise OSError(f"{path}: no such file")
            vol.bread(ITABLE + (ino - 1) // 8, f"inode table, FCB {ino}")
            k.sys.append(dict(vol=vol, name=name, ino=ino, count=1, off=0))
            idx = len(k.sys) - 1
            log("lfs", f"FCB {ino} copied into system-wide open-file table, index {idx}")
        else:
            k.sys[idx]["count"] += 1
            log("lfs", f"already in system-wide table (index {idx}) -> NO directory search, "
                       f"open count now {k.sys[idx]['count']}")
        fds = k.procs.setdefault(pid, {})
        fd = max(fds, default=2) + 1
        fds[fd] = dict(sys=idx, off=0)
        log("lfs", f"per-process table of pid {pid}: fd {fd} -> system-wide index {idx}")
        return fd

    def read(k, pid, fd, n):
        pe = k.procs[pid][fd]
        se = k.sys[pe["sys"]]
        holder = se if k.shared else pe                      # where the offset lives
        log("app", f"{k.names[pid]} (pid {pid}) calls read(fd={fd}, {n} bytes)")
        log("lfs", f"fd {fd} -> system-wide index {pe['sys']} (inode {se['ino']}); offset "
                   f"{holder['off']} from " + ("SHARED system-wide entry" if k.shared else "own entry"))
        data = se["vol"].read(se["ino"], holder["off"], n)
        holder["off"] += len(data)
        return data

    def close(k, pid, fd):
        pe = k.procs[pid].pop(fd)
        se = k.sys[pe["sys"]]
        se["count"] -= 1
        if se["count"] == 0: k.sys[pe["sys"]] = None

    def show(k):
        print(col(1, "   System-wide open-file table (one row per open file)"))
        table(["index", "file", "inode", "open count"] + (["offset (WRONG place)"] if k.shared else []),
              [[i, e["name"], e["ino"], e["count"]] + ([e["off"]] if k.shared else [])
               for i, e in enumerate(k.sys) if e] or [["-"] * (5 if k.shared else 4)])
        for pid, fds in k.procs.items():
            print(col(1, f"\n   Per-process open-file table: {k.names[pid]} (pid {pid})"))
            table(["fd", "-> system index", "offset"],
                  [[fd, pe["sys"], "(shared)" if k.shared else pe["off"]] for fd, pe in fds.items()]
                  or [["-", "-", "-"]])


# ---------------------------------------------------------------- sample data
FILES = ["amina", "brian", "chebet", "david", "esther", "faith", "george", "halima", "ian", "wanjiru"]


def record(name):
    return (f"STUDENT RECORD: {name.capitalize()}\nProgramme: BSc Computer Science\n"
            f"Units: OS, Networks, Databases\nStatus: in good standing\n").encode()


def office(directory=None, dev="/dev/sim0", label="RECORDS"):
    vol = Volume(dev, directory or Hash(), label)
    for f in FILES: vol.create(f + ".rec", record(f))
    return vol


def students(n): return [f"student_{r}.rec" for r in random.Random(7).sample(range(100000, 999999), n)]


def traced(fn):
    global TRACE
    TRACE = True
    try: return fn()
    finally: TRACE = False


# ---------------------------------------------------------------- scenes
def scene1():
    banner("SCENE 1 - A request travels through the layers",
           "Layered structure: logical FS, file-organisation module, basic FS, I/O control")
    k = Kernel()
    k.names[100] = "registrar_app"
    vol = office()
    k.mount(vol, "/records")
    step('open("/records/wanjiru.rec")')
    fd = traced(lambda: k.open(100, "/records/wanjiru.rec"))
    pause()
    step("read 40 bytes - first time, the block must come from disk")
    print("   data: " + col(32, repr(traced(lambda: k.read(100, fd, 40)).decode())))
    pause()
    step("read the same bytes again - the basic FS has the block in its cache")
    k.procs[100][fd]["off"], before = 0, vol.reads
    traced(lambda: k.read(100, fd, 40))
    ok(f"disk reads during this call: {vol.reads - before} (buffer cache hit)")
    note("Each layer does one job; one I/O-control driver serves every file system.")
    pause()


def scene2():
    banner("SCENE 2 - What is actually written on the disk",
           "On-disk structures: boot control block, volume control block, directory, FCB/inode")
    vol = office()
    step("Disk map (first 256 of 4096 blocks)")
    m = "".join("B" if b == 0 else "S" if b == SB else "M" if b == 2 else "I" if b < DIRBLK
                else "D" if b < DATA else "#" if b in vol.used else "." for b in range(256))
    for i in range(0, 256, 64): print("   " + m[i:i + 64])
    note(f"B boot  S superblock  M free-space bitmap  I inode table  D directory  # data  "
         f"(backup superblock: block {BACKUP})")
    pause()
    step("Block 0 - boot control block")
    print("   " + repr(bytes(vol.blocks[0]).rstrip(b"\0")))
    step("Block 1 - volume control block (superblock), decoded from raw bytes")
    print("   raw: " + col(2, bytes(vol.blocks[SB][:24]).hex(" ") + " ..."))
    table(["field", "value"], vol.mount().items())
    note("The magic number identifies the file-system type; mount refuses the volume without it.")
    pause()
    step("Directory - maps file NAMES to inode NUMBERS")
    table(["name", "inode"], sorted(((n, vol.dir.lookup(n)[0]) for n in vol.dir.names()), key=lambda r: r[1]))
    pause()
    step('FCB (inode) of "wanjiru.rec" - everything about the file EXCEPT its name')
    ino = vol.dir.lookup("wanjiru.rec")[0]
    i = vol.inodes[ino]
    table(["field", "value"], [["inode", ino], ["owner", i["owner"]], ["permissions", i["perms"]],
                               ["size", i["size"]], ["links", i["links"]], ["data blocks", i["blocks"]],
                               ["stored in block", ITABLE + (ino - 1) // 8]])
    print(f"   block {i['blocks'][0]}: " + col(32, repr(bytes(vol.blocks[i['blocks'][0]][:40]))))
    pause()


def two_readers(k, fa, fb):
    a, b = k.read(201, fa, 15), k.read(202, fb, 15)
    print(f"   registrar got: {col(32, repr(a.decode()))}\n"
          f"   finance   got: {col(31 if k.shared else 32, repr(b.decode()))}")


def office_kernel(shared=False):
    k = Kernel(shared_offset=shared)
    k.names.update({201: "registrar", 202: "finance"})
    k.mount(office(), "/records")
    return k


def scene3():
    banner("SCENE 3 - What the kernel keeps in memory",
           "In-memory structures: mount table, system-wide & per-process open-file tables")
    k = office_kernel()
    k.mount(office(Linear(), "/dev/sim1", "ARCHIVE"), "/archive")
    step("Mount table")
    table(["mount point", "device", "directory", "label"],
          [[mp, v.dev, v.dir.label, v.label] for mp, v in k.mounts.items()])
    pause()
    step("Two processes open the SAME file")
    fa, fb = traced(lambda: (k.open(201, "/records/amina.rec"), print(), k.open(202, "/records/amina.rec")))[::2]
    pause()
    step("registrar reads 15 bytes, then finance reads 15 bytes")
    two_readers(k, fa, fb)
    ok("both start at byte 0 - each process keeps its OWN offset")
    k.show()
    pause()
    step("unmount /records while finance still has the file open")
    k.close(201, fa)
    try: k.umount("/records")
    except OSError as e: bad(str(e))
    k.close(202, fb)
    k.umount("/records")
    ok("after the last close, unmount succeeds")
    pause()
    banner("SCENE 3b - WRONG DESIGN: offset kept in the system-wide table",
           "What goes wrong without per-process state")
    k = office_kernel(shared=True)
    two_readers(k, k.open(201, "/records/amina.rec"), k.open(202, "/records/amina.rec"))
    bad("finance asked for the start of the record but got the MIDDLE - one shared offset")
    k.show()
    note("Shared (FCB copy, open count) -> system-wide.  Private (offset, mode) -> per-process.")
    pause()


def show_walk(d, name):
    walk = []
    ino, comps, k = d.lookup(name, walk)
    trail = " ".join(col(32, w + " OK") if w == name else col(31, w.split(".")[0] + " x") for w in walk)
    print(f"   {d.label:<34}" + (col(2, f" drawer {k}: ") if k is not None else " ") + (trail or "(empty)"))
    print(f"   {'':<34} {col(1, comps)} comparison(s)" + ("" if ino else col(31, "  NOT FOUND")))


def bench(sizes=(100, 1000, 10000, 50000), lookups=300):
    kinds = [("Linear list", Linear), ("Hash, good fn, auto-resize", lambda: Hash()),
             ("Hash, too small (16 fixed)", lambda: Hash(16, grow=False)),
             ("Hash, bad fn (1st letter)", lambda: Hash(1024, first_letter, grow=False))]
    rows, last = [], {}
    for n in sizes:
        names = students(n)
        targets = random.Random(11).choices(names, k=lookups)
        for label, make in kinds:
            d = make()
            for i, nm in enumerate(names): d.insert(nm, i)
            t0 = time.perf_counter()
            avg = sum(d.lookup(t)[1] for t in targets) / lookups
            us = (time.perf_counter() - t0) / lookups * 1e6
            last[label] = avg
            rows.append([f"{n:,}", label, f"{avg:,.1f}", f"{d.lookup('student_000000.rec')[1]:,}", f"{us:,.1f}"])
    table(["files", "approach", "avg compares", "compares to CREATE (miss)", "us/lookup"], rows)
    print(col(1, f"\n   Average comparisons per lookup, {sizes[-1]:,} files"))
    top = max(last.values())
    for label, v in last.items():
        print(f"   {label:<28} {col(31 if v > top / 5 else 32, '#' * max(1, round(v / top * 46)))} {v:,.1f}")


def scene4():
    banner("SCENE 4 - Finding a name: linear list vs hash table", "Directory implementation and trade-offs")
    lin, hsh = Linear(), Hash(16, grow=False)
    for i, f in enumerate(FILES): lin.insert(f + ".rec", i); hsh.insert(f + ".rec", i)
    step("Small office (10 files): find wanjiru.rec")
    show_walk(lin, "wanjiru.rec"); show_walk(hsh, "wanjiru.rec")
    step("Find a file that does NOT exist (every create() must do this to check duplicates)")
    show_walk(lin, "zawadi.rec"); show_walk(hsh, "zawadi.rec")
    pause()
    step("Scale up: 300 random lookups at each directory size")
    bench()
    pause()
    step("Why do the two bad hash tables fail? (2,000 files)")
    for d in (Hash(1024, first_letter, grow=False), Hash(16, grow=False), Hash()):
        for i, nm in enumerate(students(2000)): d.insert(nm, i)
        chains = [len(c) for c in d.b]
        (ok if max(chains) < 10 else bad)(f"{d.label}: {len(d.b)} buckets, longest chain {max(chains)}, "
                                          f"{chains.count(0)} empty")
    note("bad fn: every name starts with 's' -> one bucket = a linear list again (collisions)")
    pause()
    step("Trade-off summary")
    table(["", "Linear list", "Hash table"], [
        ["lookup", "O(n) scan", "O(1) average"],
        ["create", "O(n) duplicate check", "O(1) average"],
        ["sorted listing", "easy if kept sorted", "no order - must sort"],
        ["complexity", "simple, compact", "table, chains, resizing"],
        ["risk", "slow for big directories", "collisions, bad size, bad hash"]])
    note("ext4 uses a hashed tree (htree) - see wsl_demo.sh part 4.")
    pause()


def scene5():
    banner("SCENE 5 - Failure case: the superblock is destroyed",
           "On-disk structures: why the volume control block is critical")
    k = Kernel()
    k.names[1] = "registrar"
    vol = office()
    k.mount(vol, "/records")
    fd = k.open(1, "/records/esther.rec")
    print("   before: " + col(32, repr(k.read(1, fd, 30).decode())))
    k.close(1, fd)
    k.umount("/records")
    step("Power cut while writing block 1: the superblock becomes garbage")
    vol.blocks[SB][:] = random.Random(5).randbytes(BS)
    print("   block 1: " + col(31, bytes(vol.blocks[SB][:16]).hex(" ")) + " ...")
    pause()
    step("mount /dev/sim0 /records")
    try: k.mount(vol, "/records")
    except OSError as e: bad(f"mount: wrong fs type, bad superblock on /dev/sim0: {e}")
    blk = vol.inodes[vol.dir.lookup("esther.rec")[0]]["blocks"][0]
    note(f"yet the data is still on the disk, block {blk}: {bytes(vol.blocks[blk][:30])!r}")
    pause()
    step(f"Recovery: mount using the BACKUP superblock (block {BACKUP}) - like e2fsck -b")
    k.mount(vol, "/records", backup=True)
    fd = k.open(1, "/records/esther.rec")
    ok("mounted from backup, primary rewritten: " + repr(k.read(1, fd, 30).decode()))
    k.close(1, fd)
    k.umount("/records")
    pause()
    step("Worst case: primary AND backup destroyed")
    vol.blocks[SB][:] = vol.blocks[BACKUP][:] = bytes(BS)
    for backup in (False, True):
        try: k.mount(vol, "/records", backup)
        except OSError as e: bad(("backup " if backup else "primary ") + str(e))
    bad("the volume cannot be mounted at all - why file systems keep several copies")


SCENES = {1: scene1, 2: scene2, 3: scene3, 4: scene4, 5: scene5}

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--no-color" in sys.argv: COLOR = False
    if args[:1] == ["bench"]: bench()
    elif args[:1] == ["scene"] and len(args) > 1 and int(args[1]) in SCENES: SCENES[int(args[1])]()
    elif not args: [SCENES[n]() for n in SCENES]
    else: print(__doc__)
