"""The files a render writes, and the scratch directories it stages them in (ports.outputs)."""
import contextlib
import os
import tempfile


def write_text(path, text, encoding="utf-8", errors="strict"):
    """Write `text` to `path`, replacing it, in text mode.

    Args:
        path: the file.
        text: its whole content.
        encoding: how it is encoded.
        errors: what an unencodable character becomes, as open() takes it.

    Returns:
        None. Writes the file, with the platform's line endings.
    """
    with open(path, "w", encoding=encoding, errors=errors) as fh:
        fh.write(text)


def scratch():
    """A fresh temporary directory, as a context manager yielding its path.

    Returns:
        tempfile.TemporaryDirectory(); it and everything in it go on exit.
    """
    return tempfile.TemporaryDirectory()


def replace(src, dst):
    """Move `src` over `dst` (os.replace).

    Returns:
        None. Moves the file.
    """
    os.replace(src, dst)


def discard(path):
    """Remove `path`; nothing when it is not there.

    Returns:
        None. Deletes the file.
    """
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)
