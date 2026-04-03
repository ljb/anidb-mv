from amv.file_info import FileInfo


def create_file_info(path, id_=None):
    return FileInfo(
        id=id_,
        view_date=1532983833.2112887,
        internal=True,
        watched=True,
        path=path,
        size=1337,
        ed2k="1" * 32,
    )
