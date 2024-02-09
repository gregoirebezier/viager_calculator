import requests
import json


def get_all_ads(all_dossier_ids=[]):
    query = {
        "wantLibre": False,
        "wantOccupe": False,
        "wantATerme": False,
        "bouquet": {"min": 0, "max": -1},
        "rente": {"min": 0, "max": -1},
        "where": [],
        "sqlQuery": {
            "id": 0,
            "dossierId": None,
            "mandatIds": None,
            "orderBy": {},
            "limit": 50,
            "offset": 0,
            "ignoreDossierIds": all_dossier_ids,
        },
        "_hashFieldDic": {"where": "w", "wantOccupe": "o", "wantLibre": "l"},
        "getLabelsFor": None,
        "isExtendedSearch": False,
        "isFullyExtendedSearch": False,
        "Options": {},
        "bien_type_id": -1,
        "options": {"forceCount": True},
    }

    response = requests.post(
        "https://www.costes-viager.com/api_se/annonces2", json=query
    )
    json_r = response.json()
    all_dossier_ids += [ad["dossier_id"] for ad in json_r["results"]["annonces"]]
    return json_r, all_dossier_ids


def main():
    all_ads = []
    all_dossier_ids = []
    while True:
        json_r, all_dossier_ids = get_all_ads(all_dossier_ids)
        all_ads += json_r["results"]["annonces"]
        if len(all_ads) >= json_r["results"]["total"]:
            break
    with open("all_ads.json", "w") as f:
        json.dump(all_ads, f, indent=4)


if __name__ == "__main__":
    main()
