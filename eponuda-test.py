import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

TTE_XML = "data/tte.xml"
OUTPUT_JSON = "eponuda-test.json"

TEST_PRODUCTS = 20

SELLERS = {
    "big bang": "Big Bang",
    "bazzar": "Bazzar",
    "eplaneta": "Eplaneta",
    "superfon": "Superfon",
}


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def get_tte_products():
    tree = ET.parse(TTE_XML)
    root = tree.getroot()

    products = []

    for product in root.findall(".//product"):
        ean = clean_text(product.findtext("ean"))

        if not ean:
            continue

        products.append({
            "tte_sifra": clean_text(product.findtext("article_number")),
            "tte_naziv": clean_text(product.findtext("name")),
            "brand": clean_text(product.findtext("brand")),
            "ean": ean,
            "tte_cena": clean_text(product.findtext("price")),
        })

        if len(products) >= TEST_PRODUCTS:
            break

    return products


def search_eponuda(ean):
    """
    Pretraga javnog Eponuda sajta preko Google/Bing-style
    query URL-a nije pouzdana, zato ovde koristimo direktnu
    Eponuda pretragu.
    """

    query = urllib.parse.quote(ean)

    url = f"https://www.eponuda.com/pretraga?q={query}"

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            )
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8", errors="ignore")

        return html, url

    except Exception as e:
        print(f"  Greška pri pristupu Eponudi: {e}")
        return "", url


def extract_product_url(html):
    """
    Pokušava da pronađe prvi Eponuda product URL.
    """

    patterns = [
        r'href="(https://www\.eponuda\.com/[^"]+-cena-\d+)"',
        r'href="(/[^"]+-cena-\d+)"',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)

        if matches:
            url = matches[0]

            if url.startswith("/"):
                url = "https://www.eponuda.com" + url

            return url

    return None


def download_page(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            )
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="ignore")

    except Exception as e:
        print(f"  Greška pri učitavanju proizvoda: {e}")
        return ""


def extract_prices(html):
    """
    Pokušava da pronađe prodavce i njihove cene
    iz HTML-a Eponuda stranice.

    Ovo je TEST verzija.
    Kada vidimo stvarnu strukturu HTML-a, prilagodićemo
    parser precizno toj strukturi.
    """

    result = {
        "eponuda_min": None,
        "eponuda_min_seller": None,
        "big_bang": None,
        "bazzar": None,
        "eplaneta": None,
        "superfon": None,
    }

    # Pronalazimo blokove koji sadrže cenu + naziv prodavca.
    # Za početni test pokušavamo da pronađemo RSD cene.
    price_matches = re.findall(
        r'([0-9][0-9\.,]{1,12})\s*(?:RSD|din)',
        html,
        re.IGNORECASE,
    )

    prices = []

    for price in price_matches:
        price = price.replace(".", "").replace(",", ".")

        try:
            value = float(price)

            if value > 0:
                prices.append(value)

        except ValueError:
            pass

    if prices:
        result["eponuda_min"] = min(prices)

    # Prodavce tražimo u okolini njihovog naziva.
    lower_html = html.lower()

    for seller_key, seller_name in SELLERS.items():

        if seller_key not in lower_html:
            continue

        # Uzmi deo HTML-a oko prvog pojavljivanja prodavca
        position = lower_html.find(seller_key)

        nearby = html[
            max(0, position - 2000):
            min(len(html), position + 5000)
        ]

        nearby_prices = re.findall(
            r'([0-9][0-9\.,]{1,12})\s*(?:RSD|din)',
            nearby,
            re.IGNORECASE,
        )

        seller_prices = []

        for price in nearby_prices:
            price = price.replace(".", "").replace(",", ".")

            try:
                value = float(price)

                if value > 0:
                    seller_prices.append(value)

            except ValueError:
                pass

        if seller_prices:
            result[seller_key.replace(" ", "_")] = min(seller_prices)

    return result


def main():

    print("=" * 60)
    print("EPONUDA TEST")
    print("=" * 60)

    products = get_tte_products()

    print(f"\nPronađeno TTE artikala za test: {len(products)}")

    results = []

    for index, product in enumerate(products, start=1):

        print()
        print("-" * 60)
        print(f"{index}/{len(products)}")
        print(f"TTE šifra: {product['tte_sifra']}")
        print(f"Naziv: {product['tte_naziv']}")
        print(f"EAN: {product['ean']}")
        print(f"TTE cena: {product['tte_cena']}")

        html, search_url = search_eponuda(product["ean"])

        result = {
            **product,
            "eponuda_search_url": search_url,
            "eponuda_url": None,
            "eponuda_min": None,
            "eponuda_min_seller": None,
            "big_bang": None,
            "bazzar": None,
            "eplaneta": None,
            "superfon": None,
            "match": "NEMA MATCHA",
        }

        if not html:
            print("  ❌ Nema odgovora sa Eponude")

            results.append(result)
            continue

        product_url = extract_product_url(html)

        if not product_url:
            print("  ❌ Nije pronađena Eponuda stranica proizvoda")

            results.append(result)
            continue

        print(f"  ✅ Eponuda proizvod: {product_url}")

        product_html = download_page(product_url)

        if not product_html:
            results.append(result)
            continue

        prices = extract_prices(product_html)

        result.update(prices)
        result["eponuda_url"] = product_url
        result["match"] = "MATCH EAN"

        # Odredi najnižeg prodavca među poznatim prodavcima
        seller_prices = {
            "Big Bang": result["big_bang"],
            "Bazzar": result["bazzar"],
            "Eplaneta": result["eplaneta"],
            "Superfon": result["superfon"],
        }

        valid_prices = {
            seller: price
            for seller, price in seller_prices.items()
            if price is not None
        }

        if valid_prices:

            lowest_seller = min(
                valid_prices,
                key=valid_prices.get
            )

            result["eponuda_min"] = valid_prices[lowest_seller]
            result["eponuda_min_seller"] = lowest_seller

        print(f"  Najniža cena: {result['eponuda_min']}")
        print(f"  Prodavac: {result['eponuda_min_seller']}")
        print(f"  Big Bang: {result['big_bang']}")
        print(f"  Bazzar: {result['bazzar']}")
        print(f"  Eplaneta: {result['eplaneta']}")
        print(f"  Superfon: {result['superfon']}")

        results.append(result)

        # Pauza između proizvoda
        time.sleep(3)

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 60)
    print("TEST ZAVRŠEN")
    print("=" * 60)
    print(f"Rezultat je sačuvan u: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
