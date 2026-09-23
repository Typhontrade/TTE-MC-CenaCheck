import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

TTE_XML = "data/tte.xml"
OUTPUT_JSON = "eponuda-test.json"

TEST_PRODUCTS = 20


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


def get_page(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "sr-RS,sr;q=0.9,en;q=0.8",
        },
    )

    try:

        with urllib.request.urlopen(request, timeout=30) as response:

            return response.read().decode(
                "utf-8",
                errors="ignore"
            )

    except Exception as e:

        print("  GREŠKA:", e)

        return ""


def search_eponuda(product):

    ean = product["ean"]

    name = product["tte_naziv"]

    # Prvo pokušavamo direktnu Eponuda pretragu po nazivu.
    query = urllib.parse.quote(
        f"{product['brand']} {name}"
    )

    url = (
        "https://www.eponuda.com/"
        f"pretraga?q={query}"
    )

    print("  Pretraga:", url)

    html = get_page(url)

    return html, url


def find_product_url(html):

    if not html:
        return None

    # Eponuda product URL završava sa -cena-BROJ
    pattern = (
        r'https://www\.eponuda\.com/'
        r'[^"\']+?-cena-\d+'
    )

    matches = re.findall(
        pattern,
        html,
        re.IGNORECASE
    )

    if matches:

        # ukloni moguće duplikate
        unique = []

        for url in matches:

            if url not in unique:
                unique.append(url)

        return unique[0]

    return None


def find_prices(html):

    result = {

        "eponuda_min": None,
        "eponuda_min_seller": None,

        "big_bang": None,
        "bazzar": None,
        "eplaneta": None,
        "superfon": None,

    }

    if not html:
        return result

    # Pretvori HTML u lakši tekst
    text = re.sub(
        r"<script.*?</script>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL
    )

    text = re.sub(
        r"<style.*?</style>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    # ------------------------------------------------
    # Pronađi sve RSD cene
    # ------------------------------------------------

    price_pattern = (
        r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?)"
        r"\s*(?:din|RSD)"
    )

    prices = re.findall(
        price_pattern,
        text,
        re.IGNORECASE
    )

    numeric_prices = []

    for p in prices:

        p = p.replace(".", "")
        p = p.replace(" ", "")
        p = p.replace(",", ".")

        try:

            value = float(p)

            if value > 0:
                numeric_prices.append(value)

        except:
            pass

    if numeric_prices:

        result["eponuda_min"] = min(
            numeric_prices
        )

    # ------------------------------------------------
    # Prodavci
    # ------------------------------------------------

    sellers = {

        "big_bang": [
            "Big Bang",
            "BC Group",
            "BCGROUP"
        ],

        "bazzar": [
            "Bazzar"
        ],

        "eplaneta": [
            "Eplaneta",
            "ePlaneta"
        ],

        "superfon": [
            "Superfon"
        ],

    }

    lower = text.lower()

    for key, names in sellers.items():

        positions = []

        for seller in names:

            position = lower.find(
                seller.lower()
            )

            if position >= 0:
                positions.append(position)

        if not positions:
            continue

        position = min(positions)

        # Uzmi 1.500 karaktera oko prodavca
        start = max(
            0,
            position - 1000
        )

        end = min(
            len(text),
            position + 2000
        )

        nearby = text[start:end]

        nearby_prices = re.findall(
            price_pattern,
            nearby,
            re.IGNORECASE
        )

        values = []

        for p in nearby_prices:

            p = p.replace(".", "")
            p = p.replace(" ", "")
            p = p.replace(",", ".")

            try:

                value = float(p)

                if value > 0:
                    values.append(value)

            except:
                pass

        if values:

            result[key] = min(values)

    # ------------------------------------------------
    # Najniža cena među poznatim prodavcima
    # ------------------------------------------------

    seller_prices = {

        "Big Bang": result["big_bang"],
        "Bazzar": result["bazzar"],
        "Eplaneta": result["eplaneta"],
        "Superfon": result["superfon"],

    }

    valid = {

        seller: price
        for seller, price
        in seller_prices.items()
        if price is not None

    }

    if valid:

        seller = min(
            valid,
            key=valid.get
        )

        result["eponuda_min"] = valid[seller]
        result["eponuda_min_seller"] = seller

    return result


def main():

    print("=" * 70)
    print("EPONUDA TEST - VERZIJA 2")
    print("=" * 70)

    products = get_tte_products()

    print(
        f"\nTestira se {len(products)} TTE proizvoda."
    )

    results = []

    for i, product in enumerate(
        products,
        start=1
    ):

        print()
        print("=" * 70)

        print(
            f"{i}/{len(products)}"
        )

        print(
            f"TTE šifra: {product['tte_sifra']}"
        )

        print(
            f"Naziv: {product['tte_naziv']}"
        )

        print(
            f"EAN: {product['ean']}"
        )

        print(
            f"TTE cena: {product['tte_cena']}"
        )

        result = {

            **product,

            "eponuda_url": None,

            "eponuda_min": None,

            "eponuda_min_seller": None,

            "big_bang": None,

            "bazzar": None,

            "eplaneta": None,

            "superfon": None,

            "match": "NEMA MATCHA",

        }

        html, search_url = search_eponuda(
            product
        )

        result["eponuda_search_url"] = search_url

        if not html:

            print(
                "  ❌ Eponuda nije vratila stranicu."
            )

            results.append(result)

            continue

        product_url = find_product_url(
            html
        )

        if not product_url:

            print(
                "  ❌ Nije pronađena Eponuda stranica."
            )

            results.append(result)

            continue

        print(
            "  ✅ pronađen proizvod:"
        )

        print(
            f"  {product_url}"
        )

        product_html = get_page(
            product_url
        )

        if not product_html:

            results.append(result)

            continue

        prices = find_prices(
            product_html
        )

        result.update(prices)

        result["eponuda_url"] = product_url

        result["match"] = "MATCH"

        print(
            f"  Eponuda MIN: "
            f"{result['eponuda_min']}"
        )

        print(
            f"  Prodavac: "
            f"{result['eponuda_min_seller']}"
        )

        print(
            f"  Big Bang: "
            f"{result['big_bang']}"
        )

        print(
            f"  Bazzar: "
            f"{result['bazzar']}"
        )

        print(
            f"  Eplaneta: "
            f"{result['eplaneta']}"
        )

        print(
            f"  Superfon: "
            f"{result['superfon']}"
        )

        results.append(result)

        # Pauza
        time.sleep(2)

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
    print("=" * 70)
    print(
        "TEST ZAVRŠEN"
    )
    print("=" * 70)

    print(
        f"Rezultat: {OUTPUT_JSON}"
    )


if __name__ == "__main__":
    main()
