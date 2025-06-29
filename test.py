import base64

with open("google-credentials.json", "rb") as f_in, open("key.b64.txt", "wb") as f_out:
    f_out.write(base64.b64encode(f_in.read()))