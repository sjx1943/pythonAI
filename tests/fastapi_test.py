import requests

def external_api(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"An error occurred: {err}")

# 调用函数
# external_api("https://jsonplaceholder.typicode.com/posts/1")
print(external_api("https://jsonplaceholder.typicode.com/posts/1"))
