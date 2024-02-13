# /usr/bin/env python3
import json
import os
import hashlib
import requests
from decouple import config
import xmltodict
import threading
from concurrent.futures import ThreadPoolExecutor

sitemap_index_url = "https://www.costes-viager.com/sitemap.xml"
save_dir = "sitemaps"


HEADERS = {
    "Host": "www.costes-viager.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.63 Safari/537.36",  # noqa
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "*/*",
    "Connection": "close",
}


PROXY_SERVER = config("PROXY_SERVER")
PROXIES = {"http": PROXY_SERVER, "https": PROXY_SERVER}
json_lock = threading.Lock()


def hash_file(filepath):
    """Calcule le hash SHA256 d'un fichier."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def compare_and_download_sitemap(url, save_path):
    """Compare et télécharge le sitemap si différent, puis extrait les URLs nouvelles."""
    new_sitemap_path = save_path + "_new"
    download_sitemap(url, new_sitemap_path)

    if os.path.exists(save_path) and hash_file(save_path) == hash_file(new_sitemap_path):
        print("Le sitemap n'a pas changé.")
        os.remove(new_sitemap_path)
    else:
        print("Le sitemap a changé. Mise à jour en cours.")
        extract_new_urls(save_path, new_sitemap_path)
        os.replace(new_sitemap_path, save_path)

def extract_new_urls(old_sitemap_path, new_sitemap_path):
    """Extrait et sauvegarde les nouvelles URLs."""
    old_urls = set()
    new_urls = set()

    if os.path.exists(old_sitemap_path):
        with open(old_sitemap_path, "r") as file:
            old_sitemap = xmltodict.parse(file.read())
            for url in old_sitemap["urlset"]["url"]:
                old_urls.add(url["loc"])

    with open(new_sitemap_path, "r") as file:
        new_sitemap = xmltodict.parse(file.read())
        for url in new_sitemap["urlset"]["url"]:
            new_urls.add(url["loc"])

    added_urls = new_urls - old_urls
    if added_urls:
        with open("new_urls.txt", "w") as file:
            for url in added_urls:
                urls_id = url.split("pieces-")[1]
                file.write(urls_id + "\n")
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
    header = {
        "Content-Type": "application/json",
    }
    response = requests.post(
        "https://www.costes-viager.com/api_se/annonces2",
        json=query,
        headers=header,
        # proxies=PROXIES,
    )
    with json_lock:
        json_r = response.json()
        with open("json_files/all_ads.json", "a") as f:
            json.dump(json_r, f, ensure_ascii=False)
            f.write("\n")
    return json_r


def download_sitemap(url, save_path):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    if not save_path.startswith("sitemaps"):
        return
    if os.path.exists(save_path):
        print(f"Le fichier {save_path} existe déjà. Téléchargement annulé.")
        return

    response = requests.get(url, headers=HEADERS, proxies=PROXIES)
    if response.status_code == 200:
        with open(save_path, "wb") as file:
            file.write(response.content)
        print(f"Sitemap téléchargé et sauvegardé à {save_path}")
    else:
        print(f"Erreur {response.status_code}: Impossible de télécharger {url}")


def parse_sitemap(save_path):
    with open(save_path, "r") as file:
        sitemap = xmltodict.parse(file.read())
    for sitemap in sitemap["urlset"]["url"]:
        if "pieces-" in sitemap["loc"]:
            with open("txt_files/dossiers_ids.txt", "a") as file:
                file.write(sitemap["loc"].split("pieces-")[1] + "\n")


def keep_unique_ads():
    with open("txt_files/dossiers_ids.txt", "r") as file:
        urls = file.readlines()
    urls = list(set(urls))
    with open("txt_files/dossiers_ids.txt", "w") as file:
        file.writelines(urls)


def main():
    compare_and_download_sitemap(sitemap_index_url, "sitemaps/sitemap.xml")
    parse_sitemap("sitemaps/sitemap.xml")
    keep_unique_ads()
    urls = []
    temp = 0
    with open("txt_files/new_urls.txt", "r") as file:
        urls = file.readlines()
        temp = 1
    if not urls:
        with open("txt_files/dossiers_ids.txt", "r") as file:
            urls = file.readlines()
        return 0 # On a déjà téléchargé les annonces
    with ThreadPoolExecutor() as executor:
        for dossier_id in urls:
            dossier_id = int(dossier_id.replace("\n", "").strip())
            executor.submit(get_ad_infos, dossier_id)
        executor.shutdown(wait=True)
    if temp == 1:
        open("txt_files/new_urls.txt", "w").close()
        with open("txt_files/dossiers_ids.txt", "a") as file:
            for url in urls:
                file.write(url.replace("\n", "").strip() + "\n")
    print("Toutes les annonces ont été téléchargées.")

if __name__ == "__main__":
    main()
