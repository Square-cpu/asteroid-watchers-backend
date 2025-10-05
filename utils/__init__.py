def get_locale(request_obj):
    return request_obj.args.get("locale", "gb")


def unpack_dictionary(dictionary, keys):
    response = []
    for key in keys:
        response.append(dictionary.get(key, None))

    # Checking corner cases
    if len(response) == 1:
        return response[0]
    elif len(response) == 0:
        return None

    return response
