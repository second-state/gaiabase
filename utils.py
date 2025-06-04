def encrypt_data(obj):
    json_str = json.dumps(obj)
    base64_bytes = base64.b64encode(json_str.encode('utf-8'))
    encrypted_chars = [
        chr(b ^ ord(secret[i % len(secret)]))
        for i, b in enumerate(base64_bytes)
    ]
    return ''.join(encrypted_chars)


def decrypt_data(data):
    encrypted_bytes = bytes(
        ord(ch) ^ ord(secret[i % len(secret)])
        for i, ch in enumerate(data)
    )
    json_str = base64.b64decode(encrypted_bytes).decode('utf-8')
    return json.loads(json_str)