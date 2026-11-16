#!/usr/bin/env bash
# wsl_demo.sh - live WSL Ubuntu demo for "Implementing a File System" (OSC 10e, Ch. 14)
#   bash wsl_demo.sh [all|1|2|3|4|5|clean]     parts: 1 layers, 2 on-disk, 3 in-memory,
#                                                4 directory (linear vs hash), 5 superblock failure
#   NO_PAUSE=1  run without pauses       NO_SUDO=1  skip the optional sudo steps
# Needs: sudo apt install -y e2fsprogs lsof strace.  Run from ~ (ext4), not /mnt/c.
# Everything happens in ~/fs_demo; the superblock is only corrupted in an image FILE.
set -u
D="${DEMO_DIR:-$HOME/fs_demo}"; IMG="$D/records.img"; MNT="$D/mnt"
if [ -t 1 ]; then B=$'\e[1m' DIM=$'\e[2m' R=$'\e[31m' G=$'\e[32m' Y=$'\e[33m' C=$'\e[36m' N=$'\e[0m'
else B= DIM= R= G= Y= C= N=; fi
LINE="$C========================================================================$N"

banner() { printf '\n%s\n %s%s%s\n %sConcept: %s%s\n%s\n' "$LINE" "$B" "$1" "$N" "$DIM" "$2" "$N" "$LINE"; }
say()    { echo; echo "$Y>> $N$B$*$N"; }
note()   { echo "$DIM   $*$N"; }
good()   { echo "$G   OK  $N$*"; }
bad()    { echo "$R   !!  $N$*"; }
pause()  { [ "${NO_PAUSE:-0}" = 1 ] || read -r -p "$DIM   [Enter]$N " _ </dev/tty; }
run()    { echo "$G\$ $1$N"; bash -c "$1"; }          # show a command, then run it
ns()     { date +%s%N; }
sudo_ok() { [ "${NO_SUDO:-0}" != 1 ] && command -v sudo >/dev/null && sudo -v; }

setup() {
  for t in mkfs.ext4 dumpe2fs debugfs e2fsck lsof findmnt lsattr xxd; do
    command -v "$t" >/dev/null || { bad "missing $t: sudo apt install -y e2fsprogs lsof xxd"; exit 1; }
  done
  mkdir -p "$D/records"
  [ "$(findmnt -n -o FSTYPE -T "$D")" = ext4 ] || bad "$D is not on ext4 - run from your Linux home (cd ~)"
  for n in amina brian chebet david esther faith george halima ian wanjiru; do
    printf 'STUDENT RECORD: %s\nProgramme: BSc Computer Science\nStatus: in good standing\n' "${n^}" > "$D/records/$n.rec"
  done
}

