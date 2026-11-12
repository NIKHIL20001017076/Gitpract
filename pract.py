
import requests

ip_array = [
   "10.10.5.127"
]

for ip in ip_array:

    url = f"https://ipapi.co/{ip}/json/"

    try:
        response = requests.get(url, timeout=15)

        print("\nIP:", ip)
        print("Status Code:", response.status_code)
        print("Raw Response:", response.text)

    except requests.RequestException as e:
        print("Request failed:", e)
