import re

def hideGroups(svgText, groupIds):
    # hides groups in a svg
    for groupId in groupIds:
        pattern = r'(<g\b[^>]*\bid="' + re.escape(groupId) + '")'
        svgText = re.sub(pattern, r'\1 display="none"', svgText, count=1)
    return svgText