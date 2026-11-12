
import csv
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


# ==========================================
# CONFIGURATION
# ==========================================

INPUT_FILE = "companies.csv"
OUTPUT_FILE = "result.csv"

TIMEOUT = 12
DELAY = 0.3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    )
}

# US states
US_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california",
    "colorado", "connecticut", "delaware", "florida", "georgia",
    "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas",
    "kentucky", "louisiana", "maine", "maryland", "massachusetts",
    "michigan", "minnesota", "mississippi", "missouri", "montana",
    "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota",
    "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas", "utah",
    "vermont", "virginia", "washington", "west virginia",
    "wisconsin", "wyoming"
]

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
}

FOREIGN_COUNTRIES = [
    "india", "united kingdom", "uk", "england", "scotland",
    "canada", "australia", "new zealand", "germany", "france",
    "ireland", "singapore", "pakistan", "bangladesh", "china",
    "japan", "brazil", "south africa", "netherlands", "spain",
    "italy", "uae", "united arab emirates", "switzerland"
]

# Pages to check on each company's website
PAGES_TO_CHECK = [
    "",
    "about",
    "about-us",
    "services",
    "our-services",
    "contact",
    "contact-us"
]


# ==========================================
# 1. CHECK US LOCATION
# ==========================================

def check_us_address(address):

    if not address or not address.strip():
        return "Review"

    address_lower = address.lower()

    # Explicit US country indicators
    us_indicators = [
        "united states",
        "united states of america",
        "usa",
        "u.s.a",
        "u.s."
    ]

    if any(x in address_lower for x in us_indicators):
        return "Yes"

    # Check full US state names
    for state in US_STATES:
        if re.search(r"\b" + re.escape(state) + r"\b", address_lower):
            return "Yes"

    # Check comma-separated state abbreviations
    parts = [part.strip().upper() for part in address.split(",")]

    if any(part in US_STATE_CODES for part in parts):
        return "Yes"

    # Clear foreign country indicators
    if any(country in address_lower for country in FOREIGN_COUNTRIES):
        return "No"

    return "Review"


# ==========================================
# 2. CHECK EMPLOYEE SIZE
# ==========================================

def check_employee_size(size):

    if not size:
        return "Review"

    value = str(size).lower().strip()

    value = value.replace(",", "")

    if any(x in value for x in [
        "up to 15",
        "less than 15",
        "under 15"
    ]):
        return "Yes"

    # Handle values such as 16+, 20+, 50+
    if "+" in value:

        numbers = re.findall(r"\d+", value)

        if numbers:
            return "Yes" if int(numbers[0]) <= 15 else "No"

        return "Review"

    # Handle more than 15 / over 15
    if "more than" in value or "over" in value:

        numbers = re.findall(r"\d+", value)

        if numbers:
            return "No" if int(numbers[0]) >= 15 else "Review"

        return "Review"

    # Extract numbers
    numbers = re.findall(r"\d+", value)

    if not numbers:
        return "Review"

    # Range: 1-15, 11-50, 16-20
    if len(numbers) >= 2:

        minimum = int(numbers[0])
        maximum = int(numbers[1])

        if maximum <= 15:
            return "Yes"

        elif minimum > 15:
            return "No"

        else:
            return "Review"

    # Single number: 10 employees, 15 employees, 50 employees
    employee_count = int(numbers[0])

    return "Yes" if employee_count <= 15 else "No"


# ==========================================
# 3. NORMALIZE WEBSITE URL
# ==========================================

def normalize_url(url):

    if not url:
        return None

    url = url.strip()

    if not url:
        return None

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


# ==========================================
# 4. FETCH WEBSITE CONTENT
# ==========================================

def fetch_website_page(session, url):

    try:

        response = session.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()

        if "html" not in content_type:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove unnecessary HTML
        for tag in soup([
            "script",
            "style",
            "noscript",
            "svg",
            "footer"
        ]):
            tag.decompose()

        title = ""

        if soup.title:
            title = soup.title.get_text(" ", strip=True)

        description = ""

        description_tag = soup.find(
            "meta",
            attrs={"name": re.compile("^description$", re.I)}
        )

        if description_tag:
            description = description_tag.get("content", "")

        body_text = soup.get_text(" ", strip=True)

        combined_text = (
            title + " " + description + " " + body_text
        )

        return combined_text[:30000]

    except requests.RequestException:
        return None


# ==========================================
# 5. CHECK MULTIPLE WEBSITE PAGES
# ==========================================

def get_company_website_content(website):

    base_url = normalize_url(website)

    if not base_url:
        return "", "Failed"

    session = requests.Session()

    all_text = []
    successful_pages = 0

    try:

        # First visit homepage
        homepage_text = fetch_website_page(session, base_url)

        if homepage_text:
            all_text.append(homepage_text)
            successful_pages += 1

        else:
            return "", "Failed"

        # Visit About, Services and Contact pages
        for page in PAGES_TO_CHECK[1:]:

            page_url = urljoin(
                base_url.rstrip("/") + "/",
                page
            )

            page_text = fetch_website_page(session, page_url)

            if page_text:
                all_text.append(page_text)
                successful_pages += 1

            time.sleep(0.1)

        return " ".join(all_text).lower(), (
            "Success" if successful_pages > 0 else "Failed"
        )

    finally:
        session.close()


