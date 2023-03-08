import io
import os
import clr
import time
import ctypes
import win32api
import win32con
import win32event
import api.player
import win32process
import ctypes.wintypes
from api.dump import output_dump
from typing_extensions import Self

CLEAR_ON_RUN_NAMES = [
    'rspy',
]


clr.AddReference("System.IO")  # type: ignore
import System.IO  # type: ignore

clr.AddReference("System.IO.Pipes")  # type: ignore
import System.IO.Pipes  # type: ignore

clr.AddReference("System.Net")  # type: ignore
import System.Net  # type: ignore

DEFAULT_OUTPUT = "_output.dat"


class api_base:
    __instances: dict[str, Self] = {}
    __dumps: dict[str, output_dump]
    __first_time: bool

    __output_io: io.BufferedReader | None = None
    workspace_dir: str = "workspace"
    output_path: str

    def __new__(cls, output=DEFAULT_OUTPUT) -> Self:
        '''
        Checks if a tethered to the same output file is not already used.
        If not, makes a new one.  If so, returns the one which exists.
        '''
        if output in api_base.__instances:
            return api_base.__instances[output]
        item: Self = super().__new__(cls)
        api_base.__instances[output] = item
        item.output_path = output
        item.__dumps = {}

        item.__first_time = True
        item.reset()
        item.__first_time = False
        return item

    def _setup_call(self) -> None:
        '''
        (Re)opens the output stream for console evaluation.
        '''
        path: str = os.path.join(self.workspace_dir, self.output_path)
        if self.__output_io:
            self.__output_io.close()
        with open(path, "wb") as _:
            pass
        self.__output_io = open(path, "rb")

        for name in CLEAR_ON_RUN_NAMES:
            path, dump = self.dump_get(name)
            with open(path, "wb") as _:
                dump.reset()

        # Writes code onto "workspace/output.lua" which properly outputs to our console.
        olua: str = os.path.join(self.workspace_dir, "output.lua")
        with open(olua, "w") as f:
            f.write(f"return {self.output_call('_E.ARGS[1]')}")

    def reset(self) -> None:
        if not self.should_inject():
            raise ProcessLookupError("The API wasn't able to verify a working Rōblox process.")
        self._setup_call()

    def should_inject(self) -> bool:
        pid, version = api.player.get_running()
        return bool(pid)

    def exec(self, _: str) -> None:
        raise NotImplementedError()

    def is_attached(self) -> bool:
        raise NotImplementedError()

    def output_call(self, message: str, suffix: str = "nil", pretty: bool = True) -> str:
        return f"""
        _E.EXEC('save', {repr(self.output_path)}, {message}, {'true' if pretty else 'false'}, {suffix}, true)
        """

    def output_follow(self) -> bool:
        data: bytes = bytes()
        while self.__output_io:
            data = self.__output_io.read()
            if not data:
                time.sleep(0)
                continue
            break

        tries: int = int(1e5)
        processed: bool = False
        splice: bytes
        while self.__output_io and tries > 0:
            if data:
                if data[-1] == 0:
                    splice = data[:-1]
                    tries = int(1e3)
                else:
                    splice = data
                    tries = int(2e5)
                if splice:
                    ps = splice.decode("utf-8")
                    print(ps, end="")
                    processed = True
            else:
                tries -= 1
            time.sleep(0)
            data = self.__output_io.read()
        return processed

    def dump_path(self, name: str) -> str:
        if self.output_path == DEFAULT_OUTPUT:
            return os.path.join(self.workspace_dir, f"_{name}.dat")
        dir_n = os.path.dirname(self.output_path)
        bse_n = os.path.basename(self.output_path)
        return os.path.join(dir_n, f"{bse_n}_{name}.dat")

    def dump_get(self, name: str) -> tuple[str, output_dump]:
        path = self.dump_path(name)
        return path, self.__dumps.setdefault(path, output_dump(path))

    # https://github.com/dabeaz/generators/blob/master/examples/follow.py
    def dump_follow(self, name: str, print=print) -> bool:
        path, dump = self.dump_get(name)
        data = bytes()
        done = False
        while dump:
            data = dump.file_thread.read()
            if not data:
                break
            done = True
            ps = data.decode("utf-8")
            print(ps, end="")
        print("", end="\n" if done else "")
        return done

    def dump_reset(self, name: str) -> int:
        path = self.dump_path(name)
        if path in self.__dumps:
            return self.__dumps[path].reset()
        self.__dumps[path] = output_dump(path)
        return 0

    def __del__(self) -> None:
        if self.__output_io:
            self.__output_io.close()


