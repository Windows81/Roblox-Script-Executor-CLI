import win32com.client
import subprocess
import os
import re
GET_TASKS_COMMAND = '''wmic process where "commandline like '%RobloxPlayerBeta.exe%'" get commandline, processid'''


def get_running() -> tuple[int | None, str | None]:
    wmic_dump, _ = subprocess.Popen(
        GET_TASKS_COMMAND,
        stdout=subprocess.PIPE,
        encoding='utf-8',
    ).communicate()
    version_match = re.search('version-[0-9a-f]{16}', wmic_dump)
    if not version_match:
        return (None, None)
    pid_match = re.search(' *[0-9]+ *[\n\r\t]', wmic_dump[version_match.end():])
    if not pid_match:
        return (None, None)

    return (
        int(pid_match.group()),
        version_match.group(),
    )
