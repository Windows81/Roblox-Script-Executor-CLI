import os, sys
from executors.krnl import api_krnl_exe

# Makes importing DLLs manageable.
cdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if cdir == "":
    print(
        "Python was unable to get the main directory.  "
        + "Try looking into the codebase."
    )
    exit(1)

sys.path.append(cdir)
os.chdir(cdir)
from executors.wearedevs import api_wrd_dll, api_wrd_exe, api_wrd_inj
from executors.base import api_base, api_upd
from executors.oxygen import api_oxy
from proc import process
import argparse

EXEC_TYPES: dict[str : type[api_base]] = {
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
    "oxygen-u": api_oxy,
    "oxygenu": api_oxy,
    "oxygen": api_oxy,
    "oxy": api_oxy,
}


def get_parse():
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
    parser = get_parse()
    args = parser.parse_args().__dict__
    api_class = EXEC_TYPES[args["executor"]]
    if args["update"]:
        if issubclass(api_class, api_upd):
            api_class.update()
        else:
            print("Execution method must be updated manually.")

    try:
        api = api_class()
        print("Executor has been successfully injected.")
        process(api)
    except ConnectionError as e:
        print(e)
