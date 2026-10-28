"""Portable project file snapshots in PostgreSQL. Never writes source files."""
import hashlib
import json
import os
import sqlite3
import stat
import tempfile
import time
import uuid
from pathlib import Path, PurePosixPath
from backend.datacenter_lib import sqlite_consistent_snapshot

CHUNK_SIZE = 1024 * 1024
# Only rebuildable developer artifacts are omitted; user_data is never filtered.
EXCLUDED_DIRS = {'.git', '.worktrees', 'node_modules', '__pycache__', '.venv', 'venv', '.pytest_cache'}
DDL = [
    'CREATE SCHEMA IF NOT EXISTS archive',
    '''CREATE TABLE IF NOT EXISTS archive.runs (
        id text PRIMARY KEY, started_at timestamptz DEFAULT now(), finished_at timestamptz,
        state text NOT NULL, files bigint DEFAULT 0, bytes bigint DEFAULT 0, source_roots jsonb,
        error text)''',
    '''CREATE TABLE IF NOT EXISTS archive.chunks (
        sha256 text PRIMARY KEY, content bytea NOT NULL,
        CHECK (sha256 = encode(sha256(content), 'hex')))''',
    '''CREATE TABLE IF NOT EXISTS archive.entries (
        run_id text REFERENCES archive.runs(id), path text, kind text, size bigint,
        sha256 text, chunks jsonb NOT NULL, mode integer, mtime_ns bigint, link_target text,
        PRIMARY KEY (run_id,path))''',
]


def inventory(root):
    """Include files, empty directories and links; never follow symlinks."""
    root = Path(root)
    def walk(directory, relative):
        for path in sorted(directory.iterdir()):
            rel = relative / path.name
            under_user = rel.parts[0] == 'user_data'
            if not under_user and (path.name in EXCLUDED_DIRS or
                    (len(rel.parts) == 2 and rel.parts[0] == 'ai-office-assistant-web' and
                     (path.name == 'dist' or path.name.startswith('dist.bak')))):
                continue
            # PID files and sockets are not portable data. SQLite sidecars handled by backup API.
            if path.name in ('app.pid',) or path.name.endswith(('-wal', '-shm', '-journal')):
                continue
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                yield path, rel, 'symlink', info
            elif stat.S_ISDIR(info.st_mode):
                yield path, rel, 'directory', info
                yield from walk(path, rel)
            elif stat.S_ISREG(info.st_mode):
                yield path, rel, 'file', info
            else:
                raise ValueError(f'Unsupported special file: {rel}')
    yield from walk(root, Path())


def safe_destination(root, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or any(p in ('..', '') for p in path.parts):
        raise ValueError('Unsafe archive path')
    target = Path(root).joinpath(*path.parts)
    if not target.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('Archive path escapes restore directory')
    return target


def store_file(conn, path, known_chunks):
    """Retry changing files; publish an entry only after a stable read."""
    for attempt in range(3):
        before = path.stat()
        digest = hashlib.sha256()
        chunks, size = [], 0
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(CHUNK_SIZE), b''):
                digest.update(block)
                key = hashlib.sha256(block).hexdigest()
                if key not in known_chunks:
                    conn.run('INSERT INTO archive.chunks (sha256, content) VALUES (:h,:b) ON CONFLICT DO NOTHING', h=key,b=block)
                    known_chunks.add(key)
                chunks.append(key)
                size += len(block)
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns):
            return size, digest.hexdigest(), chunks
    raise RuntimeError('Source kept changing during snapshot')


