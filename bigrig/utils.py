import requests


def download_file(url: str, full_path: str) -> None:
    res = requests.get(url, stream=True)
    res.raise_for_status()
    with open(full_path, "wb") as f:
        for chunk in res.iter_content():
            f.write(chunk)
