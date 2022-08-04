import os

# Makes importing DLLs manageable.
cdir = os.path.dirname(__file__)
if cdir != "":
    os.chdir(cdir)

from executors.wearedevs import api_wrd_dll, api_wrd_exe, api_wrd_inj
from executors.base import api_base, api_upd
from logic.processor import exec_processor
from executors.oxygen import api_oxy
import argparse

EXEC_TYPES: dict[str : type[api_base]] = {
    "wearedevs-dll": api_wrd_dll,
    "wearedevs-inj": api_wrd_inj,
    "wearedevs-exe": api_wrd_exe,
    "wearedevs": api_wrd_exe,
    "wrd-dll": api_wrd_dll,
    "wrd-inj": api_wrd_inj,
    "wrd-exe": api_wrd_exe,
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

    api = api_class()
    print("Executor has been successfully injected.")
    in_obj = exec_processor(api)
    while True:
        in_obj.process()