def snapshot_project(conn, roots, heartbeat=None):
    for statement in DDL:
        conn.run(statement)
    run_id = uuid.uuid4().hex
    conn.run("INSERT INTO archive.runs (id,state,source_roots) VALUES (:id,'running',:roots::jsonb)",
             id=run_id, roots=json.dumps({key:str(value) for key,value in roots.items()}))
    known = {r[0] for r in conn.run('SELECT sha256 FROM archive.chunks')}
    count, total, entries, sqlite_count = 0, 0, 0, 0
    last_beat = 0
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for label, root in roots.items():
                if not Path(root).is_dir():
                    raise ValueError('Configured source root is missing')
                for path, relative, kind, info in inventory(root):
                    size, digest, chunks, link = 0, None, [], None
                    if kind == 'file':
                        with path.open('rb') as stream:
                            is_sqlite = stream.read(16) == b'SQLite format 3\x00'
                        source = path
                        if is_sqlite:
                            source = Path(tmp) / 'snapshot.db'
                            source.unlink(missing_ok=True)
                            sqlite_consistent_snapshot(path, source)
                            sqlite_count += 1
                        size, digest, chunks = store_file(conn, source, known)
                        count += 1
                        total += size
                    elif kind == 'symlink':
                        link = os.readlink(path)
                    conn.run('''INSERT INTO archive.entries
                        (run_id,path,kind,size,sha256,chunks,mode,mtime_ns,link_target)
                        VALUES (:r,:p,:k,:s,:h,:c::jsonb,:m,:t,:l)''',
                        r=run_id,p=str(Path(label)/relative),k=kind,s=size,h=digest,c=json.dumps(chunks),
                        m=stat.S_IMODE(info.st_mode),t=info.st_mtime_ns,l=link)
                    entries += 1
                    if heartbeat and time.monotonic()-last_beat > 15:
                        heartbeat()
                        last_beat = time.monotonic()
        # Verify stored bytes independently before advertising the snapshot as complete.
        bad = conn.run("SELECT count(*) FROM archive.chunks WHERE sha256 <> encode(sha256(content),'hex')")[0][0]
        if bad:
            raise RuntimeError('Stored chunk checksum mismatch')
        conn.run("UPDATE archive.runs SET state='complete',finished_at=now(),files=:f,bytes=:b WHERE id=:id",
                 f=count,b=total,id=run_id)
        return {'id':run_id,'ok':True,'files':count,'entries':entries,'bytes':total,'sqlite_snapshots':sqlite_count,
                'excluded':sorted(EXCLUDED_DIRS)+['frontend build outputs','SQLite sidecars','app.pid']}
    except Exception as exc:
        conn.run("UPDATE archive.runs SET state='failed',finished_at=now(),error=:e WHERE id=:id",
                 e=type(exc).__name__,id=run_id)
        raise


def restore_project(conn, target, run_id=None):
    """Restore only into a new directory; refuse escapes and preserve file modes."""
    target = Path(target)
    if target.exists():
        raise FileExistsError('Restore destination must not exist')
    result = conn.run("SELECT id FROM archive.runs WHERE state='complete' " +
                      ('AND id=:id ' if run_id else '') + 'ORDER BY finished_at DESC LIMIT 1',
                      **({'id':run_id} if run_id else {}))
    if not result:
        raise ValueError('No complete archive')
    run_id = result[0][0]
    target.mkdir(parents=True, mode=0o700)
    entries = conn.run('SELECT path,kind,size,sha256,chunks,mode,mtime_ns,link_target FROM archive.entries WHERE run_id=:id ORDER BY path', id=run_id)
    directories, links, files, total = [], [], 0, 0
    try:
        for relative, kind, size, digest, chunks, mode, mtime, link in entries:
            dest = safe_destination(target, relative)
            dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if kind == 'directory':
                dest.mkdir(exist_ok=True,mode=0o700)
                directories.append((dest,mode,mtime))
            elif kind == 'symlink':
                # Recreate links last; refuse absolute links or links leaving the restored tree.
                if Path(link).is_absolute() or not (dest.parent/link).resolve().is_relative_to(target.resolve()):
                    raise ValueError('Unsafe symbolic link in archive')
                links.append((dest,link))
            elif kind == 'file':
                actual = hashlib.sha256()
                with dest.open('xb') as out:
                    os.chmod(dest,0o600)
                    for key in chunks:
                        block = conn.run('SELECT content FROM archive.chunks WHERE sha256=:h',h=key)[0][0]
                        if hashlib.sha256(block).hexdigest() != key:
                            raise ValueError('Chunk checksum mismatch')
                        out.write(block);actual.update(block)
                if dest.stat().st_size != size or actual.hexdigest() != digest:
                    raise ValueError('File checksum mismatch')
                os.chmod(dest,mode & 0o777)
                os.utime(dest,ns=(mtime,mtime))
                files += 1; total += size
            else:
                raise ValueError('Unknown entry kind')
        for dest, link in links:
            dest.symlink_to(link)
        for dest,mode,mtime in reversed(directories):
            os.chmod(dest,mode & 0o777);os.utime(dest,ns=(mtime,mtime))
    except Exception:
        # Never mark a partially restored directory as usable.
        (target/'RESTORE_FAILED').write_text('Restore failed. Do not use this directory.\n')
        raise
    return {'run_id':run_id,'files':files,'bytes':total,'checksums':'pass'}
