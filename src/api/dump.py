from io import BufferedReader


class output_dump:
    file_thread: BufferedReader
    output_path: str

    def __init__(self, path: str) -> None:
        self.file_thread = open(path, "rb")
        self.output_path = path

    def reset(self) -> int:
        pos = self.file_thread.tell()
        self.file_thread.seek(0)
        return pos

    def __del__(self) -> None:
        self.file_thread.close()

    def follow(self) -> bool:
        data = bytes()
        done = False
        while self:
            data = self.file_thread.read()
            if not data:
                break
            done = True
            ps = data.decode("utf-8")
            print(ps, end="")
        print("", end="\n" if done else "")
        return done
