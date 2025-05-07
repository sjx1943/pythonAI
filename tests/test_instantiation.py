import base64

def get_file_content_as_base64(path, urlencoded=False):

    with open(path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf8")
        if urlencoded:
            content = urllib.parse.quote_plus(content)
    return content

print(get_file_content_as_base64("flower.png"))