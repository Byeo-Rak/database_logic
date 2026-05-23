#!/usr/bin/env python3
"""
호환용 래퍼: 전체 업로드는 scripts/upload_to_firebase.py로 통합되었습니다.
"""
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [sys.executable, "scripts/upload_to_firebase.py", "--all-default-targets", *sys.argv[1:]]
    result = subprocess.run(cmd, check=False)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