new_image() {   # fresh 256 MB ext4 volume in a file, filled with the records via debugfs (no mount)
  rm -f "$IMG"; truncate -s 256M "$IMG"; mkfs.ext4 -q -F -b 4096 -L RECORDS "$IMG"
  for f in "$D"/records/*.rec; do echo "write $f $(basename "$f")"; done > "$D/cmds"
  debugfs -w -f "$D/cmds" "$IMG" >/dev/null 2>&1
}

part1() {
  banner "PART 1 - The layers a read() passes through" "Layered structure"
  say "Logical file systems this kernel knows"
  run "grep -v nodev /proc/filesystems"
  say "Which file system and device hold our folder"
  run "findmnt -T $D -o TARGET,SOURCE,FSTYPE; lsblk -o NAME,SIZE,TYPE"
  note "ext4 = logical FS + file-organisation module; block layer = basic FS; disk driver = I/O control"
  pause
  if command -v strace >/dev/null; then
    say "What the application asks for: names, file descriptors and bytes - never blocks"
    run "strace -e trace=openat,read,close cat $D/records/wanjiru.rec 2>&1 >/dev/null | grep -A3 wanjiru.rec"
  fi
  run "stat -f -c 'block size used by the basic file system: %S bytes' $D"
  pause
}

part2() {
  banner "PART 2 - What ext4 writes on the disk" "On-disk structures: boot block, superblock, directory, inode"
  say "A fresh 256 MB volume inside a file"
  new_image; run "ls -lhs $IMG"
  say "Boot control block (first 1024 bytes) and the superblock magic number at byte 1080"
  run "xxd -l 32 $IMG; xxd -s 1080 -l 2 $IMG"
  note "zeros = not bootable;  53 ef = 0xEF53, the ext2/3/4 magic number"
  pause
  say "The superblock decoded, and its backup copies"
  run "dumpe2fs -h $IMG 2>/dev/null | grep -E 'volume name|magic|Block count|Block size|Inode count|Free blocks|features'"
  run "dumpe2fs $IMG 2>/dev/null | grep -i 'superblock at'"
  pause
  say "The directory: name -> inode number"
  run "debugfs -R 'ls -l /' $IMG 2>/dev/null"
  say "The inode (FCB): everything except the name"
  run "debugfs -R 'stat /wanjiru.rec' $IMG 2>/dev/null | grep -E 'Inode:|User:|Links:|mtime|EXTENTS|^\\('"
  pause
  say "Same thing on the live system: two names, ONE inode (hard link)"
  run "ln -f $D/records/wanjiru.rec $D/records/copy.rec; ls -li $D/records/wanjiru.rec $D/records/copy.rec; rm $D/records/copy.rec"
  pause
}

part3() {
  banner "PART 3 - What the kernel keeps in memory" "Mount table, system-wide and per-process open-file tables"
  local F="$D/records/amina.rec" A P Q
  say "The mount table"
  run "findmnt -o TARGET,SOURCE,FSTYPE | head -15"
  pause
  say "Two processes open the SAME file; A reads 10 bytes, B reads nothing"
  ( exec 3<"$F"; dd bs=1 count=10 <&3 >/dev/null 2>&1; exec sleep 120 ) & A=$!
  ( exec 3<"$F"; exec sleep 120 ) & P=$!
  sleep 0.5
  run "for p in $A $P; do echo \"pid \$p: \$(readlink /proc/\$p/fd/3)  \$(grep pos /proc/\$p/fdinfo/3)\"; done"
  note "same file, different offsets -> the offset is PER-PROCESS state"
  run "lsof $F"
  note "both entries point to the same inode (NODE column) - shared, system-wide information"
  pause
  if sudo_ok; then
    say "Unmount a volume while a file on it is open"
    [ -f "$IMG" ] || new_image; mkdir -p "$MNT"
    sudo mount -o loop "$IMG" "$MNT"
    ( exec 3<"$MNT/amina.rec"; exec sleep 120 ) & Q=$!
    sleep 0.5
    run "sudo umount $MNT"
    bad "busy: an open-file table entry still points into this volume"
    kill $Q; wait $Q 2>/dev/null
    run "sudo umount $MNT && echo unmounted after the file was closed"
  fi
  kill $A $P 2>/dev/null; wait $A $P 2>/dev/null
  pause
}

timeit() {      # $1 = command run in a loop $2 times; prints microseconds per run
  local t0 i; t0=$(ns); for ((i = 0; i < $2; i++)); do eval "$1"; done; echo $(( ($(ns) - t0) / $2 / 1000 ))
}

part4() {
  banner "PART 4 - Finding one name among thousands" "Directory implementation: linear list vs hash table"
  local n f k img m
  for n in 1000 50000; do
    [ -d "$D/dir_$n" ] || { mkdir "$D/dir_$n"; (cd "$D/dir_$n" && seq -f 'student_%06g.rec' 1 $n | xargs touch); }
  done
  say "Two directories: 1,000 and 50,000 files. Are they hash-indexed?"
  run "lsattr -d $D/dir_1000 $D/dir_50000"
  note "flag I = Indexed directory: ext4's htree, a hash of name -> directory block"
  pause
  say "Look up the LAST file: kernel lookup (hash index) vs reading every entry (linear list)"
  for n in 1000 50000; do
    f=$(printf 'student_%06d.rec' $n)
    echo "   $n files:  hashed ${G}$(timeit "[ -e $D/dir_$n/$f ]" 2000) us${N}   linear scan ${R}$(timeit "ls -f $D/dir_$n | grep -qxF $f" 20) us${N}"
  done
  good "hash index: same time when the directory grows 50x"
  bad  "linear scan: time grows with the number of files (O(n))"
  if sudo_ok; then
    pause
    say "Optional: 20,000 files on ext4 WITH and WITHOUT the directory index (dir_index)"
    for k in hash linear; do
      img="$D/$k.img" m="$D/mnt_$k"; mkdir -p "$m"; sudo umount "$m" 2>/dev/null
      rm -f "$img"; truncate -s 128M "$img"
      if [ $k = linear ]; then mkfs.ext4 -q -F -O ^dir_index "$img"; else mkfs.ext4 -q -F "$img"; fi
      sudo mount -o loop "$img" "$m"; sudo mkdir "$m/d"
      (cd "$m/d" && seq -f 'student_%06g.rec' 1 20000 | sudo xargs touch)
    done
    run "lsattr -d $D/mnt_hash/d $D/mnt_linear/d"
    for k in hash linear; do
      sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null      # start with a cold cache
      echo "   $k: 200 lookups of MISSING names: $(( $(timeit "[ -e $D/mnt_$k/d/nosuch_\$i ]" 200) * 200 )) us"
      sudo umount "$D/mnt_$k"
    done
    note "a missing name is the worst case - and every create() must check for one"
  fi
  pause
}

part5() {
  banner "PART 5 - Failure case: destroy the superblock" "Without the volume control block the volume cannot be mounted"
  local BK
  new_image
  BK=$(dumpe2fs "$IMG" 2>/dev/null | grep -m1 -o 'Backup superblock at [0-9]*' | awk '{print $4}')
  run "debugfs -R 'cat /esther.rec' $IMG 2>/dev/null"
  echo "   backup superblock at block $B$BK$N"
  pause
  say "'Power cut': overwrite the superblock with random bytes"
  run "dd if=/dev/urandom of=$IMG bs=1024 seek=1 count=1 conv=notrunc status=none; xxd -s 1080 -l 2 $IMG"
  say "Try to use the volume"
  run "dumpe2fs -h $IMG 2>&1 | sed -n 2,3p"
  if sudo_ok; then mkdir -p "$MNT"; run "sudo mount -o loop $IMG $MNT"; fi
  run "grep -c 'STUDENT RECORD' $IMG"
  bad "cannot mount - yet the records are still physically on the disk"
  pause
  say "Recovery from the backup superblock"
  run "e2fsck -f -y -b $BK -B 4096 $IMG; echo \"exit code \$? (1 = errors fixed)\""
  run "debugfs -R 'cat /esther.rec' $IMG 2>/dev/null"
  good "repaired from the backup - this is why ext4 keeps several copies"
  pause
}

case "${1:-all}" in
  all)   setup; for p in 1 2 3 4 5; do "part$p"; done ;;
  [1-5]) setup; "part$1" ;;
  clean) for m in "$MNT" "$D"/mnt_*; do mountpoint -q "$m" 2>/dev/null && sudo umount "$m"; done
         rm -rf "$D"; good "removed $D" ;;
  *)     sed -n 2,7p "$0" ;;
esac
