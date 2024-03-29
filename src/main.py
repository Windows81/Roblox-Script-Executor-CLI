import interface
import argparse
import sys
import os

# Makes importing DLLs manageable.
src_dir: str = os.path.dirname(os.path.abspath(__file__))
cdir: str = os.path.dirname(src_dir)
if cdir == "":
    print(
        "Python was unable to get the main directory.  "
        + "Try looking into the codebase."
    )
    exit(1)

sys.path.append(src_dir)
sys.path.append(cdir)
os.chdir(cdir)

#from executors.oxygen import api_oxy
from api.base import api_upd
from api.executors.wearedevs import api_wrd_dll, api_wrd_exe, api_wrd_inj
from api.executors.krnl import api_krnl_exe

EXEC_TYPES = {
    "wearedevs-dll": api_wrd_dll,
    "wearedevs-inj": api_wrd_inj,
    "wearedevs-exe": api_wrd_exe,
    "krnl-exe": api_krnl_exe,
    "wearedevs": api_wrd_exe,
    "wrd-dll": api_wrd_dll,
    "wrd-inj": api_wrd_inj,
    "wrd-exe": api_wrd_exe,
    "krnl": api_krnl_exe,
    "wrd": api_wrd_exe,
    # "oxygen-u": api_oxy,
    # "oxygenu": api_oxy,
    # "oxygen": api_oxy,
    # "oxy": api_oxy,
}


def get_parse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "executor",
        type=str.lower,
        # default="krnl",
        default="wrd-exe",
        choices=list(EXEC_TYPES),
        nargs="?",
    )
    parser.add_argument("--update", action="store_true")
    return parser


if __name__ == "__main__":
    try:
        parser = get_parse()
        args = parser.parse_args().__dict__
        api_class = EXEC_TYPES[args["executor"]]
        if args["update"]:
            if issubclass(api_class, api_upd):
                api_class.update()
            else:
                print('"--update" is not valid; execution method must be updated manually.')
                exit(1)

        client = interface.client(api_class(), interface.command_mode.PREFIX)
        print("Executor has been successfully injected.")
        client.process()
    except Exception as e:
        print(e)
        exit(1)