# ==========================================
# 6. DETECT IT INDUSTRY
# ==========================================

def detect_industry(text):

    if not text:
        return "Unclear", ""

    categories = {

        "Custom Software Development": [
            "custom software development",
            "custom software",
            "software engineering",
            "enterprise software development",
            "software solutions",
            "bespoke software",
            "custom application development"
        ],

        "App Development": [
            "mobile app development",
            "app development",
            "android app development",
            "ios app development",
            "application development",
            "mobile application development",
            "flutter development",
            "react native development"
        ],

        "Website Development": [
            "website development",
            "web development",
            "web design",
            "ecommerce development",
            "wordpress development",
            "shopify development",
            "web application development",
            "frontend development",
            "backend development"
        ],

        "IT Services": [
            "it services",
            "technology consulting",
            "software consulting",
            "digital transformation",
            "cloud solutions",
            "managed it services",
            "it consulting",
            "technology solutions"
        ]
    }

    # Find all matching categories and keywords
    matches = {}

    for category, keywords in categories.items():

        found = [
            keyword for keyword in keywords
            if keyword in text
        ]

        if found:
            matches[category] = found

    if not matches:
        return "Unclear", ""

    # Prefer the category with the most matching keywords
    best_category = max(
        matches,
        key=lambda category: len(matches[category])
    )

    evidence = ", ".join(matches[best_category][:5])

    return best_category, evidence


# ==========================================
# 7. FINAL ICP MATCH
# ==========================================

def check_icp(us_status, employee_status, industry):

    if us_status == "No" or employee_status == "No":
        return "No"

    if industry == "Unclear":
        return "Review"

    if us_status == "Review" or employee_status == "Review":
        return "Review"

    if industry in [
        "App Development",
        "Website Development",
        "Custom Software Development",
        "IT Services"
    ]:
        return "Yes"

    return "No"


# ==========================================
# 8. MAIN FUNCTION
# ==========================================

def main():

    try:

        with open(
            INPUT_FILE,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            rows = list(reader)

            original_headers = reader.fieldnames

        if not original_headers:
            print("CSV file is empty or headers are missing.")
            return

        # Required columns
        required_columns = [
            "Company Name",
            "Website",
            "Employee Size",
            "Company Address"
        ]

        missing_columns = [
            col for col in required_columns
            if col not in original_headers
        ]

        if missing_columns:

            print("Missing CSV columns:", missing_columns)
            print("Please check your CSV headers.")
            return

        # New result columns
        result_columns = [
            "US Based",
            "Employee <= 15",
            "Industry Domain",
            "ICP Match",
            "Website Check",
            "Industry Evidence"
        ]

        result_headers = original_headers + result_columns

        total = len(rows)

        print(f"\nTotal companies: {total}")
        print("Starting company checks...\n")

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8-sig",
            newline=""
        ) as output_file:

            writer = csv.DictWriter(
                output_file,
                fieldnames=result_headers
            )

            writer.writeheader()

            for index, row in enumerate(rows, start=1):

                company = row.get("Company Name", "").strip()

                website = row.get("Website", "")

                employee_size = row.get("Employee Size", "")

                address = row.get("Company Address", "")

                # Check US location
                us_status = check_us_address(address)

                # Check employee count
                employee_status = check_employee_size(
                    employee_size
                )

                # Check website pages
                website_text, website_status = (
                    get_company_website_content(website)
                )

                # Detect IT industry
                industry, evidence = detect_industry(
                    website_text
                )

                # Final ICP decision
                icp_match = check_icp(
                    us_status,
                    employee_status,
                    industry
                )

                # Add results
                row["US Based"] = us_status

                row["Employee <= 15"] = employee_status

                row["Industry Domain"] = industry

                row["ICP Match"] = icp_match

                row["Website Check"] = website_status

                row["Industry Evidence"] = evidence

                writer.writerow(row)

                output_file.flush()

                print(
                    f"[{index}/{total}] {company} | "
                    f"US: {us_status} | "
                    f"Employees: {employee_status} | "
                    f"Industry: {industry} | "
                    f"ICP: {icp_match}"
                )

                time.sleep(DELAY)

        print("\n================================")
        print("CHECKING COMPLETED!")
        print(f"Results saved in: {OUTPUT_FILE}")
        print("================================")

    except FileNotFoundError:

        print(f"Input file not found: {INPUT_FILE}")

    except PermissionError:

        print(
            "Permission denied. Close result.csv in Excel "
            "and run the script again."
        )

    except Exception as error:

        print("Unexpected error:", error)


if __name__ == "__main__":
    main()
