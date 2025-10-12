from time import perf_counter
from pathlib import Path


def logger(func):
    def wrapper(*args, **kwargs):
        path = Path(args[1])
        path = path.parts[-1]
        start = perf_counter()
        print(f'Uploading {str(path)}....')
        result = func(*args, **kwargs)
        end = perf_counter()
        if result:
            print(f'Uploaded in {round(end - start, 2)} seconds\n')
        return result

    return wrapper
