"""Bounded housekeeping for this app's own files; no resident cleaner."""
from pathlib import Path
import stat
import time


def cleanup_runtime(data):
    """Remove abandoned atomic-write files, never settings or user pictures."""
    data=Path(data)
    removed=[]
    if not data.exists() or data.is_symlink():return removed
    attrs=getattr(data.stat(),'st_file_attributes',0)
    if attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT:return removed
    now=time.time()
    for name in ('status.tmp','settings.tmp','window.tmp'):
        path=data/name
        try:
            info=path.lstat()
            if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
                    or getattr(info,'st_file_attributes',0)&stat.FILE_ATTRIBUTE_REPARSE_POINT
                    or now-info.st_mtime<60):continue
            path.unlink()
            removed.append(name)
        except FileNotFoundError:pass
        except OSError:pass
    return removed
