#!/usr/bin/env python3
import json
import hashlib
from pathlib import Path
import requests
import threading
from decouple import config
import xmltodict
from concurrent.futures import ThreadPoolExecutor

sitemap_index_url = "https://www.costes-viager.com/sitemap.xml"
save_dir = Path("sitemaps")

HEADERS = {
    "Host": "www.costes-viager.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.63 Safari/537.36",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "*/*",
    "Connection": "close",
}

PROXY_SERVER = config("PROXY_SERVER", default=None)
PROXIES = {"http": PROXY_SERVER, "https": PROXY_SERVER}
json_locker = threading.Lock()


def hash_file(filepath):
    """Calcule le hash SHA256 d'un fichier."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def compare_and_download_sitemap(url, save_path):
    """Compare et télécharge le sitemap si différent, puis extrait les nouvelles URLs."""
    new_sitemap_path = save_path.parent / (save_path.stem + "_new" + save_path.suffix)
    download_sitemap(url, new_sitemap_path)

    if save_path.exists() and hash_file(save_path) == hash_file(new_sitemap_path):
        print("Le sitemap n'a pas changé.")
        new_sitemap_path.unlink()
    else:
        print("Le sitemap a changé. Mise à jour en cours.")
        extract_new_urls(save_path, new_sitemap_path)
        new_sitemap_path.rename(save_path)


def extract_new_urls(old_sitemap_path, new_sitemap_path):
    """Extrait et sauvegarde les nouvelles URLs."""
    old_urls, new_urls = set(), set()

    if old_sitemap_path.exists():
        with old_sitemap_path.open("r") as file:
            old_sitemap = xmltodict.parse(file.read())
            old_urls.update(url["loc"] for url in old_sitemap["urlset"]["url"])

    with new_sitemap_path.open("r") as file:
        new_sitemap = xmltodict.parse(file.read())
        new_urls.update(url["loc"] for url in new_sitemap["urlset"]["url"])

    added_urls = new_urls - old_urls
    if added_urls:
        with Path("txt_files/new_urls.txt").open("w") as file:
            for url in added_urls:
                if "pieces-" in url:
                    urls_id = url.split("pieces-")[1]
                    file.write(f"{urls_id}\n")
        print(f"{len(added_urls)} nouvelles URLs ont été ajoutées.")


def get_ad_infos(dossier_id):
    query = {
        "wantLibre": False,
        "wantOccupe": False,
        "wantATerme": False,
        "bouquet": {"min": 0, "max": -1},
        "rente": {"min": 0, "max": -1},
        "where": [],
        "sqlQuery": {
            "id": 0,
            "dossierId": [dossier_id],
            "mandatIds": None,
            "orderBy": {},
            "limit": 50,
            "offset": 0,
            "ignoreDossierIds": [],
        },
        "_hashFieldDic": {"where": "w", "wantOccupe": "o", "wantLibre": "l"},
        "getLabelsFor": None,
        "isExtendedSearch": False,
        "isFullyExtendedSearch": False,
        "Options": {},
        "bien_type_id": -1,
        "options": {"forceCount": True},
    }
    header = {"Content-Type": "application/json"}

    response = requests.post(
        "https://www.costes-viager.com/api_se/annonces2",
        json=query,
        headers=header,
    )

    json_r = response.json()
    with json_locker:
        with Path("json_files/all_ads.json").open("a") as f:
            json.dump(json_r, f, ensure_ascii=False)
            f.write("\n")
        print(f"Annonce {dossier_id} récupérée.")
    return json_r


def download_sitemap(url, save_path):
    save_dir.mkdir(exist_ok=True)
    if save_path.exists():
        print(f"Le fichier {save_path} existe déjà. Téléchargement annulé.")
        return

    response = requests.get(
        url, headers=HEADERS, proxies=PROXIES if PROXY_SERVER else None
    )
    if response.status_code == 200:
        with save_path.open("wb") as file:
            file.write(response.content)
        print(f"Sitemap téléchargé et sauvegardé à {save_path}")
    else:
        print(f"Erreur {response.status_code}: Impossible de télécharger {url}")


def parse_sitemap(save_path):
    with save_path.open("r") as file:
        sitemap = xmltodict.parse(file.read())
    for sitemap in sitemap["urlset"]["url"]:
        if "pieces-" in sitemap["loc"]:
            with Path("txt_files/dossiers_ids.txt").open("a") as file:
                file.write(sitemap["loc"].split("pieces-")[1] + "\n")


def keep_unique_ads():
    dossier_ids_path = Path("txt_files/dossiers_ids.txt")
    with dossier_ids_path.open("r") as file:
        urls = set(file.readlines())
    with dossier_ids_path.open("w") as file:
        file.writelines(urls)


def full_reset_scrap():
    Path("txt_files/new_urls.txt").write_text("")
    Path("txt_files/dossiers_ids.txt").write_text("")
    Path("json_files/all_ads.json").write_text("")
    Path("json_files/unique_ads.json").write_text("")
    Path("sitemaps/sitemap.xml").unlink()


def main():
    if config("FULL_RESET_SCRAP", default=False, cast=bool):
        full_reset_scrap()
    compare_and_download_sitemap(sitemap_index_url, save_dir / "sitemap.xml")
    parse_sitemap(save_dir / "sitemap.xml")
    keep_unique_ads()

    with Path("txt_files/new_urls.txt").open("r") as file:
        urls = [url.strip() for url in file.readlines()]

    if not urls:
        with Path("txt_files/dossiers_ids.txt").open("r") as file:
            urls = [url.strip() for url in file.readlines()]
        return

    with ThreadPoolExecutor() as executor:
        executor.map(get_ad_infos, map(int, urls))

    Path("txt_files/new_urls.txt").write_text("")


if __name__ == "__main__":
    main()
