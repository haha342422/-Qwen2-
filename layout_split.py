def split_layout(text):
    header = ""
    body = ""
    footer = ""

    lines = text.split("\n")

    for i, line in enumerate(lines):
        if "抄送" in line or "印发" in line:
            footer = "\n".join(lines[i:])
            body = "\n".join(lines[:i])
            break
    else:
        body = text

    header = lines[0] if lines else ""

    return header, body, footer