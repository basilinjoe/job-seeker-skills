"""The MCP server's session: which workspace it serves, and the loaded record its reads share.

Ruling 15 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: the
workspace is the session's - `JSK_ROOT` when set, else the one around the directory the
server started in (find_root). A server started outside any workspace looks again on each
call, so `jsk kb new` run after it started is found without a restart.

Ruling 14: no long-lived lock, and no long-lived store. A write tool takes the writers'
turn per call, inside the compose function it calls, exactly as the CLI does; nothing here
holds the turn or the store open between calls. Reads share one loaded Store, kept while
the record on disk has not moved. Loading a workspace is seconds; a session's agent reads
it dozens of times between writes.

What "has not moved" means: the ruling asked for the log revision, read with one read-only
open per call. tests/test_db.py lets only infra/oxigraph/db.py and record.py open the store,
and application graphs carry no revision anyway, so the key is read off the disk instead -
every file in career/store/ by name, size and mtime, and .jsk/backup.trig, which every write
replaces (record.write_graphs). Any write, from this server or a CLI in another shell,
changes RocksDB's files (a new table, a grown log, a new manifest). The counter the server
bumps on its own writes is kept beside it as the ruling asked, so a write of ours that the
filesystem's clock cannot tell apart from the one before still reloads.
"""
import datetime
import os

# The variable that names the workspace, ahead of the directory the server started in.
ROOT_ENV = "JSK_ROOT"


def today():
    """The day, read from the clock. Ruling 17: the server calls this once per tool call and
    passes the day down, as adapters/cli/options.py does for a command; nothing below reads
    the clock, and a test patches this one function."""
    return datetime.date.today()


class Session:
    """One server's workspace and its read cache.

    Args:
        root: the workspace, or None to find it (JSK_ROOT, then find_root(os.getcwd())).
        load: root -> a loaded Store (compose.record.load); a test may count its calls.
    """

    def __init__(self, root=None, load=None):
        from ...infra.files import find_root

        self.start = os.getcwd()
        given = root or os.environ.get(ROOT_ENV) or None
        self.fixed = given is not None
        self.root = os.path.abspath(given) if given else find_root(self.start)
        if load is None:
            from ..cli.compose.record import load
        self.load_fresh = load
        self.writes = 0
        self.cached = None              # (key, Store)
        self.loads = 0                  # how many loads the cache made, for its tests

    def workspace(self):
        """The workspace root, looked for again when none was found at the start."""
        if self.root is None and not self.fixed:
            from ...infra.files import find_root

            self.root = find_root(self.start)
        return self.root

    def served(self):
        """The workspace root, which a read only asks for once server.Tools.call found one.

        Raises:
            LookupError: there is none - a call that skipped that check, a server bug.
        """
        root = self.workspace()
        if root is None:
            raise LookupError("the session has no workspace")
        return root

    def key(self):
        """What says the record on disk is the one cached: the store's files by name, size
        and mtime, the backup's, and this server's own write count."""
        from ...infra.oxigraph import db

        root = self.served()
        stats = []
        store = db.path(root)
        try:
            names = sorted(os.listdir(store))
        except OSError:
            names = []
        for name in names:
            try:
                st = os.stat(os.path.join(store, name))
            except OSError:
                continue                # a file RocksDB removed between list and stat
            stats.append((name, st.st_size, st.st_mtime_ns))
        try:
            st = os.stat(os.path.join(root, ".jsk", "backup.trig"))
            stats.append(("backup", st.st_size, st.st_mtime_ns))
        except OSError:
            pass
        return (root, self.writes, tuple(stats))

    def store(self):
        """The loaded record, from the cache while the disk has not moved."""
        key = self.key()
        if self.cached is None or self.cached[0] != key:
            self.cached = (key, self.load_fresh(self.served()))
            self.loads += 1
        return self.cached[1]

    def load(self, root, vocabulary=None, files=None, graphs=None):
        """compose.record.load's shape, served from the cache when it is a plain read of
        this workspace; anything else - a candidate, other files - is loaded fresh."""
        if graphs is None and files is None and vocabulary is None and \
                os.path.normcase(os.path.abspath(root)) == \
                os.path.normcase(os.path.abspath(self.served())):
            return self.store()
        kw = {k: v for k, v in (("vocabulary", vocabulary), ("files", files),
                                ("graphs", graphs)) if v is not None}
        return self.load_fresh(root, **kw)

    def wrote(self):
        """Note a write this server made, so the next read reloads."""
        self.writes += 1
        self.cached = None

    def ports(self):
        """compose.native.Ports whose plain loads come from the cache: for the reads only."""
        from ..cli.compose.native import Ports

        session = self

        class Cached(Ports):
            def load(self, root, graphs=None):
                return session.load(root, graphs=graphs)

        return Cached()