class api_ver(api_base):
    '''APIs which only work for a particular version of Rōblox's client.'''
    RBLX_VERSION: str

    def should_inject(self) -> bool:
        pid, version = api.player.get_running()
        return version == self.RBLX_VERSION


class api_inj(api_base):
    '''APIs which support connecting to named pipes.'''
    PIPE_NAME: str

    def _setup_call(self) -> None:
        pipe_args = [".", self.PIPE_NAME, System.IO.Pipes.PipeDirection.Out]
        while True:
            try:
                pipe = System.IO.Pipes.NamedPipeClientStream(*pipe_args)
                pipe.Connect(100)
                pipe.Dispose()
                break
            except System.TimeoutException:
                continue
        super()._setup_call()

    def _write_pipe(self, body: str) -> None:
        try:
            pipe_args = [
                ".",
                self.PIPE_NAME,
                System.IO.Pipes.PipeDirection.Out
            ]
            pipe = System.IO.Pipes.NamedPipeClientStream(*pipe_args)
            pipe.Connect(666)

            writer_args = [pipe]
            writer = System.IO.StreamWriter(*writer_args)
            writer.Write(body)
            writer.Dispose()
            pipe.Dispose()
        except System.TimeoutException:
            raise ConnectionError("Fatal: unable to connect to pipe.")

    def exec(self, script: str) -> None:
        self._write_pipe(script)

    # https://github.com/penghwee-sng/penetration-testing-snippets/blob/2d3ed6ee547657c3dc36951bf186dea9a3950af7/dll/dll_injector.py
    def _inject(self, path: str) -> None:
        path_b: bytes = bytes(os.path.abspath(path), "ascii")
        proc_id, _ = api.player.get_running()

        if not proc_id:
            raise ProcessLookupError()

        process_handle = win32api.OpenProcess(
            win32con.PROCESS_ALL_ACCESS, False, proc_id
        )
        memory_address = win32process.VirtualAllocEx(
            process_handle,
            0,
            len(path_b),
            win32con.MEM_COMMIT | win32con.MEM_RESERVE,
            win32con.PAGE_READWRITE,
        )

        k32 = ctypes.windll.kernel32
        bytes_written = ctypes.c_int(0)
        k32.WriteProcessMemory(
            int(process_handle),
            memory_address,
            path_b,
            len(path_b),
            ctypes.byref(bytes_written),
        )

        k32_handle = win32api.GetModuleHandle("kernel32.dll")
        load_library_a_address = win32api.GetProcAddress(
            k32_handle, b"LoadLibraryA")  # type: ignore
        remote_data = win32process.CreateRemoteThread(
            process_handle, None, 0, load_library_a_address, memory_address, 0  # type: ignore
        )

        event_state = win32event.WaitForSingleObjectEx(
            remote_data[0], 60 * 1000, False)
        if event_state == win32event.WAIT_TIMEOUT:
            print("Injected DllMain thread timed out.")


class api_upd(api_base):
    FILE_PATH: str

    def _load(self) -> bytes | None:
        if os.path.isfile(self.FILE_PATH):
            with open(self.FILE_PATH, "rb") as f:
                return f.read()
        else:
            self.update()

    @staticmethod
    def update():
        raise NotImplementedError()
